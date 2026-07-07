#!/bin/bash
echo "=== Current live nginx config ==="
sudo cat /etc/nginx/conf.d/fluidgo.conf

echo ""
echo "=== Any other nginx server blocks ==="
sudo ls -la /etc/nginx/conf.d/ /etc/nginx/sites-enabled/ 2>/dev/null

echo ""
echo "=== Is certbot already installed? ==="
which certbot || echo "not installed"

echo ""
echo "=== Confirm public IP matches expectation ==="
curl -s ifconfig.me
echo ""

echo ""
echo "=== .env.prod CORS/domain-related settings (secrets redacted) ==="
grep -iE "cors|domain" /opt/fluidgo/app/.env.prod 2>/dev/null || echo "no matches"
