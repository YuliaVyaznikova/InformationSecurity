import concurrent.futures
import csv
import math
import statistics
import threading
import time
from pathlib import Path

from neo4j import GraphDatabase


URI = "bolt+ssc://localhost:7687"
AUTH = ("neo4j", "LabAdmin2026!")
SESSIONS = 10
OPERATIONS_PER_SESSION = 20
RUNS = 20
RESULTS = Path(__file__).resolve().parents[2] / "results"
OUT = RESULTS / "performance.txt"
CSV_OUT = RESULTS / "performance_runs.csv"
# Раздел 14 N 64: 20 прогонов чтения и записи с вычислением 95% доверительного интервала.
READ_QUERY = """
MATCH (p:Person)-[:OWNS]->(a:Account)
OPTIONAL MATCH (a)-[:SENT]->(t:Transaction)
RETURN p.id AS person, a.id AS account, count(t) AS transfers,
       coalesce(sum(t.amount), 0) AS totalAmount
"""
WRITE_QUERY = """
MATCH (source:Account {id: 'A-001'}), (target:Account {id: 'A-002'})
CREATE (source)-[:SENT]->(t:Transaction {id: $id, amount: 10, timestamp: datetime()})
       -[:RECEIVED_BY]->(target)
RETURN t.id AS id
"""


def confidence_interval(values):
    mean = statistics.mean(values)
    if len(values) < 2:
        return mean, 0.0
    half_width = 2.093 * statistics.stdev(values) / math.sqrt(len(values))
    return mean, half_width


def run_batch(kind, run_number):
    barrier = threading.Barrier(SESSIONS)

    def worker(worker_number):
        latencies = []
        with GraphDatabase.driver(URI, auth=AUTH) as driver:
            with driver.session() as session:
                barrier.wait()
                for operation in range(OPERATIONS_PER_SESSION):
                    started = time.perf_counter()
                    if kind == "read":
                        session.run(READ_QUERY).consume()
                    else:
                        transaction_id = f"T-BENCH-{run_number:02d}-{worker_number:02d}-{operation:02d}"
                        session.run(WRITE_QUERY, id=transaction_id).single()["id"]
                    latencies.append((time.perf_counter() - started) * 1000)
        return latencies

    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=SESSIONS) as pool:
        nested = list(pool.map(worker, range(SESSIONS)))
    elapsed = time.perf_counter() - started
    latencies = [value for group in nested for value in group]
    total = SESSIONS * OPERATIONS_PER_SESSION
    return {
        "run": run_number,
        "kind": kind,
        "elapsed_s": elapsed,
        "throughput": total / elapsed,
        "mean_ms": statistics.mean(latencies),
        "median_ms": statistics.median(latencies),
        "p95_ms": sorted(latencies)[int(len(latencies) * 0.95)],
        "max_ms": max(latencies),
    }


def main():
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        with driver.session() as session:
            session.run("MATCH (t:Transaction) WHERE t.id STARTS WITH 'T-BENCH-' DETACH DELETE t").consume()
    records = []
    for run_number in range(1, RUNS + 1):
        for kind in ("read", "write"):
            record = run_batch(kind, run_number)
            records.append(record)
            print(
                f"{kind} run {run_number:02d}: {record['throughput']:.2f} ops/s, "
                f"mean {record['mean_ms']:.3f} ms"
            )

    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        with driver.session() as session:
            session.run("MATCH (t:Transaction) WHERE t.id STARTS WITH 'T-BENCH-' DETACH DELETE t").consume()

    with CSV_OUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)

    lines = [
        "Проверка производительности Neo4j Enterprise 5.26",
        f"Прогонов каждого типа: {RUNS}",
        f"Параллельных сессий: {SESSIONS}",
        f"Операций в прогоне: {SESSIONS * OPERATIONS_PER_SESSION}",
        f"Всего операций чтения: {RUNS * SESSIONS * OPERATIONS_PER_SESSION}",
        f"Всего операций записи: {RUNS * SESSIONS * OPERATIONS_PER_SESSION}",
        "Запрос чтения: MATCH по Person-OWNS-Account, OPTIONAL MATCH по SENT, count и sum",
        "Запись: CREATE Transaction со связями SENT и RECEIVED_BY",
        "Доверительный интервал: 95% по средним значениям 20 прогонов",
        "Экземпляров Neo4j: 1",
    ]
    for kind, label in (("read", "Чтение"), ("write", "Запись")):
        selected = [record for record in records if record["kind"] == kind]
        throughput, throughput_ci = confidence_interval([record["throughput"] for record in selected])
        latency, latency_ci = confidence_interval([record["mean_ms"] for record in selected])
        lines.extend(
            [
                f"{label}: {throughput:.2f} ± {throughput_ci:.2f} операций/с",
                f"{label}, средняя задержка: {latency:.3f} ± {latency_ci:.3f} мс",
            ]
        )
    RESULTS.mkdir(exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n" + "\n".join(lines))


if __name__ == "__main__":
    main()
