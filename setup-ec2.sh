#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# fluidGo EC2 Bootstrap Script
# Compatible: Ubuntu 22.04 LTS AND Ubuntu 24.04 LTS (auto-detected)
# Instance:   t3.medium (4GB RAM minimum) or t3.large (8GB recommended)
#
# Usage:
#   1. Launch EC2 t3.medium or t3.large, Ubuntu 24.04 LTS, 50GB gp3 EBS
#   2. SSH in: ssh -i fluidgo.pem ubuntu@<EC2_PUBLIC_IP>
#   3. Run:   bash <(curl -fsSL https://raw.githubusercontent.com/amitipst/fluidgo/main/setup-ec2.sh)
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

DOMAIN="dsr.fluidpro.in"
APP_DIR="/opt/fluidgo"
REPO_URL="https://github.com/amitipst/fluidgo.git"
DEPLOY_USER="ubuntu"

# ── Detect OS version ─────────────────────────────────────────────────────────
OS_VERSION=$(lsb_release -rs 2>/dev/null || echo "24.04")
echo "╔══════════════════════════════════════════════╗"
echo "║   fluidGo EC2 Production Setup               ║"
echo "║   Ubuntu $OS_VERSION detected                       ║"
echo "╚══════════════════════════════════════════════╝"

# ── 1. System update ─────────────────────────────────────────────────────────
echo "▶ [1/9] Updating system packages..."
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get upgrade -y -qq
sudo apt-get install -y -qq \
    git curl wget unzip jq ca-certificates gnupg lsb-release \
    nginx certbot python3-certbot-nginx \
    ufw fail2ban \
    postgresql-client \
    htop ncdu

# ── 2. Docker (Ubuntu 24.04 compatible method) ───────────────────────────────
echo "▶ [2/9] Installing Docker..."
if ! command -v docker &>/dev/null; then
    # Official Docker install script — works on both 22.04 and 24.04
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sudo sh /tmp/get-docker.sh
    rm /tmp/get-docker.sh

    sudo usermod -aG docker "$DEPLOY_USER"
    sudo systemctl enable docker
    sudo systemctl start docker
    echo "   ✅ Docker installed: $(docker --version)"
else
    echo "   ✅ Docker already present: $(docker --version)"
fi

# Docker Compose plugin (v2) — Ubuntu 24.04 compatible
if ! docker compose version &>/dev/null; then
    sudo apt-get install -y -qq docker-compose-plugin
fi
echo "   ✅ Docker Compose: $(docker compose version --short)"

# ── 3. Create app directories ─────────────────────────────────────────────────
echo "▶ [3/9] Creating app directories..."
sudo mkdir -p "$APP_DIR"/{pgdata,ollama,backups,logs,certs}
sudo chown -R "$DEPLOY_USER:$DEPLOY_USER" "$APP_DIR"
chmod 750 "$APP_DIR/pgdata"
echo "   ✅ Directories at $APP_DIR"

# ── 4. Clone repo ─────────────────────────────────────────────────────────────
echo "▶ [4/9] Cloning repository..."
if [ -d "$APP_DIR/app/.git" ]; then
    echo "   ℹ️  Existing repo found — pulling latest..."
    cd "$APP_DIR/app" && git pull origin main
else
    git clone "$REPO_URL" "$APP_DIR/app"
fi
echo "   ✅ Code at $APP_DIR/app"

# ── 5. Environment file ───────────────────────────────────────────────────────
echo "▶ [5/9] Setting up environment..."
if [ ! -f "$APP_DIR/app/.env.prod" ]; then
    cp "$APP_DIR/app/.env.prod.example" "$APP_DIR/app/.env.prod"
    DB_PASS=$(openssl rand -base64 32 | tr -d '=/+' | head -c 32)
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/CHANGE_ME_strong_random_password/$DB_PASS/" "$APP_DIR/app/.env.prod"
    sed -i "s/CHANGE_ME_generate_64_char_hex_secret/$JWT_SECRET/" "$APP_DIR/app/.env.prod"
    sed -i "s/dsr\.fluidpro\.in/$DOMAIN/g" "$APP_DIR/app/.env.prod"
    echo ""
    echo "   ⚠️  Credentials saved to: $APP_DIR/app/.env.prod"
    echo "   Run: cat $APP_DIR/app/.env.prod  (save these NOW)"
    echo ""
