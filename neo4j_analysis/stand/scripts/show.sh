#!/usr/bin/env bash
# Просмотр журналов безопасности, запросов и избирательного аудита по разделу 10 N 64.
export MSYS_NO_PATHCONV=1
what="${1:-security}"; n="${2:-25}"

brief() {
  docker exec neo4j-lab3 sh -c "grep -v 'Query started' $1 | grep -v \"type: 'system'\" | tail -n $n" \
    | sed -E 's/^([0-9-]+ [0-9:.]+)[^ ]* +([A-Z]+) +.*\t([^\t]+) - ([^ ]+) - (.*) - runtime=[^ ]+ - \{[^}]*\}( - (.*))?$/\1 \2  \4@\3: \5   \7/'
}

case "$what" in
  security) docker exec neo4j-lab3 tail -n "$n" /logs/security.log ;;
  query)    brief /logs/query.log ;;
  analyst)  brief /logs/analyst-audit.log ;;
  raw)      docker exec neo4j-lab3 tail -n "$n" /logs/query.log ;;
  files)    docker exec neo4j-lab3 ls -l /logs ;;
  debug)    docker exec neo4j-lab3 sh -c "grep 'changed to' /logs/debug.log | tail -n $n" ;;
  *)        echo "Использование: bash scripts/show.sh security|query|analyst|raw [N] | files | debug" ;;
esac
