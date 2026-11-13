#!/usr/bin/env bash
# Первоначальное развёртывание стенда: сертификаты, контейнер, тестовые данные и роли N 64.
set -euo pipefail
cd "$(dirname "$0")/.."

if docker ps --format '{{.Names}}' | grep -qx neo4j-security-lab; then
  echo "Останавливаю старый стенд neo4j-security-lab (он занимает те же порты)..."
  docker stop neo4j-security-lab >/dev/null
fi

bash scripts/generate-certificates.sh
docker compose up -d

echo -n "Жду готовности Neo4j"
for _ in $(seq 1 60); do
  status="$(docker inspect --format '{{.State.Health.Status}}' neo4j-lab3 2>/dev/null || true)"
  [[ "$status" == "healthy" ]] && break
  echo -n "."
  sleep 3
done
echo
[[ "$status" == "healthy" ]] || { echo "Neo4j не запустился, см. docker logs neo4j-lab3"; exit 1; }

shell() { MSYS_NO_PATHCONV=1 docker exec -i neo4j-lab3 cypher-shell -a bolt+ssc://localhost:7687 -u neo4j -p 'LabAdmin2026!' "$@"; }

shell -d neo4j  < cypher/01-data.cypher
shell -d system < cypher/02-security.cypher

echo "Готово. Browser: https://localhost:7473  (neo4j+s://localhost:7687, neo4j / LabAdmin2026!)"
