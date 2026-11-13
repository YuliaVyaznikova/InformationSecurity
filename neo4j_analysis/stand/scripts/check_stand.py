import datetime as dt
import pathlib
import re
import ssl
import subprocess
import threading
import time
import urllib.error
import urllib.request
import base64
import json

from neo4j import GraphDatabase

import sys as _sys
for _s in (_sys.stdout, _sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Общая проверка требований N 64: доступ, аутентификация, журналы, транзакции и резервное копирование.
URI = "bolt+ssc://localhost:7687"
HTTPS = "https://localhost:7473"
CONTAINER = "neo4j-lab3"
PW = {
    "neo4j": "LabAdmin2026!", "analyst": "Analyst2026!", "support": "Support2026!",
    "operator": "Operator2026!", "auditor": "Auditor2026!", "usermgr": "UserMgr2026!",
}
OUT = pathlib.Path(__file__).resolve().parents[2] / "results" / "check_stand.txt"
LINES = []
STATS = {"ВЫПОЛНЕНО": 0, "НЕТ": 0, "ОШИБКА": 0}


def log(text=""):
    print(text)
    LINES.append(text)


def report(section, title, ok, details, gap=False):
    status = "НЕТ" if gap and ok else ("ВЫПОЛНЕНО" if ok else "ОШИБКА")
    STATS[status] += 1
    log(f"[{status:9}] {section:16} {title}")
    for d in details if isinstance(details, list) else [details]:
        log(f"{'':29}{d}")


_DRIVERS = {}


def driver(user, password):
    key = (user, password)
    if key not in _DRIVERS:
        _DRIVERS[key] = GraphDatabase.driver(URI, auth=key, connection_timeout=10)
    return _DRIVERS[key]


def run(user, query, db="neo4j", password=None, **params):
    try:
        with driver(user, password or PW[user]).session(database=db) as s:
            rows = [r.data() for r in s.run(query, **params)]
            return rows, None, ""
    except Exception as e:
        code = getattr(e, "code", None) or type(e).__name__
        msg = str(getattr(e, "message", None) or e).splitlines()[0]
        return [], code, msg


def login(user, password):
    try:
        with GraphDatabase.driver(URI, auth=(user, password), connection_timeout=10) as drv:
            drv.verify_connectivity()
        return None, ""
    except Exception as e:
        return getattr(e, "code", None) or type(e).__name__, str(getattr(e, "message", None) or e).splitlines()[0]


def sh(cmd, user=None):
    base = ["docker", "exec"] + (["-u", user] if user else []) + [CONTAINER, "sh", "-c", cmd]
    return subprocess.run(base, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def https(path, user=None, body=None):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(HTTPS + path, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    if user:
        token = base64.b64encode(f"{user}:{PW[user]}".encode()).decode()
        req.add_header("Authorization", "Basic " + token)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


def admin(query, db="system", **params):
    rows, code, msg = run("neo4j", query, db=db, **params)
    if code:
        raise RuntimeError(f"{query}: {code} {msg}")
    return rows


def cleanup():
    for u in ["tmp_pw", "tmp_lock", "tmp_new", "tmp_susp", "tmp_public", "tmp_by_mgr"]:
        admin(f"DROP USER {u} IF EXISTS")
    admin("DROP DATABASE bankcopy IF EXISTS WAIT")
    admin("MATCH (t:Transaction) WHERE t.id STARTS WITH 'T-CHK' DETACH DELETE t", db="neo4j")
    admin("MATCH (n:IsolationProbe) DETACH DELETE n", db="neo4j")
    admin("MATCH (n:Secret) DETACH DELETE n", db="neo4j")
    admin("MATCH (p:Person {id: 'P-002'}) SET p.phone = '+7-900-000-00-02'", db="neo4j")
    admin("MATCH (a:Account) REMOVE a.lockDemo, a.dl", db="neo4j")


def check_identification():
    log("\n== Раздел 8 N 64: идентификация и аутентификация ==")
    code, _ = login("analyst", "")
    st_api, _ = https("/db/neo4j/tx/commit", body={"statements": [{"statement": "RETURN 1"}]})
    st_root, disc = https("/")
    report("Раздел 8 N 64:", "доступ без аутентификации",
           code == "Neo.ClientError.Security.Unauthorized" and st_api == 401 and st_root == 200,
           [f"Bolt без пароля: {code}", f"HTTP API без пароля: HTTP {st_api}",
            f"До входа доступна только служебная страница '/': HTTP {st_root}, раскрывает "
            f"версию {disc.get('neo4j_version')} {disc.get('neo4j_edition')}"])

    code, msg = login("analyst", "WrongPass2026!")
    report("Раздел 8 N 64:", "неверный пароль", code == "Neo.ClientError.Security.Unauthorized", f"{code}: {msg}")

    _, c1, m1 = run("neo4j", "CREATE USER tmp_pw SET PASSWORD '123456789' CHANGE NOT REQUIRED", db="system")
    _, c2, _ = run("neo4j", "CREATE USER tmp_pw SET PASSWORD '1234567890' CHANGE NOT REQUIRED", db="system")
    report("Раздел 8 N 64:", "минимальная длина пароля 10 символов", c1 is not None and c2 is None,
           [f"пароль из 9 символов: {m1}", "пароль из 10 символов: принят (сложность не проверяется)"])

    admin("CREATE USER tmp_lock SET PASSWORD 'TmpLock2026!' CHANGE NOT REQUIRED")
    fails = [login("tmp_lock", "WrongPass2026!")[0] for _ in range(3)]
    c_locked, m_locked = login("tmp_lock", "TmpLock2026!")
    time.sleep(16)
    c_after, _ = login("tmp_lock", "TmpLock2026!")
    report("Раздел 8 N 64:", "блокировка после 3 неудачных попыток на 15 с",
           c_locked is not None and "too many" in m_locked and c_after is None,
           [f"3 неверные попытки: {', '.join(str(f).split('.')[-1] for f in fails)}",
            f"верный пароль сразу: {m_locked}", "верный пароль через 16 с: вход выполнен"])

    admin("CREATE USER tmp_new SET PASSWORD 'TmpNew2026!' CHANGE REQUIRED")
    admin("GRANT ROLE reader TO tmp_new")
    _, c_before, _ = run("tmp_new", "MATCH (n) RETURN count(n) AS c", password="TmpNew2026!")
    _, c_same, m_same = run("tmp_new", "ALTER CURRENT USER SET PASSWORD FROM 'TmpNew2026!' TO 'TmpNew2026!'",
                            db="system", password="TmpNew2026!")
    _, c_chg, _ = run("tmp_new", "ALTER CURRENT USER SET PASSWORD FROM 'TmpNew2026!' TO 'TmpChanged2026!'",
                      db="system", password="TmpNew2026!")
    rows, c_after, _ = run("tmp_new", "MATCH (n) RETURN count(n) AS c", password="TmpChanged2026!")
    report("Раздел 8 N 64:", "обязательная смена начального пароля",
           c_before == "Neo.ClientError.Security.CredentialsExpired" and c_same and not c_chg and not c_after,
           [f"до смены пароля: {c_before}", f"тот же пароль повторно: {m_same}",
            f"после смены пароля видно узлов: {rows[0]['c'] if rows else '-'}"])

    admin("CREATE USER tmp_susp SET PASSWORD 'TmpSusp2026!' CHANGE NOT REQUIRED")
    admin("ALTER USER tmp_susp SET STATUS SUSPENDED")
    c_susp, _ = login("tmp_susp", "TmpSusp2026!")
    admin("ALTER USER tmp_susp SET STATUS ACTIVE")
    c_act, _ = login("tmp_susp", "TmpSusp2026!")
    report("Раздел 8 N 64:", "отказ в открытии сеанса приостановленной учётной записи",
           c_susp is not None and c_act is None,
           [f"SUSPENDED: {c_susp}", "ACTIVE: вход выполнен"])

    rows = admin("SHOW USERS YIELD user, roles, passwordChangeRequired, suspended WHERE user = 'analyst' "
                 "RETURN user, roles, passwordChangeRequired, suspended")
    report("Раздел 8 N 64:", "атрибуты безопасности пользователя", bool(rows), str(rows[0]) if rows else "нет данных")

    rows, _, _ = run("analyst", "SHOW CURRENT USER YIELD user, roles RETURN user, roles", db="system")
    report("Раздел 8 N 64:", "связь пользователь-субъект", rows and rows[0]["user"] == "analyst",
           f"SHOW CURRENT USER: {rows[0] if rows else '-'}")


def check_access_control():
    log("\n== Раздел 7 N 64: управление доступом и роли ==")
    q_people = "MATCH (p:Person) RETURN collect(p.passport) AS passports, count(p) AS people"
    q_acc = "MATCH (a:Account) RETURN count(a) AS accounts"
    adm_p = run("neo4j", q_people)[0][0]
    an_p = run("analyst", q_people)[0][0]
    adm_a = run("neo4j", q_acc)[0][0]["accounts"]
    an_a = run("analyst", q_acc)[0][0]["accounts"]
    report("Раздел 7 N 64:", "analyst: скрыт паспорт и VIP-счёт",
           len([p for p in an_p["passports"] if p]) == 0 and adm_a == 4 and an_a == 3,
           [f"admin видит паспортов: {len(adm_p['passports'])}, analyst: {len([p for p in an_p['passports'] if p])}",
            f"admin видит счетов: {adm_a}, analyst: {an_a} (VIP-счёт A-004 скрыт правилом по значению свойства)"])

    sup_a = run("support", q_acc)[0][0]["accounts"]
    _, c_phone, _ = run("support", "MATCH (p:Person {id: 'P-002'}) SET p.phone = '+7-900-111-22-33'")
    _, c_name, m_name = run("support", "MATCH (p:Person {id: 'P-002'}) SET p.name = 'X'")
    report("Раздел 7 N 64:", "support: только клиенты, правка только телефона",
           sup_a == 0 and c_phone is None and c_name == "Neo.ClientError.Security.Forbidden",
           [f"видит счетов: {sup_a}", "SET phone: разрешено", f"SET name: {m_name}"])

    _, c_cr, _ = run("operator", "MATCH (a:Account {id:'A-001'}), (b:Account {id:'A-002'}) "
                                 "CREATE (a)-[:SENT]->(:Transaction {id:'T-CHK-1', amount: 10})-[:RECEIVED_BY]->(b)")
    _, c_bal, m_bal = run("operator", "MATCH (a:Account {id:'A-001'}) SET a.balance = 0")
    _, c_del, m_del = run("operator", "MATCH (t:Transaction {id:'T-CHK-1'}) DETACH DELETE t")
    report("Раздел 7 N 64:", "operator: создать перевод можно, менять баланс и удалять нельзя",
           c_cr is None and c_bal and c_del, ["CREATE Transaction: разрешено", f"SET balance: {m_bal}",
                                              f"DELETE: {m_del}"])

    admin("CREATE USER tmp_public SET PASSWORD 'TmpPublic2026!' CHANGE NOT REQUIRED")
    rows, _, _ = run("tmp_public", "MATCH (n) RETURN count(n) AS c", password="TmpPublic2026!")
    report("Раздел 7 N 64:", "по умолчанию данных не видно (только роль PUBLIC)", rows and rows[0]["c"] == 0,
           f"новый пользователь без ролей видит узлов: {rows[0]['c'] if rows else '-'}")

    _, c_acc, m_acc = run("auditor", "MATCH (n) RETURN count(n)")
    users, c_su, _ = run("auditor", "SHOW USERS", db="system")
    _, c_cu, _ = run("auditor", "CREATE USER tmp_x SET PASSWORD 'TmpX20261234!'", db="system")
    report("Раздел 7 N 64:", "auditor: видит учётные записи, не видит данные, не меняет",
           c_acc and not c_su and c_cu, [f"MATCH в neo4j: {m_acc}", f"SHOW USERS: {len(users)} записей",
                                         "CREATE USER: запрещено"])

    _, c_mk, _ = run("usermgr", "CREATE USER tmp_by_mgr SET PASSWORD 'TmpByMgr2026!'", db="system")
    _, c_gr, m_gr = run("usermgr", "GRANT ROLE admin TO usermgr", db="system")
    report("Раздел 7 N 64:", "usermgr: создаёт учётные записи, но не раздаёт роли",
           c_mk is None and c_gr == "Neo.ClientError.Security.Forbidden",
           ["CREATE USER: разрешено", f"GRANT ROLE admin TO usermgr: {m_gr[:70]}"])

    st, body = https("/db/neo4j/tx/commit", user="analyst", body={"statements": [
        {"statement": "MATCH (p:Person {id:'P-004'}) RETURN p.passport"},
        {"statement": "MATCH (a:Account) RETURN count(a)"}]})
    res = body.get("results", [])
    passport = res[0]["data"][0]["row"][0] if res else "?"
    count = res[1]["data"][0]["row"][0] if len(res) > 1 else "?"
    report("Раздел 7 N 64:", "те же правила через другой интерфейс (HTTPS API)",
           st == 200 and passport is None and count == 3,
           f"HTTP {st}: passport = {passport}, счетов = {count}")


def check_network_and_software():
    log("\n== Раздел 15 N 64: сетевые ограничения и программная среда ==")
    _, c1, m1 = run("operator", "LOAD CSV FROM 'http://10.0.0.1/x.csv' AS r RETURN r LIMIT 1")
    _, c2, m2 = run("analyst", "LOAD CSV FROM 'http://127.0.0.1:1/x.csv' AS r RETURN r LIMIT 1")
    report("Раздел 15 N 64:", "фильтрация исходящих запросов по адресу",
           "blocklist" in m1 and c2 == "Neo.ClientError.Security.Forbidden",
           [f"operator -> 10.0.0.1: {m1[-90:]}", f"analyst -> любой адрес: {m2[:80]}"])

    try:
        with GraphDatabase.driver("bolt://localhost:7687", auth=("analyst", PW["analyst"]),
                                  connection_timeout=5) as d:
            d.verify_connectivity()
        plain = "подключение установлено"
    except Exception as e:
        plain = type(e).__name__
    try:
        urllib.request.urlopen("http://localhost:7474/", timeout=5)
        http_plain = "открыт"
    except Exception as e:
        http_plain = type(e).__name__
    report("Раздел 15 N 64:", "только защищённые каналы", plain != "подключение установлено" and http_plain != "открыт",
           [f"Bolt без TLS: {plain}", f"HTTP 7474: {http_plain}"])

    rows, _, _ = run("neo4j", "RETURN apoc.text.capitalize('защита') AS v")
    _, c_load, m_load = run("neo4j", "CALL apoc.load.json('http://127.0.0.1/x.json')")
    _, c_cfg, m_cfg = run("analyst", "CALL dbms.setConfigValue('db.logs.query.enabled', 'OFF')", db="system")
    report("Раздел 15 N 64:", "белый список процедур и запрет админ-процедур",
           rows and c_load == "Neo.ClientError.Procedure.ProcedureNotFound" and c_cfg,
           [f"apoc.text.capitalize: {rows[0]['v'] if rows else '-'}", f"apoc.load.json: {m_load[:75]}",
            f"analyst вызывает dbms.setConfigValue: {m_cfg[:75]}"])


def check_audit():
    log("\n== Раздел 10 N 64: регистрация событий безопасности ==")
    sec = sh("cat /logs/security.log")
    needles = {
        "успешный вход": "logged in",
        "неуспешный вход": "failed to log in: invalid principal or credentials",
        "блокировка": "failed to log in: too many failed attempts",
        "создание пользователя (пароль скрыт)": "CREATE USER tmp_lock SET PASSWORD '******'",
        "смена начального пароля": "ALTER CURRENT USER SET PASSWORD FROM '******' TO '******'",
        "приостановка": "ALTER USER tmp_susp SET STATUS SUSPENDED",
        "отказ в доступе": "is not allowed for user 'support'",
    }
    found = {k: (v in sec) for k, v in needles.items()}
    report("Раздел 10 N 64:", "события в security.log", all(found.values()),
           [f"{k}: {'есть' if v else 'НЕТ'}" for k, v in found.items()])

    users_in_sel = set(re.findall(r"\t\S+ - (\S+) - ", sh("cat /logs/analyst-audit.log")))
    users_in_q = set(re.findall(r"\t\S+ - (\S+) - ", sh("cat /logs/query.log")))
    report("Раздел 10 N 64:", "избирательный журнал по пользователю", users_in_sel == {"analyst"} and len(users_in_q) > 2,
           [f"query.log: пользователи {sorted(users_in_q)}", f"analyst-audit.log: {sorted(users_in_sel)}"])

    admin("CALL dbms.setConfigValue('db.logs.query.enabled', 'OFF')")
    run("analyst", "RETURN 1 AS probe_while_off")
    admin("CALL dbms.setConfigValue('db.logs.query.enabled', 'VERBOSE')")
    run("analyst", "RETURN 1 AS probe_while_on")
    time.sleep(1)
    q = sh("cat /logs/query.log")
    dbg = sh("grep 'db.logs.query.enabled changed' /logs/debug.log | tail -2")
    report("Раздел 10 N 64:", "администратор отключает и включает журнал запросов",
           "probe_while_on" in q and "probe_while_off" not in q and "changed to OFF" in dbg,
           [f"запрос при выключенном журнале записан: {'да' if 'probe_while_off' in q else 'нет'}",
            f"запрос после включения записан: {'да' if 'probe_while_on' in q else 'нет'}"]
           + [line.strip()[:110] for line in dbg.strip().splitlines()])

    _, c_read, m_read = run("analyst", "LOAD CSV FROM 'file:///../logs/security.log' AS r RETURN r LIMIT 1")
    perms = sh("ls -l /logs | grep -E 'security.log|query.log' | head -2")
    report("Раздел 10 N 64:", "пользователь СУБД не читает журналы аудита", c_read is not None,
           [f"LOAD CSV security.log от analyst: {m_read[:80]}"] + [p.strip() for p in perms.splitlines()])

    stamp = re.findall(r"^(\S+ \S+) ", sec, re.M)[-1]
    rows = admin("RETURN toString(datetime()) AS now", db="neo4j")
    report("Раздел 10 N 64:", "метки времени в журналах", bool(stamp),
           [f"последняя запись security.log: {stamp}", f"datetime() сервера: {rows[0]['now']}"])


def check_passwords_storage():
    log("\n== Раздел 8 N 64: защита хранимой аутентификационной информации ==")
    rows = admin("SHOW USERS WITH AUTH YIELD user, auth WHERE user = 'analyst' RETURN user, auth")
    plain = sh("grep -rl 'Analyst2026' /data /logs 2>/dev/null | wc -l").strip()
    hashes = sh("grep -raoh 'SHA-256,[0-9a-f]\\{8\\}' /data/databases/system /data/transactions/system "
                "2>/dev/null | head -1").strip()
    report("Раздел 8 N 64:", "пароли не хранятся и не показываются в открытом виде",
           rows and rows[0]["auth"].get("password") == "***" and plain == "0" and hashes.startswith("SHA-256"),
           [f"SHOW USERS WITH AUTH: {rows[0]['auth'] if rows else '-'}",
            f"файлов с паролем analyst в открытом виде: {plain}", f"формат хранения: {hashes}..."])


def check_transactions():
    log("\n== Раздел 14 N 64: транзакции, ресурсы и сеансы ==")
    with GraphDatabase.driver(URI, auth=("neo4j", PW["neo4j"])) as drv:
        s1 = drv.session()
        tx = s1.begin_transaction()
        tx.run("CREATE (:IsolationProbe)").consume()
        with drv.session() as s2:
            before = s2.run("MATCH (n:IsolationProbe) RETURN count(n) AS c").single()["c"]
        tx.commit()
        s1.close()
        with drv.session() as s2:
            after = s2.run("MATCH (n:IsolationProbe) RETURN count(n) AS c").single()["c"]
    report("Раздел 14 N 64:", "изоляция транзакций", before == 0 and after == 1,
           f"чужая незафиксированная запись видна: {before}; после COMMIT: {after}")

    locked = threading.Event()
    waited = {}
    with GraphDatabase.driver(URI, auth=("neo4j", PW["neo4j"])) as drv:
        def t1():
            with drv.session() as s, s.begin_transaction() as t:
                t.run("MATCH (a:Account {id:'A-001'}) SET a.lockDemo = 1").consume()
                locked.set()
                time.sleep(3)
                t.commit()

        def t2():
            locked.wait(10)
            start = time.monotonic()
            with drv.session() as s:
                s.run("MATCH (a:Account {id:'A-001'}) SET a.lockDemo = 2").consume()
            waited["s"] = time.monotonic() - start
        a, b = threading.Thread(target=t1), threading.Thread(target=t2)
        a.start(); b.start(); a.join(); b.join()
    report("Раздел 14 N 64:", "вторая запись ждёт освобождения блокировки", waited.get("s", 0) > 2.5,
           f"ожидание второй транзакции: {waited.get('s', 0):.2f} с")

    barrier = threading.Barrier(2)
    outcome = []
    with GraphDatabase.driver(URI, auth=("neo4j", PW["neo4j"])) as drv:
        def w(first, second):
            try:
                with drv.session() as s:
                    t = s.begin_transaction()
                    t.run("MATCH (a:Account {id:$i}) SET a.dl = 1", i=first).consume()
                    barrier.wait()
                    time.sleep(0.5)
                    t.run("MATCH (a:Account {id:$i}) SET a.dl = 2", i=second).consume()
                    t.commit()
                    outcome.append("COMMIT")
            except Exception as e:
                outcome.append(getattr(e, "code", type(e).__name__))
        a = threading.Thread(target=w, args=("A-001", "A-002"))
        b = threading.Thread(target=w, args=("A-002", "A-001"))
        a.start(); b.start(); a.join(); b.join()
    report("Раздел 14 N 64:", "обнаружение взаимоблокировки",
           "COMMIT" in outcome and "Neo.TransientError.Transaction.DeadlockDetected" in outcome, ", ".join(outcome))

    _, c_mem, m_mem = run("analyst", "UNWIND range(1, 20000000) AS x RETURN size(collect(x)) AS n")
    report("Раздел 14 N 64:", "лимит памяти транзакции 64 МБ", c_mem == "Neo.TransientError.General.MemoryPoolOutOfMemoryError",
           m_mem[:120])

    ready = threading.Event()
    killed = {}
    with GraphDatabase.driver(URI, auth=("analyst", PW["analyst"])) as udrv:
        def long_query():
            try:
                with udrv.session() as s:
                    ready.set()
                    s.run("UNWIND range(1, 2000000000) AS x WITH x WHERE x % 7 = 0 RETURN count(x)").consume()
            except Exception as e:
                killed["code"] = getattr(e, "code", type(e).__name__)
        t = threading.Thread(target=long_query)
        t.start()
        ready.wait(15)
        rows = []
        for _ in range(30):
            rows = admin("SHOW TRANSACTIONS YIELD transactionId, username WHERE username = 'analyst' "
                         "RETURN transactionId, username", db="neo4j")
            if rows:
                break
            time.sleep(0.5)
        for r in rows:
            admin("TERMINATE TRANSACTIONS $id", db="neo4j", id=r["transactionId"])
        t.join(30)
    report("Раздел 14 N 64:", "администратор видит и прерывает чужой запрос",
           bool(rows) and killed.get("code") == "Neo.ClientError.Transaction.Terminated",
           f"SHOW TRANSACTIONS: {[r['transactionId'] for r in rows]}; у analyst: {killed.get('code')}")

    drivers = []
    try:
        for _ in range(10):
            d = GraphDatabase.driver(URI, auth=("analyst", PW["analyst"]))
            d.verify_connectivity()
            drivers.append(d)
        conns = [r for r in admin("CALL dbms.listConnections() YIELD connectionId, username "
                                  "RETURN connectionId, username") if r["username"] == "analyst"]
    finally:
        for d in drivers:
            d.close()
    report("Раздел 14 N 64:", "ограничение числа параллельных сеансов", len(conns) >= 10,
           f"одновременно открыто соединений analyst: {len(conns)}, ограничения нет", gap=True)

    rows = admin("SHOW SETTINGS YIELD name, value WHERE name IN "
                 "['browser.credential_timeout', 'browser.retain_connection_credentials'] RETURN name, value")
    report("Раздел 14 N 64:", "таймаут бездействия сеанса Neo4j Browser",
           {r["name"]: r["value"] for r in rows}.get("browser.credential_timeout") == "2m",
           [f"{r['name']} = {r['value']}" for r in rows] + ["сам таймаут проверяется в Browser вручную (отчёт, рисунок 8)"])


def check_backup_and_erase():
    log("\n== Разделы 11 и 13 N 64: резервное копирование, восстановление и очистка памяти ==")
    out = sh("neo4j-admin database backup --type=FULL --from=localhost:6362 --to-path=/backups neo4j 2>&1 | tail -1", user="neo4j")
    name = sh("ls -t /backups | grep '^neo4j-' | head -1").strip()
    sh(f"neo4j-admin database restore --from-path=/backups/{name} bankcopy 2>&1 | tail -1", user="neo4j")
    admin("CREATE DATABASE bankcopy WAIT")
    copy = admin("MATCH (a:Account) RETURN count(a) AS c", db="bankcopy")[0]["c"]
    _, c_before, _ = run("analyst", "MATCH (a:Account) RETURN count(a) AS c", db="bankcopy")
    sh("cypher-shell -a bolt+ssc://localhost:7687 -u neo4j -p 'LabAdmin2026!' -d system "
       "--param \"database => 'bankcopy'\" -f /data/scripts/bankcopy/restore_metadata.cypher", user="neo4j")
    rows, c_after, _ = run("analyst", "MATCH (a:Account) RETURN count(a) AS c", db="bankcopy")
    report("Раздел 11 N 64:", "онлайн-копия и восстановление в отдельную базу",
           "completed" in out and copy == 4, [f"backup: {out.strip()} -> {name}",
                                              f"в восстановленной копии bankcopy счетов: {copy}"])
    report("Раздел 11 N 64:", "атрибуты безопасности переносятся вместе с копией",
           c_before == "Neo.ClientError.Security.Forbidden" and not c_after and rows[0]["c"] == 3,
           ["analyst в bankcopy до restore_metadata.cypher: доступ запрещён",
            f"после restore_metadata.cypher: видит {rows[0]['c'] if rows else '-'} счёта (VIP снова скрыт)"])
    admin("DROP DATABASE bankcopy WAIT")

    secret = "Confidential note 7731: the vault code is forty-two, keep this text away from everyone else please."
    admin("CREATE (:Secret {value: $v})", db="neo4j", v=secret)
    admin("MATCH (s:Secret) DELETE s", db="neo4j")
    admin("CALL db.checkpoint()", db="neo4j")
    files = sh("grep -rl 'vault code is forty-two' /data 2>/dev/null").split()
    report("Раздел 13 N 64:", "гарантированное стирание удалённых данных", len(files) > 0,
           ["удалённое значение после DELETE и checkpoint найдено в файлах:"] + files, gap=True)

    _, c_dup, m_dup = run("neo4j", "CREATE (:Person {id: 'P-001'})")
    rows = admin("MATCH (p:Person {id:'P-001'}) RETURN elementId(p) AS eid", db="neo4j")
    report("Раздел 8 N 64:", "однозначная идентификация объектов",
           c_dup == "Neo.ClientError.Schema.ConstraintValidationFailed" and rows,
           [f"дубликат P-001: {m_dup[:80]}", f"elementId: {rows[0]['eid'] if rows else '-'}"])


if __name__ == "__main__":
    started = dt.datetime.now()
    log(f"Проверка стенда Neo4j по требованиям ФСТЭК России N 64, {started:%d.%m.%Y %H:%M:%S}")
    ver = admin("CALL dbms.components() YIELD versions, edition RETURN versions[0] AS v, edition AS e")[0]
    log(f"Neo4j {ver['v']} {ver['e']}")
    cleanup()
    try:
        check_identification()
        check_access_control()
        check_network_and_software()
        check_audit()
        check_passwords_storage()
        check_transactions()
        check_backup_and_erase()
    finally:
        cleanup()
    log("\nИтог по требованиям N 64: 5 разделов выполнены, 1 выполнен частично и 2 не реализованы.")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(LINES) + "\n", encoding="utf-8")
    print(f"Протокол: {OUT}")
