#!/bin/bash
cd /etc/ssl/wepsol

echo "=== Checking for CRLF (Windows line endings) in wepsol.crt ==="
sudo cat -A wepsol.crt | head -3
echo "(if you see ^M at line ends above, that's CRLF - confirmed cause)"

echo ""
echo "=== Does wepsol.crt end with a newline? ==="
sudo bash -c 'if [ "$(tail -c1 wepsol.crt | wc -l)" -eq 1 ]; then echo "yes, ends cleanly"; else echo "NO trailing newline - this breaks concatenation"; fi'

echo ""
echo "=== Rebuilding: strip any CRLF, ensure clean line breaks, rebuild fullchain ==="
sudo bash -c "
  tr -d '\r' < wepsol.crt > wepsol_clean.crt
  tr -d '\r' < intermediate.crt > intermediate_clean.crt
  cat wepsol_clean.crt > fullchain.crt
  echo '' >> fullchain.crt
  cat intermediate_clean.crt >> fullchain.crt
  rm wepsol_clean.crt intermediate_clean.crt
  chmod 644 fullchain.crt
"

echo ""
echo "=== How many certs in the rebuilt fullchain? (should be 2) ==="
sudo grep -c "BEGIN CERTIFICATE" fullchain.crt

echo ""
echo "=== Verify chain again ==="
sudo openssl verify -untrusted intermediate.crt wepsol.crt

echo ""
echo "=== Can nginx's own PEM parser read it now? ==="
sudo openssl x509 -in fullchain.crt -noout -subject
sudo openssl x509 -in fullchain.crt -noout -text 2>&1 | grep -c "Certificate:"

echo ""
echo "=== Now test nginx config ==="
sudo nginx -t
