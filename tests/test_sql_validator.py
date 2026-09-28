import pytest

from practice.sql_validator import validate_sql


DEMO_TABLES = ["customers", "products", "orders", "order_items"]
DATASET_TABLE = "dataset_7_abc"


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM orders;",
        "SELECT COUNT(*) FROM orders",
        "SELECT 'DELETE; -- text, not SQL' AS note FROM orders;",
        "SELECT 'O''Reilly' AS customer_name FROM customers;",
        "SELECT EXTRACT(YEAR FROM order_date) AS year FROM orders;",
        "SELECT DATE_TRUNC('month', order_date) FROM orders;",
        "SELECT * FROM ONLY orders;",
        "SELECT o.order_id FROM orders AS o JOIN order_items AS oi ON oi.order_id = o.order_id;",
        "SELECT * FROM orders, products;",
        "SELECT * FROM orders UNION ALL SELECT * FROM orders;",
        "WITH x AS (SELECT * FROM orders) SELECT * FROM x;",
        "WITH x AS MATERIALIZED (SELECT * FROM orders), y AS (SELECT * FROM x) SELECT * FROM y;",
        "WITH x(order_id) AS (SELECT order_id FROM orders) SELECT * FROM x;",
        (
            "WITH RECURSIVE x AS ("
            "SELECT MIN(order_id) AS order_id FROM orders "
            "UNION ALL SELECT order_id + 1 FROM x WHERE order_id < 3"
            ") SELECT * FROM x;"
        ),
        "SELECT * FROM (SELECT * FROM orders) AS nested_orders;",
        "SELECT * FROM generate_series(1, 3) AS value;",
    ],
)
def test_valid_demo_read_only_queries(sql):
    assert validate_sql(sql, DEMO_TABLES) == (True, "SQL is valid.")


def test_dynamic_table_allowlist_is_exact():
    assert validate_sql(f"SELECT * FROM {DATASET_TABLE};", [DATASET_TABLE])[0]
    assert validate_sql(f"SELECT * FROM {DATASET_TABLE};", DATASET_TABLE)[0]

    valid, message = validate_sql(
        "SELECT * FROM dataset_8_other;", [DATASET_TABLE]
    )
    assert not valid
    assert "not in the allowed table list" in message


def test_explicit_empty_allowlist_never_falls_back_to_demo_tables():
    assert validate_sql("SELECT 1;", [])[0]
    assert not validate_sql("SELECT * FROM orders;", [])[0]


def test_schema_qualified_table_requires_exact_qualified_allowlist():
    sql = "SELECT * FROM public.dataset_7_abc;"
    assert not validate_sql(sql, [DATASET_TABLE])[0]
    assert validate_sql(sql, ["public.dataset_7_abc"])[0]


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO orders(order_id) VALUES (1);",
        "UPDATE orders SET status = 'Completed';",
        "DELETE FROM orders;",
        "DROP TABLE orders;",
        "ALTER TABLE orders ADD COLUMN unsafe int;",
        "TRUNCATE orders;",
        "CREATE TABLE copied AS SELECT * FROM orders;",
        "REPLACE INTO orders VALUES (1);",
        "MERGE INTO orders USING products ON TRUE WHEN MATCHED THEN DELETE;",
        "GRANT SELECT ON orders TO public;",
        "REVOKE SELECT ON orders FROM public;",
        "COPY orders TO '/tmp/orders.csv';",
        "CALL unsafe_proc();",
        "DO $$ BEGIN NULL; END $$;",
        "BEGIN;",
        "START TRANSACTION;",
        "COMMIT;",
        "ROLLBACK;",
        "SAVEPOINT unsafe;",
        "RELEASE SAVEPOINT unsafe;",
        "PREPARE unsafe AS SELECT * FROM orders;",
        "EXECUTE unsafe;",
        "VACUUM orders;",
        "ANALYZE orders;",
        "SELECT * INTO copied_orders FROM orders;",
        "WITH changed AS (DELETE FROM orders RETURNING *) SELECT * FROM changed;",
        "WITH x AS (SELECT * FROM orders) DELETE FROM orders;",
    ],
)
def test_rejects_write_ddl_copy_call_do_and_transaction_commands(sql):
    assert not validate_sql(sql)[0]


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM orders; SELECT * FROM customers;",
        "SELECT * FROM orders;;",
        ";SELECT * FROM orders;",
        "SELECT * FROM orders; DROP TABLE orders;",
        "SELECT * FROM orders -- comment",
        "SELECT * FROM orders /* comment */;",
        "SELECT * FROM orders */;",
    ],
)
def test_rejects_multiple_statements_and_comments(sql):
    assert not validate_sql(sql)[0]


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM (orders;",
        "SELECT * FROM orders);",
        "SELECT 'unterminated FROM orders;",
        'SELECT * FROM "orders";',
        "SELECT * FROM `orders`;",
        "SELECT $$orders$$ FROM orders;",
        "SELECT 'C:\\temp' FROM orders;",
        "SELECT * FROM dätaset_7_abc;",
    ],
)
def test_rejects_ambiguous_or_unsupported_syntax(sql):
    assert not validate_sql(sql, [DATASET_TABLE, "orders"])[0]


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM information_schema.tables;",
        "SELECT * FROM pg_catalog.pg_class;",
        "SELECT * FROM pg_toast.pg_toast_123;",
        "SELECT * FROM pg_temp.temp_data;",
        "SELECT * FROM pg_temp_3.temp_data;",
        "SELECT * FROM pg_class;",
        "SELECT pg_catalog.current_database();",
    ],
)
def test_rejects_postgresql_system_schemas_and_tables(sql):
    allowed = [
        "tables",
        "pg_class",
        "information_schema.tables",
        "pg_catalog.pg_class",
        "pg_toast.pg_toast_123",
        "pg_temp.temp_data",
        "pg_temp_3.temp_data",
    ]
    assert not validate_sql(sql, allowed)[0]


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM other_users_dataset;",
        "SELECT * FROM dataset_7_abc JOIN other_users_dataset ON TRUE;",
        "SELECT * FROM dataset_7_abc, other_users_dataset;",
        "SELECT * FROM (SELECT * FROM other_users_dataset) AS stolen;",
        "WITH x AS (SELECT * FROM other_users_dataset) SELECT * FROM x;",
        "WITH x AS (TABLE other_users_dataset) SELECT * FROM x;",
        "SELECT * FROM public.dataset_7_abc;",
        'SELECT * FROM "dataset_7_abc";',
        'SELECT * FROM "other_users_dataset";',
        "SELECT * FROM ONLY (other_users_dataset);",
        "SELECT * FROM (dataset_7_abc JOIN other_users_dataset ON TRUE) AS joined;",
        "SELECT * FROM (TABLE other_users_dataset) AS stolen;",
    ],
)
def test_rejects_allowlist_bypass_attempts(sql):
    assert not validate_sql(sql, [DATASET_TABLE])[0]


