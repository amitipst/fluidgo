#!/bin/bash
echo "=== Current server_name line in fluidgo.conf ==="
sudo grep -n "server_name" /etc/nginx/conf.d/fluidgo.conf

echo ""
echo "=== Setting it to the real domain ==="
sudo sed -i 's/server_name _;/server_name fluidgo.wepsol.com;/' /etc/nginx/conf.d/fluidgo.conf
sudo grep -n "server_name" /etc/nginx/conf.d/fluidgo.conf

echo ""
echo "=== Test + reload ==="
sudo nginx -t && sudo systemctl reload nginx

echo ""
echo "=== Verify: should now be fluidGo, not the nginx welcome page ==="
curl -s http://fluidgo.wepsol.com/ | head -c 300
echo ""
curl -s http://fluidgo.wepsol.com/api/health
echo ""
