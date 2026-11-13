// Схема тестовой базы для проверок N 64: клиенты, счета, переводы и ограничения уникальности.
CREATE CONSTRAINT person_id_unique IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT account_id_unique IF NOT EXISTS FOR (a:Account) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT transaction_id_unique IF NOT EXISTS FOR (t:Transaction) REQUIRE t.id IS UNIQUE;

// Вымышленные клиенты с паспортными данными для проверки скрытия отдельных свойств.
MERGE (p:Person {id: 'P-001'}) SET p.name = 'Анна Смирнова',  p.phone = '+7-900-000-00-01', p.email = 'anna@example.test',  p.passport = '5001 100001';
MERGE (p:Person {id: 'P-002'}) SET p.name = 'Борис Котов',    p.phone = '+7-900-000-00-02', p.email = 'boris@example.test', p.passport = '5002 200002';
MERGE (p:Person {id: 'P-003'}) SET p.name = 'Вера Ильина',    p.phone = '+7-900-000-00-03', p.email = 'vera@example.test',  p.passport = '5003 300003';
MERGE (p:Person {id: 'P-004'}) SET p.name = 'Глеб Орлов',     p.phone = '+7-900-000-00-04', p.email = 'gleb@example.test',  p.passport = '5004 400004';

// Обычные счета и один VIP-счёт для проверки ограничения по значению свойства level.
MERGE (a:Account {id: 'A-001'}) SET a.balance = 125000,   a.currency = 'RUB', a.level = 'STANDARD';
MERGE (a:Account {id: 'A-002'}) SET a.balance = 78000,    a.currency = 'RUB', a.level = 'STANDARD';
MERGE (a:Account {id: 'A-003'}) SET a.balance = 243000,   a.currency = 'RUB', a.level = 'STANDARD';
MERGE (a:Account {id: 'A-004'}) SET a.balance = 9800000,  a.currency = 'RUB', a.level = 'VIP';

// Владение счетами и связи между клиентами.
MATCH (p:Person {id: 'P-001'}), (a:Account {id: 'A-001'}) MERGE (p)-[:OWNS]->(a);
MATCH (p:Person {id: 'P-002'}), (a:Account {id: 'A-002'}) MERGE (p)-[:OWNS]->(a);
MATCH (p:Person {id: 'P-003'}), (a:Account {id: 'A-003'}) MERGE (p)-[:OWNS]->(a);
MATCH (p:Person {id: 'P-004'}), (a:Account {id: 'A-004'}) MERGE (p)-[:OWNS]->(a);
MATCH (x:Person {id: 'P-001'}), (y:Person {id: 'P-002'}) MERGE (x)-[:KNOWS {since: 2021}]->(y);
MATCH (x:Person {id: 'P-002'}), (y:Person {id: 'P-003'}) MERGE (x)-[:KNOWS {since: 2023}]->(y);

// Переводы для проверки создания, чтения и запрета удаления объектов.
MERGE (t:Transaction {id: 'T-001'}) SET t.amount = 15000,  t.timestamp = datetime('2026-10-15T10:30:00Z');
MERGE (t:Transaction {id: 'T-002'}) SET t.amount = 42000,  t.timestamp = datetime('2026-10-16T14:45:00Z');
MERGE (t:Transaction {id: 'T-003'}) SET t.amount = 500000, t.timestamp = datetime('2026-10-20T09:00:00Z');
MATCH (a:Account {id: 'A-001'}), (t:Transaction {id: 'T-001'}), (b:Account {id: 'A-002'}) MERGE (a)-[:SENT]->(t)-[:RECEIVED_BY]->(b);
MATCH (a:Account {id: 'A-002'}), (t:Transaction {id: 'T-002'}), (b:Account {id: 'A-003'}) MERGE (a)-[:SENT]->(t)-[:RECEIVED_BY]->(b);
MATCH (a:Account {id: 'A-004'}), (t:Transaction {id: 'T-003'}), (b:Account {id: 'A-001'}) MERGE (a)-[:SENT]->(t)-[:RECEIVED_BY]->(b);