def test_cte_aliases_do_not_expand_the_physical_table_allowlist():
    allowed = [DATASET_TABLE]
    assert validate_sql(
        "WITH summary AS (SELECT * FROM dataset_7_abc) SELECT * FROM summary;",
        allowed,
    )[0]
    assert not validate_sql(
        "WITH summary AS (SELECT * FROM other_users_dataset) SELECT * FROM summary;",
        allowed,
    )[0]


def test_cte_name_in_an_unrelated_nested_scope_cannot_hide_a_physical_table():
    sql = """
    SELECT *
    FROM other_users_dataset
    WHERE EXISTS (
        WITH other_users_dataset AS (SELECT * FROM dataset_7_abc)
        SELECT 1 FROM other_users_dataset
    );
    """
    assert not validate_sql(sql, [DATASET_TABLE])[0]


def test_nested_cte_inherits_an_outer_cte_safely():
    sql = """
    WITH scoped AS (SELECT * FROM dataset_7_abc)
    SELECT * FROM (
        WITH nested AS (SELECT * FROM scoped)
        SELECT * FROM nested
    ) AS result;
    """
    assert validate_sql(sql, [DATASET_TABLE])[0]


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT pg_read_file('/etc/passwd');",
        "SELECT pg_read_binary_file('/etc/passwd');",
        "SELECT pg_ls_dir('/tmp');",
        "SELECT pg_stat_file('/tmp/file');",
        "SELECT pg_sleep(10);",
        "SELECT pg_terminate_backend(123);",
        "SELECT pg_notify('channel', 'payload');",
        "SELECT lo_import('/tmp/file');",
        "SELECT lo_export(1, '/tmp/file');",
        "SELECT * FROM dblink('connection', 'SELECT 1') AS t(value int);",
        "SELECT query_to_xml('SELECT * FROM secrets', true, false, '');",
        "SELECT net.http_get('https://example.com');",
        "SELECT http_get('https://example.com');",
        "SELECT aws_s3.query_export_to_s3('SELECT 1', 'bucket');",
        "SELECT set_config('search_path', 'pg_catalog', false);",
        "SELECT current_setting('search_path');",
        "SELECT nextval('orders_order_id_seq');",
        "SELECT currval('orders_order_id_seq');",
        "SELECT pg_get_functiondef(1);",
    ],
)
def test_rejects_file_network_admin_and_side_effect_functions(sql):
    assert not validate_sql(sql)[0]


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM orders FOR UPDATE;",
        "SELECT * FROM orders FOR SHARE;",
        "SELECT * FROM orders FOR KEY SHARE;",
        "SELECT * FROM orders FOR NO KEY UPDATE;",
    ],
)
def test_rejects_row_locking_selects(sql):
    assert not validate_sql(sql)[0]


@pytest.mark.parametrize(
    "sql",
    [
        "VALUES (1);",
        "TABLE orders;",
        "EXPLAIN SELECT * FROM orders;",
        "WITH x AS (SELECT * FROM orders) VALUES (1);",
    ],
)
def test_only_select_or_with_select_is_accepted(sql):
    assert not validate_sql(sql)[0]


@pytest.mark.parametrize(
    "allowed",
    [
        [""],
        ["dataset name"],
        ['"dataset_7_abc"'],
        ["a.b.c"],
        ["pg_catalog.pg_class"],
        ["pg_class"],
    ],
)
def test_invalid_or_system_allowlist_entries_are_rejected(allowed):
    assert not validate_sql("SELECT 1;", allowed)[0]
