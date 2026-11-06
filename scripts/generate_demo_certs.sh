#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
CERT_DIR="$REPO_ROOT/certs"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT
umask 077

mkdir -p "$CERT_DIR"

openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "$TMP_DIR/ca.key" \
  -out "$CERT_DIR/ca.crt" \
  -days 3650 \
  -sha256 \
  -subj "/CN=Specmatic Arazzo Auth Demo CA" \
  -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
  -addext "keyUsage=critical,keyCertSign,cRLSign"

printf '01\n' > "$TMP_DIR/ca.srl"

openssl req -new -newkey rsa:2048 -nodes \
  -keyout "$CERT_DIR/server.key" \
  -out "$TMP_DIR/server.csr" \
  -subj "/CN=specmatic-arazzo-auth-shared-server"

cat > "$TMP_DIR/server.ext" <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:localhost,DNS:location,DNS:products,DNS:orders,DNS:inventory,IP:127.0.0.1
EOF

openssl x509 -req \
  -in "$TMP_DIR/server.csr" \
  -CA "$CERT_DIR/ca.crt" \
  -CAkey "$TMP_DIR/ca.key" \
  -CAserial "$TMP_DIR/ca.srl" \
  -out "$CERT_DIR/server.crt" \
  -days 3650 \
  -sha256 \
  -extfile "$TMP_DIR/server.ext"

openssl req -new -newkey rsa:2048 -nodes \
  -keyout "$CERT_DIR/client.key" \
  -out "$TMP_DIR/client.csr" \
  -subj "/CN=specmatic-arazzo-auth-demo-client"

cat > "$TMP_DIR/client.ext" <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=clientAuth
EOF

openssl x509 -req \
  -in "$TMP_DIR/client.csr" \
  -CA "$CERT_DIR/ca.crt" \
  -CAkey "$TMP_DIR/ca.key" \
  -CAserial "$TMP_DIR/ca.srl" \
  -out "$CERT_DIR/client.crt" \
  -days 3650 \
  -sha256 \
  -extfile "$TMP_DIR/client.ext"

openssl pkcs12 -export \
  -in "$CERT_DIR/client.crt" \
  -inkey "$CERT_DIR/client.key" \
  -certfile "$CERT_DIR/ca.crt" \
  -name specmatic-client \
  -out "$TMP_DIR/specmatic-client.p12" \
  -passout pass:changeit

rm -f "$CERT_DIR/specmatic-client.jks"
keytool -importkeystore -noprompt \
  -srckeystore "$TMP_DIR/specmatic-client.p12" \
  -srcstoretype PKCS12 \
  -srcstorepass changeit \
  -srcalias specmatic-client \
  -destkeystore "$CERT_DIR/specmatic-client.jks" \
  -deststoretype JKS \
  -deststorepass changeit \
  -destkeypass changeit \
  -destalias specmatic-client

keytool -importcert -noprompt \
  -alias specmatic-arazzo-auth-demo-ca \
  -file "$CERT_DIR/ca.crt" \
  -keystore "$CERT_DIR/specmatic-client.jks" \
  -storetype JKS \
  -storepass changeit

chmod 755 "$CERT_DIR"
chmod 644 "$CERT_DIR/ca.crt" "$CERT_DIR/server.crt" "$CERT_DIR/client.crt"
chmod 600 "$CERT_DIR/server.key" "$CERT_DIR/client.key" "$CERT_DIR/specmatic-client.jks"

printf 'Created demo-only mTLS certificates in %s\n' "$CERT_DIR"
