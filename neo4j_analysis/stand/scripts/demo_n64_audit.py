import subprocess
from pathlib import Path

from neo4j import GraphDatabase


# Раздел 10 N 64: регистрация создания и удаления базы, запуска и идентификаторов запросов.
URI = "bolt+ssc://localhost:7687"
AUTH = ("neo4j", "LabAdmin2026!")
OUT = Path(__file__).resolve().parents[2] / "results" / "n64_audit.txt"


def sh(command):
    result = subprocess.run(
        ["docker", "exec", "neo4j-lab3", "sh", "-c", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


def main():
    lines = []
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        with driver.session(database="system") as session:
            session.run("CREATE DATABASE n64auditprobe WAIT").consume()
            session.run("DROP DATABASE n64auditprobe WAIT").consume()

    lines.append("== События создания и удаления базы данных ==")
    lines.append(sh("grep 'n64auditprobe' /logs/security.log | tail -5"))

    lines.append("\n== Примеры записей security.log ==")
    lines.append(sh("tail -5 /logs/security.log"))

    lines.append("\n== Примеры записей query.log с идентификаторами запросов ==")
    lines.append(sh("grep -E 'id:[0-9]+' /logs/query.log | tail -4"))

    lines.append("\n== Сообщения о запуске Neo4j ==")
    lines.append(sh("grep -E 'Starting|Started|shutdown|Stopping' /logs/neo4j.log | head -12"))

    lines.append("\n== Изменение конфигурации журнала ==")
    lines.append(sh("grep 'db.logs.query.enabled changed' /logs/debug.log | tail -2"))

    lines.append("\n== Ротация журналов ==")
    lines.append(sh("ls -lh /logs/security.log* /logs/query.log* | tail -10"))

    lines.append("\nВывод: security.log содержит дату, время и текст события; уникальный идентификатор есть у записей query.log, но не у каждой записи security.log. Запуск и изменение конфигурации видны в системных/диагностических журналах, а не в едином журнале безопасности.")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
