#!/bin/bash
set -e
sudo mkdir -p /etc/ssl/wepsol
sudo mv /tmp/wepsol-ssl/wepsol.crt /etc/ssl/wepsol/wepsol.crt
sudo mv /tmp/wepsol-ssl/wildcard.wepsol.com.key /etc/ssl/wepsol/wildcard.wepsol.com.key
sudo chown root:root /etc/ssl/wepsol/wepsol.crt /etc/ssl/wepsol/wildcard.wepsol.com.key
sudo chmod 644 /etc/ssl/wepsol/wepsol.crt
sudo chmod 600 /etc/ssl/wepsol/wildcard.wepsol.com.key
rmdir /tmp/wepsol-ssl 2>/dev/null || true

echo "=== Cert details ==="
sudo openssl x509 -in /etc/ssl/wepsol/wepsol.crt -noout -subject -issuer -dates

echo ""
echo "=== How many certs are in the file? (1 = leaf only, needs intermediate added; 2+ = chain already included) ==="
sudo grep -c "BEGIN CERTIFICATE" /etc/ssl/wepsol/wepsol.crt

echo ""
echo "=== Do the cert and key actually match? These two hashes MUST be identical ==="
echo "cert modulus hash:"
sudo openssl x509 -noout -modulus -in /etc/ssl/wepsol/wepsol.crt | openssl md5
echo "key modulus hash:"
sudo openssl rsa -noout -modulus -in /etc/ssl/wepsol/wildcard.wepsol.com.key 2>/dev/null | openssl md5
