#!/usr/bin/env bash
# Полный сброс учебного стенда для повторной демонстрации проверок N 64 с исходного состояния.
set -uo pipefail
cd "$(dirname "$0")/.."
export MSYS_NO_PATHCONV=1

if [[ "${1:-}" != "-y" ]]; then
  read -r -p "Удалить все данные, журналы и резервные копии стенда и создать его заново? (y/n) " answer
  [[ "$answer" == "y" || "$answer" == "Y" || "$answer" == "д" ]] || { echo "Отменено."; exit 0; }
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker не отвечает. Запустите Docker Desktop, дождитесь надписи Engine running и повторите команду."
  exit 1
fi

echo "Удаляю контейнер, данные и журналы..."
docker compose down -v
rm -f backups/*.backup
echo "Разворачиваю стенд заново..."
bash scripts/setup.sh
