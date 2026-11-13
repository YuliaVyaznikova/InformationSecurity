import sys
import threading
import time

from neo4j import GraphDatabase

import sys as _sys
for _s in (_sys.stdout, _sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Раздел 14 N 64: изоляция и блокировки транзакций, взаимоблокировка, память и прерывание запросов.
URI = "bolt+ssc://localhost:7687"
ADMIN = ("neo4j", "LabAdmin2026!")
OPERATOR = ("operator", "Operator2026!")
ANALYST = ("analyst", "Analyst2026!")


def ts():
    return time.strftime("%H:%M:%S")


def isolation():
    with GraphDatabase.driver(URI, auth=ADMIN) as drv:
        with drv.session() as s:
            s.run("MATCH (n:IsolationProbe) DETACH DELETE n").consume()
        writer = drv.session()
        tx = writer.begin_transaction()
        tx.run("CREATE (:IsolationProbe {note: 'ещё не зафиксировано'})").consume()
        print(f"{ts()} T1: создала узел IsolationProbe, транзакция НЕ зафиксирована")
        with drv.session() as reader:
            n = reader.run("MATCH (n:IsolationProbe) RETURN count(n) AS c").single()["c"]
        print(f"{ts()} T2: видит узлов IsolationProbe: {n}   <- чужие незафиксированные изменения не видны")
        tx.commit()
        writer.close()
        print(f"{ts()} T1: COMMIT")
        with drv.session() as reader:
            n = reader.run("MATCH (n:IsolationProbe) RETURN count(n) AS c").single()["c"]
        print(f"{ts()} T2: видит узлов IsolationProbe: {n}   <- после фиксации изменения видны")
        tx2 = drv.session().begin_transaction()
        tx2.run("MATCH (n:IsolationProbe) DETACH DELETE n").consume()
        tx2.rollback()
        with drv.session() as reader:
            n = reader.run("MATCH (n:IsolationProbe) RETURN count(n) AS c").single()["c"]
        print(f"{ts()} T3: удалила узел и сделала ROLLBACK, узлов осталось: {n}   <- откат отменяет изменения")
        with drv.session() as s:
            s.run("MATCH (n:IsolationProbe) DETACH DELETE n").consume()


def lock():
    locked = threading.Event()
    with GraphDatabase.driver(URI, auth=ADMIN) as drv:
        def t1():
            with drv.session() as s, s.begin_transaction() as tx:
                tx.run("MATCH (a:Account {id: 'A-001'}) SET a.lockDemo = 1").consume()
                print(f"{ts()} T1: изменила счёт A-001 и держит блокировку 3 секунды")
                locked.set()
                time.sleep(3)
                tx.commit()
            print(f"{ts()} T1: COMMIT, блокировка снята")

        def t2():
            locked.wait(10)
            start = time.monotonic()
            print(f"{ts()} T2: пытается изменить тот же счёт A-001")
            with drv.session() as s, s.begin_transaction() as tx:
                tx.run("MATCH (a:Account {id: 'A-001'}) SET a.lockDemo = 2").consume()
                tx.commit()
            print(f"{ts()} T2: COMMIT после ожидания {time.monotonic() - start:.2f} с")

        a, b = threading.Thread(target=t1), threading.Thread(target=t2)
        a.start(); b.start(); a.join(); b.join()
        with drv.session() as s:
            v = s.run("MATCH (a:Account {id: 'A-001'}) RETURN a.lockDemo AS v").single()["v"]
            s.run("MATCH (a:Account) REMOVE a.lockDemo").consume()
        print(f"{ts()} Итог: lockDemo = {v} (обе записи применены по очереди, потерянного обновления нет)")


def deadlock():
    barrier = threading.Barrier(2)
    with GraphDatabase.driver(URI, auth=ADMIN) as drv:
        def worker(name, first, second):
            try:
                with drv.session() as s:
                    tx = s.begin_transaction()
                    tx.run("MATCH (a:Account {id: $id}) SET a.dl = $who", id=first, who=name).consume()
                    print(f"{ts()} {name}: заблокировала {first}")
                    barrier.wait()
                    time.sleep(0.5)
                    print(f"{ts()} {name}: пытается заблокировать {second}")
                    tx.run("MATCH (a:Account {id: $id}) SET a.dl = $who", id=second, who=name).consume()
                    tx.commit()
                    print(f"{ts()} {name}: COMMIT")
            except Exception as e:
                code = getattr(e, "code", type(e).__name__)
                print(f"{ts()} {name}: ОТКАТ, {code}")

        a = threading.Thread(target=worker, args=("T1", "A-001", "A-002"))
        b = threading.Thread(target=worker, args=("T2", "A-002", "A-001"))
        a.start(); b.start(); a.join(); b.join()
        with drv.session() as s:
            s.run("MATCH (a:Account) REMOVE a.dl").consume()


def kill():
    ready = threading.Event()
    with GraphDatabase.driver(URI, auth=ANALYST) as user_drv, GraphDatabase.driver(URI, auth=ADMIN) as adm:
        def long_query():
            try:
                with user_drv.session() as s:
                    ready.set()
                    s.run("UNWIND range(1, 2000000000) AS x WITH x WHERE x % 7 = 0 RETURN count(x)").consume()
                print(f"{ts()} analyst: запрос завершился сам")
            except Exception as e:
                print(f"{ts()} analyst: запрос прерван -> {getattr(e, 'code', type(e).__name__)}")

        t = threading.Thread(target=long_query)
        t.start()
        ready.wait(15)
        with adm.session(database="neo4j") as s:
            rows = []
            for _ in range(30):
                rows = list(s.run(
                    "SHOW TRANSACTIONS YIELD transactionId, username, elapsedTime, currentQuery "
                    "WHERE username = 'analyst' RETURN transactionId, username, elapsedTime, currentQuery"))
                if rows:
                    break
                time.sleep(0.5)
            time.sleep(1)
            for r in rows:
                print(f"{ts()} admin: SHOW TRANSACTIONS -> {r['transactionId']} {r['username']} {r['elapsedTime']} "
                      f"{r['currentQuery'][:50]}...")
            for r in rows:
                res = s.run("TERMINATE TRANSACTIONS $id", id=r["transactionId"]).single()
                print(f"{ts()} admin: TERMINATE TRANSACTIONS {r['transactionId']} -> {res['message']}")
        t.join()
        with adm.session(database="system") as s:
            conns = [c for c in s.run("CALL dbms.listConnections() YIELD connectionId, username, clientAddress "
                                      "RETURN connectionId, username, clientAddress") if c["username"] == "analyst"]
            for c in conns:
                print(f"{ts()} admin: соединение {c['connectionId']} пользователя {c['username']} с {c['clientAddress']}")
            for c in conns:
                r = s.run("CALL dbms.killConnection($id)", id=c["connectionId"]).single()
                print(f"{ts()} admin: dbms.killConnection({c['connectionId']}) -> {r['message']}")


def memory():
    with GraphDatabase.driver(URI, auth=ANALYST) as drv, drv.session() as s:
        try:
            s.run("UNWIND range(1, 20000000) AS x RETURN size(collect(x)) AS n").single()
            print("Запрос выполнился (лимит не сработал)")
        except Exception as e:
            print(f"{ts()} analyst: {getattr(e, 'code', type(e).__name__)}")
            print("   " + str(getattr(e, "message", e)).splitlines()[0][:220])


if __name__ == "__main__":
    actions = {"isolation": isolation, "lock": lock, "deadlock": deadlock, "kill": kill, "memory": memory}
    if len(sys.argv) != 2 or sys.argv[1] not in actions:
        print("Использование: python scripts/demo_transactions.py isolation|lock|deadlock|kill|memory")
        sys.exit(1)
    actions[sys.argv[1]]()