else
    echo "   ✅ .env.prod exists — skipping"
fi

# ── 6. Firewall ───────────────────────────────────────────────────────────────
echo "▶ [6/9] Configuring firewall..."
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp   comment 'SSH'
sudo ufw allow 80/tcp   comment 'HTTP'
sudo ufw allow 443/tcp  comment 'HTTPS'
sudo ufw --force enable
echo "   ✅ UFW: SSH + HTTP + HTTPS"

# ── 7. Fail2ban ───────────────────────────────────────────────────────────────
echo "▶ [7/9] Enabling fail2ban..."
sudo systemctl enable fail2ban --now
cat <<'EOF' | sudo tee /etc/fail2ban/jail.d/fluidgo.conf > /dev/null
[nginx-limit-req]
enabled  = true
port     = http,https
logpath  = /var/log/nginx/error.log
maxretry = 10
findtime = 300
bantime  = 3600
EOF
sudo systemctl reload fail2ban
echo "   ✅ fail2ban active"

# ── 8. Systemd service ────────────────────────────────────────────────────────
echo "▶ [8/9] Creating systemd service..."
sudo tee /etc/systemd/system/fluidgo.service > /dev/null <<EOF
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
User=$DEPLOY_USER
TimeoutStartSec=300
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable fluidgo
echo "   ✅ systemd: fluidgo.service"

# ── 9. Backup cron ────────────────────────────────────────────────────────────
echo "▶ [9/9] Setting up backups..."
sudo tee /opt/fluidgo/backup.sh > /dev/null <<'BACKUP'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/fluidgo/backups"
# Get container name dynamically (handles different compose project names)
DB_CONTAINER=$(docker ps --filter "name=db" --format "{{.Names}}" | head -1)
if [ -z "$DB_CONTAINER" ]; then
    echo "ERROR: DB container not running"
    exit 1
fi
FILE="$BACKUP_DIR/fluidgo_$DATE.sql.gz"
docker exec "$DB_CONTAINER" pg_dump -U fluidgo fluidgo | gzip > "$FILE"
echo "Backup: $FILE ($(du -sh "$FILE" | cut -f1))"
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 -delete
echo "Pruned backups older than 7 days"
BACKUP
sudo chmod +x /opt/fluidgo/backup.sh
sudo chown "$DEPLOY_USER" /opt/fluidgo/backup.sh
(crontab -l 2>/dev/null; echo "30 2 * * * /opt/fluidgo/backup.sh >> /opt/fluidgo/logs/backup.log 2>&1") | crontab -
echo "   ✅ Daily backup at 2:30am"

# ── Done ──────────────────────────────────────────────────────────────────────
EC2_IP=$(curl -s --max-time 3 http://169.254.169.254/latest/meta-data/public-ipv4 || echo "<EC2_PUBLIC_IP>")
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   ✅ Bootstrap complete!                                     ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║                                                              ║"
echo "║  Your EC2 IP: $EC2_IP"
echo "║                                                              ║"
echo "║  Next steps (run in order):                                  ║"
echo "║                                                              ║"
echo "║  1. Review credentials:                                      ║"
echo "║     cat $APP_DIR/app/.env.prod                               ║"
echo "║                                                              ║"
echo "║  2. Build Docker images (~8 min first time):                 ║"
echo "║     cd $APP_DIR/app                                          ║"
echo "║     docker compose -f docker-compose.prod.yml build          ║"
echo "║                                                              ║"
echo "║  3. Start fluidGo:                                           ║"
echo "║     sudo systemctl start fluidgo                             ║"
echo "║     docker compose -f docker-compose.prod.yml logs -f        ║"
echo "║                                                              ║"
echo "║  4. Seed database (first time only):                         ║"
echo "║     docker compose -f docker-compose.prod.yml exec backend \ ║"
echo "║       python seed_v3.py                                      ║"
echo "║                                                              ║"
echo "║  5. Verify:                                                  ║"
echo "║     curl http://localhost:8000/api/health                    ║"
echo "║     curl http://$EC2_IP/                                     ║"
echo "║                                                              ║"
echo "║  6. SSL (after DNS points to this IP):                       ║"
echo "║     sudo certbot --nginx -d $DOMAIN                          ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
