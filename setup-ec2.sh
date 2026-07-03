#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# fluidGo EC2 Bootstrap Script
# Tested on: Ubuntu 22.04 LTS, t3.large (8GB RAM, 2 vCPU)
#
# Usage:
#   1. Launch EC2 t3.large, Ubuntu 22.04, 50GB gp3 EBS
#   2. SSH in: ssh -i fluidgo.pem ubuntu@<EC2_PUBLIC_IP>
#   3. Run:   bash <(curl -fsSL https://raw.githubusercontent.com/amitipst/fluidgo/main/setup-ec2.sh)
#      OR:    scp setup-ec2.sh ubuntu@<IP>:~ && bash setup-ec2.sh
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

DOMAIN="dsr.fluidpro.in"       # ← CHANGE to your actual domain
APP_DIR="/opt/fluidgo"
REPO_URL="https://github.com/amitipst/fluidgo.git"    # ← CHANGE to your repo URL
DEPLOY_USER="ubuntu"

echo "╔══════════════════════════════════════════════╗"
echo "║   fluidGo EC2 Production Setup               ║"
echo "╚══════════════════════════════════════════════╝"

# ── 1. System update + essentials ────────────────────────────────────────────
echo "▶ [1/9] Updating system packages..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq
sudo apt-get install -y -qq \
    git curl wget unzip jq \
    nginx certbot python3-certbot-nginx \
    ufw fail2ban \
    postgresql-client \
    htop ncdu

# ── 2. Docker ─────────────────────────────────────────────────────────────────
echo "▶ [2/9] Installing Docker..."
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$DEPLOY_USER"
    sudo systemctl enable docker
    sudo systemctl start docker
    echo "   ✅ Docker installed"
else
    echo "   ✅ Docker already installed: $(docker --version)"
fi

# Install docker compose plugin (v2)
if ! docker compose version &>/dev/null; then
    sudo apt-get install -y -qq docker-compose-plugin
fi
echo "   ✅ Docker Compose: $(docker compose version --short)"

# ── 3. Create app directories on EBS ─────────────────────────────────────────
echo "▶ [3/9] Creating app directories..."
sudo mkdir -p "$APP_DIR"/{pgdata,ollama,backups,logs,certs}
sudo chown -R "$DEPLOY_USER:$DEPLOY_USER" "$APP_DIR"
chmod 750 "$APP_DIR/pgdata"
echo "   ✅ Directories created at $APP_DIR"

# ── 4. Clone repo ─────────────────────────────────────────────────────────────
echo "▶ [4/9] Cloning repository..."
if [ -d "$APP_DIR/app" ]; then
    echo "   ℹ️  App directory exists — pulling latest..."
    cd "$APP_DIR/app" && git pull origin main
else
    git clone "$REPO_URL" "$APP_DIR/app"
fi
echo "   ✅ Code at $APP_DIR/app"

# ── 5. Environment file ────────────────────────────────────────────────────────
echo "▶ [5/9] Setting up environment..."
if [ ! -f "$APP_DIR/app/.env.prod" ]; then
    cp "$APP_DIR/app/.env.prod.example" "$APP_DIR/app/.env.prod"
    # Auto-generate secrets
    DB_PASS=$(openssl rand -base64 32 | tr -d '=/+' | head -c 32)
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/CHANGE_ME_strong_random_password/$DB_PASS/" "$APP_DIR/app/.env.prod"
    sed -i "s/CHANGE_ME_generate_64_char_hex_secret/$JWT_SECRET/" "$APP_DIR/app/.env.prod"
    sed -i "s/dsr\.fluidpro\.in/$DOMAIN/g" "$APP_DIR/app/.env.prod"
    echo ""
    echo "   ⚠️  IMPORTANT — Generated credentials saved to: $APP_DIR/app/.env.prod"
    echo "   Run: cat $APP_DIR/app/.env.prod  (save these somewhere safe)"
    echo ""
else
    echo "   ✅ .env.prod already exists — skipping"
fi

# ── 6. UFW Firewall ────────────────────────────────────────────────────────────
echo "▶ [6/9] Configuring firewall..."
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh          # 22
sudo ufw allow http         # 80
sudo ufw allow https        # 443
sudo ufw --force enable
echo "   ✅ Firewall: SSH + HTTP + HTTPS only"

# ── 7. Fail2ban ────────────────────────────────────────────────────────────────
echo "▶ [7/9] Enabling fail2ban..."
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

cat <<'EOF' | sudo tee /etc/fail2ban/jail.d/fluidgo.conf
[nginx-http-auth]
enabled = true
port    = http,https
logpath = /var/log/nginx/access.log
maxretry = 5
findtime = 300
bantime  = 3600
EOF
sudo systemctl reload fail2ban
echo "   ✅ fail2ban active"

# ── 8. Systemd service for fluidGo ───────────────────────────────────────────
echo "▶ [8/9] Creating systemd service..."
cat <<EOF | sudo tee /etc/systemd/system/fluidgo.service
[Unit]
Description=fluidGo Sales Platform
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$APP_DIR/app
EnvironmentFile=$APP_DIR/app/.env.prod
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up -d --remove-orphans
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml down
ExecReload=/usr/bin/docker compose -f docker-compose.prod.yml pull && /usr/bin/docker compose -f docker-compose.prod.yml up -d --remove-orphans
User=$DEPLOY_USER
TimeoutStartSec=300
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable fluidgo
echo "   ✅ systemd service: fluidgo.service"

# ── 9. Automated backup cron ──────────────────────────────────────────────────
echo "▶ [9/9] Setting up automated backups..."
cat <<'EOF' | sudo tee /opt/fluidgo/backup.sh
#!/bin/bash
# Daily PostgreSQL backup — keeps 7 days of dumps
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/fluidgo/backups"
FILE="$BACKUP_DIR/fluidgo_$DATE.sql.gz"

docker exec fluidgo-db-1 pg_dump -U fluidgo fluidgo | gzip > "$FILE"
echo "Backup: $FILE ($(du -sh "$FILE" | cut -f1))"

# Prune backups older than 7 days
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 -delete
echo "Cleanup: removed backups older than 7 days"
EOF
chmod +x /opt/fluidgo/backup.sh

# Run backup at 2:30am daily
(crontab -l 2>/dev/null; echo "30 2 * * * /opt/fluidgo/backup.sh >> /opt/fluidgo/logs/backup.log 2>&1") | crontab -
echo "   ✅ Daily backup cron: 2:30am → /opt/fluidgo/backups/"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   Bootstrap complete. Next steps:                    ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║                                                      ║"
echo "║  1. Point DNS:  $DOMAIN → $(curl -s ifconfig.me)"
echo "║  2. Run:   cd $APP_DIR/app"
echo "║  3. Build: docker compose -f docker-compose.prod.yml build"
echo "║  4. Start: sudo systemctl start fluidgo"
echo "║  5. SSL:   sudo certbot --nginx -d $DOMAIN"
echo "║  6. Seed:  docker compose -f docker-compose.prod.yml exec backend python seed_v3.py"
echo "║  7. Verify: curl https://$DOMAIN/api/health"
echo "║                                                      ║"
echo "║  Review creds: cat $APP_DIR/app/.env.prod            ║"
echo "╚══════════════════════════════════════════════════════╝"
