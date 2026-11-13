#!/usr/bin/env bash
# Выполнение отдельных Cypher-запросов от имени пользователей с разными ролями N 64.
export MSYS_NO_PATHCONV=1
user="${1:?пользователь}"; query="${2:?запрос}"; db="${3:-neo4j}"; proto="${4:-bolt+ssc}"
case "$user" in
  neo4j)    def="LabAdmin2026!" ;;
  analyst)  def="Analyst2026!" ;;
  support)  def="Support2026!" ;;
  operator) def="Operator2026!" ;;
  auditor)  def="Auditor2026!" ;;
  usermgr)  def="UserMgr2026!" ;;
  *)        def="" ;;
esac
pass="${PASS:-$def}"
docker exec neo4j-lab3 cypher-shell -a "${proto}://localhost:7687" -u "$user" -p "$pass" -d "$db" --format plain "$query"
