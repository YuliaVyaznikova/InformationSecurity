#!/usr/bin/env bash
# Создание локальных сертификатов для защищённых соединений HTTPS и Bolt через TLS.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f certificates/shared/public.crt ]]; then
  echo "Сертификаты уже созданы, повторно не создаю."
  exit 0
fi

mkdir -p certificates/shared
MSYS_NO_PATHCONV=1 openssl req -x509 -newkey rsa:2048 -sha256 -days 365 -nodes \
  -keyout certificates/shared/private.key \
  -out certificates/shared/public.crt \
  -subj "/CN=localhost/O=NSU Neo4j Security Lab" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" >/dev/null 2>&1

for scope in bolt https; do
  mkdir -p "certificates/$scope/trusted" "certificates/$scope/revoked"
  cp certificates/shared/private.key "certificates/$scope/private.key"
  cp certificates/shared/public.crt "certificates/$scope/public.crt"
  cp certificates/shared/public.crt "certificates/$scope/trusted/public.crt"
done

echo "Сертификаты созданы в stand/certificates."
