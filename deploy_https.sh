#!/bin/bash
set -e

echo "=== Backing up current config ==="
sudo cp /etc/nginx/conf.d/fluidgo.conf /etc/nginx/conf.d/fluidgo.conf.bak-$(date +%Y%m%d_%H%M%S)
ls -la /etc/nginx/conf.d/*.bak-* | tail -1

echo ""
echo "=== Writing new config (IP stays HTTP-only, domain gets HTTPS + redirect) ==="
sudo tee /etc/nginx/conf.d/fluidgo.conf > /dev/null <<'EOF'
# ── Plain IP access — stays HTTP-only. A cert for *.wepsol.com cannot
#    cover a bare IP, so this is NOT redirected to HTTPS. Kept for
#    direct diagnostics/curl testing.
server {
    listen 80;
    server_name 65.2.205.77;

    location /api/ {
        proxy_pass         http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 260s;
    }
    location / {
        proxy_pass         http://127.0.0.1:3000/;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_cache_bypass $http_upgrade;
    }
}

# ── fluidgo.wepsol.com — HTTP redirects to HTTPS ──
server {
    listen 80;
    server_name fluidgo.wepsol.com;
    return 301 https://$host$request_uri;
}

# ── fluidgo.wepsol.com — HTTPS ──
server {
    listen 443 ssl http2;
    server_name fluidgo.wepsol.com;

    ssl_certificate     /etc/ssl/wepsol/fullchain.crt;
    ssl_certificate_key /etc/ssl/wepsol/wildcard.wepsol.com.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-CHACHA20-POLY1305:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers on;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 10m;

    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;

    location /api/ {
        proxy_pass         http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 260s;

        location /api/ai/analyse/stream {
            proxy_pass         http://127.0.0.1:8000/api/ai/analyse/stream;
            proxy_buffering    off;
            proxy_read_timeout 300s;
            proxy_set_header   Host $host;
            proxy_set_header   X-Real-IP $remote_addr;
            proxy_set_header   X-Forwarded-Proto $scheme;
        }
    }

    location / {
        proxy_pass         http://127.0.0.1:3000/;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
EOF

echo ""
echo "=== Testing config ==="
sudo nginx -t

echo ""
echo "=== If test passed, reloading ==="
sudo systemctl reload nginx

echo ""
echo "=== Verification ==="
echo "--- HTTP on IP (should still work, no redirect) ---"
curl -s -o /dev/null -w "%{http_code}\n" http://65.2.205.77/
echo "--- HTTP on domain (should be 301) ---"
curl -s -o /dev/null -w "%{http_code}\n" http://fluidgo.wepsol.com/
echo "--- HTTPS on domain ---"
curl -s https://fluidgo.wepsol.com/api/health
echo ""
echo "--- Cert chain check ---"
curl -svI https://fluidgo.wepsol.com/ 2>&1 | grep -i "subject\|issuer\|SSL certificate"
