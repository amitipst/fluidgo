#!/bin/bash
set -e
cd /etc/ssl/wepsol

echo "=== Downloading GlobalSign RSA OV SSL CA 2018 intermediate (official source, DER format) ==="
sudo curl -s -o gsrsaovsslca2018.der http://secure.globalsign.com/cacert/gsrsaovsslca2018.crt

echo "=== Converting DER to PEM ==="
sudo openssl x509 -inform DER -in gsrsaovsslca2018.der -outform PEM -out intermediate.crt

echo ""
echo "=== Verifying fingerprint matches GlobalSign's published value ==="
echo "Downloaded fingerprint:"
sudo openssl x509 -in intermediate.crt -noout -fingerprint -sha1
echo ""
echo "Must match GlobalSign's published SHA-1 fingerprint exactly:"
echo "df:e8:30:23:06:2b:99:76:82:70:8b:4e:ab:8e:81:9a:ff:5d:97:75"
echo ""
echo "!!! STOP AND CHECK: if these two do not match exactly, do NOT proceed. !!!"

echo ""
echo "=== Building fullchain (leaf + intermediate) ==="
sudo bash -c 'cat wepsol.crt intermediate.crt > fullchain.crt'
sudo chmod 644 fullchain.crt intermediate.crt
sudo rm -f gsrsaovsslca2018.der

echo ""
echo "=== Verifying the chain is valid ==="
sudo openssl verify -untrusted intermediate.crt wepsol.crt

echo ""
echo "=== Final file listing ==="
ls -la /etc/ssl/wepsol/
