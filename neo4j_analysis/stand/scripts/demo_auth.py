import sys
import time

from neo4j import GraphDatabase

import sys as _sys
for _s in (_sys.stdout, _sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Раздел 8 N 64: блокировка после неуспешных попыток входа и управление сеансами.
# Раздел 10 N 64: наполнение журнала безопасности для проверки его ротации.
URI = "bolt+ssc://localhost:7687"
ADMIN = ("neo4j", "LabAdmin2026!")
ANALYST = ("analyst", "Analyst2026!")


def ts():
    return time.strftime("%H:%M:%S")


def try_login(user, password):
    try:
        with GraphDatabase.driver(URI, auth=(user, password)) as drv:
            drv.verify_connectivity()
        return "вход выполнен"
    except Exception as e:
        return "ОТКАЗ: " + str(getattr(e, "message", e)).splitlines()[0][:110]


def lockout():
    for i in range(1, 4):
        print(f"{ts()} попытка {i}, неверный пароль  -> {try_login('analyst', 'WrongPass2026!')}")
    print(f"{ts()} сразу верный пароль      -> {try_login(*ANALYST)}")
    print(f"{ts()} ждём 16 секунд (dbms.security.auth_lock_time = 15s)...")
    time.sleep(16)
    print(f"{ts()} верный пароль через 16 с  -> {try_login(*ANALYST)}")


def sessions():
    drivers = []
    try:
        for _ in range(10):
            d = GraphDatabase.driver(URI, auth=ANALYST)
            d.verify_connectivity()
            drivers.append(d)
        with GraphDatabase.driver(URI, auth=ADMIN) as adm, adm.session(database="system") as s:
            rows = [r for r in s.run("CALL dbms.listConnections() YIELD connectionId, username RETURN connectionId, username")
                    if r["username"] == "analyst"]
        print(f"{ts()} открыто независимых подключений analyst: {len(drivers)}")
        print(f"{ts()} сервер видит соединений пользователя analyst: {len(rows)}")
        print("Ограничения числа параллельных сеансов на пользователя в Neo4j нет (FTA_MCS.1 не реализован).")
    finally:
        for d in drivers:
            d.close()


def flood():
    with GraphDatabase.driver(URI, auth=ANALYST) as drv, drv.session() as s:
        for i in range(450):
            try:
                s.run("MATCH (a:Account {id: 'A-001'}) SET a.balance = 0").consume()
            except Exception:
                pass
    print(f"{ts()} выполнено 450 запрещённых операций; каждая записана в security.log как ERROR")
    print("Проверьте: docker exec neo4j-lab3 ls -l /logs   (появятся security.log.01, .02 ...)")


if __name__ == "__main__":
    actions = {"lockout": lockout, "sessions": sessions, "flood": flood}
    if len(sys.argv) != 2 or sys.argv[1] not in actions:
        print("Использование: python scripts/demo_auth.py lockout|sessions|flood")
        sys.exit(1)
    actions[sys.argv[1]]()
