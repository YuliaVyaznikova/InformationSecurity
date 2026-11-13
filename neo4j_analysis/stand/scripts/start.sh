#!/usr/bin/env bash
# Запуск стенда и проверка готовности Neo4j перед демонстрацией требований N 64.
set -uo pipefail
cd "$(dirname "$0")/.."
export MSYS_NO_PATHCONV=1

if ! docker info >/dev/null 2>&1; then
  echo "Docker не отвечает. Запустите Docker Desktop, дождитесь надписи Engine running и повторите команду."
  exit 1
fi

if ! docker ps -a --format '{{.Names}}' | grep -qx neo4j-lab3 && ! docker volume ls -q | grep -qx stand_lab3_data; then
  echo "Стенда на этом компьютере ещё нет, разворачиваю с нуля (около 2 минут)..."
  exec bash scripts/setup.sh
fi

if docker ps --format '{{.Names}}' | grep -qx neo4j-security-lab; then
  echo "Останавливаю старый стенд neo4j-security-lab (он занимает те же порты)..."
  docker stop neo4j-security-lab >/dev/null
fi

echo "Запускаю контейнер neo4j-lab3..."
docker compose up -d || { echo "Контейнер не запустился, подробности: docker logs neo4j-lab3"; exit 1; }

echo -n "Жду готовности Neo4j (обычно 30-60 секунд)"
status=""
for _ in $(seq 1 60); do
  status="$(docker inspect --format '{{.State.Health.Status}}' neo4j-lab3 2>/dev/null || true)"
  [[ "$status" == "healthy" ]] && break
  echo -n "."
  sleep 3
done
echo
[[ "$status" == "healthy" ]] || { echo "Neo4j не запустился за 3 минуты, подробности: docker logs neo4j-lab3"; exit 1; }

n="$(docker exec neo4j-lab3 cypher-shell -a bolt+ssc://localhost:7687 -u analyst -p 'Analyst2026!' \
     --format plain "MATCH (a:Account) RETURN count(a)" 2>/dev/null | tail -1 | tr -d '\r')"
echo "Проверка: пользователь analyst видит счетов: ${n:-?} (должно быть 3)"
echo "Готово. Browser: https://localhost:7473  (neo4j+s://, localhost:7687, neo4j / LabAdmin2026!)"
