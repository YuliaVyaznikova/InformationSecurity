// Раздел 7 N 64: ролевое и дискреционное управление доступом к данным и администрированию.
CREATE ROLE analysts IF NOT EXISTS;
CREATE ROLE support_team IF NOT EXISTS;
CREATE ROLE operators IF NOT EXISTS;
CREATE ROLE auditors IF NOT EXISTS;
CREATE ROLE user_managers IF NOT EXISTS;

// Аналитик читает данные, но не видит паспорт и VIP-счёт.
GRANT ACCESS ON DATABASE neo4j TO analysts;
GRANT MATCH {*} ON GRAPH neo4j NODES * TO analysts;
GRANT MATCH {*} ON GRAPH neo4j RELATIONSHIPS * TO analysts;
DENY READ {passport} ON GRAPH neo4j NODES Person TO analysts;
DENY MATCH {*} ON GRAPH neo4j FOR (a:Account) WHERE a.level = 'VIP' TO analysts;
DENY LOAD ON CIDR '0.0.0.0/0' TO analysts;

// Поддержка видит только id, имя и телефон клиента и меняет только телефон.
GRANT ACCESS ON DATABASE neo4j TO support_team;
GRANT TRAVERSE ON GRAPH neo4j NODES Person TO support_team;
GRANT READ {id, name, phone} ON GRAPH neo4j NODES Person TO support_team;
GRANT SET PROPERTY {phone} ON GRAPH neo4j NODES Person TO support_team;

// Оператор создаёт переводы, но не меняет баланс и не удаляет объекты.
GRANT ACCESS ON DATABASE neo4j TO operators;
GRANT MATCH {*} ON GRAPH neo4j NODES Account, Transaction TO operators;
GRANT MATCH {*} ON GRAPH neo4j RELATIONSHIPS SENT, RECEIVED_BY TO operators;
GRANT CREATE ON GRAPH neo4j NODES Transaction TO operators;
GRANT CREATE ON GRAPH neo4j RELATIONSHIPS SENT, RECEIVED_BY TO operators;
GRANT SET PROPERTY {*} ON GRAPH neo4j NODES Transaction TO operators;
DENY SET PROPERTY {balance} ON GRAPH neo4j NODES Account TO operators;
DENY DELETE ON GRAPH neo4j TO operators;

// Аудитор видит пользователей и привилегии, но не бизнес-данные.
GRANT SHOW USER ON DBMS TO auditors;
GRANT SHOW ROLE ON DBMS TO auditors;
GRANT SHOW PRIVILEGE ON DBMS TO auditors;
GRANT SHOW SETTING * ON DBMS TO auditors;
GRANT SHOW TRANSACTION (*) ON DATABASE * TO auditors;
DENY ACCESS ON DATABASE neo4j TO auditors;

// Менеджер пользователей заводит и блокирует учётные записи, но не выдаёт роли.
GRANT USER MANAGEMENT ON DBMS TO user_managers;

// Раздел 8 N 64: создание пользователей и назначение паролей администратором.
CREATE USER analyst IF NOT EXISTS SET PASSWORD 'Analyst2026!' CHANGE NOT REQUIRED;
CREATE USER support IF NOT EXISTS SET PASSWORD 'Support2026!' CHANGE NOT REQUIRED;
CREATE USER operator IF NOT EXISTS SET PASSWORD 'Operator2026!' CHANGE NOT REQUIRED;
CREATE USER auditor IF NOT EXISTS SET PASSWORD 'Auditor2026!' CHANGE NOT REQUIRED;
CREATE USER usermgr IF NOT EXISTS SET PASSWORD 'UserMgr2026!' CHANGE NOT REQUIRED;

GRANT ROLE analysts TO analyst;
GRANT ROLE support_team TO support;
GRANT ROLE operators TO operator;
GRANT ROLE auditors TO auditor;
GRANT ROLE user_managers TO usermgr;
