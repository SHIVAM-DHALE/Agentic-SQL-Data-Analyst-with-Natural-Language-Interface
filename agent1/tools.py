"""
tools.py
Execute SQL queries on PostgreSQL.
"""

import logging

import psycopg2

from practice.config import (
    DB_CONFIG,
    DB_STATEMENT_TIMEOUT_MS,
    DEFAULT_ROW_LIMIT,
)
from practice.sql_validator import validate_sql


logger = logging.getLogger(__name__)


def _apply_default_limit(sql: str) -> str:
    """Enforce a maximum result size even when SQL contains an inner LIMIT."""
    stripped = sql.strip()
    if stripped.endswith(";"):
        stripped = stripped[:-1].strip()
    # Wrapping avoids fragile SQL rewriting and also caps a model-supplied
    # ``LIMIT ALL`` or an unreasonably large LIMIT.
    return (
        "SELECT * FROM ("
        f"{stripped}"
        ") AS _agentic_sql_result "
        f"LIMIT {DEFAULT_ROW_LIMIT};"
    )


def execute_sql(sql, allowed_tables=None):
    is_valid, message = validate_sql(sql, allowed_tables=allowed_tables)

    if not is_valid:
        raise ValueError(message)

    sql = _apply_default_limit(sql)
    logger.info("Executing read-only SQL")

    conn = None
    cursor = None

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_session(readonly=True, autocommit=False)
        cursor = conn.cursor()

        cursor.execute(
            "SET LOCAL statement_timeout = %s;",
            (DB_STATEMENT_TIMEOUT_MS,)
        )
        cursor.execute(sql)

        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall() if cursor.description else []

        conn.rollback()
        logger.info("SQL returned %s rows", len(rows))

        return columns, rows

    except Exception as e:
        logger.exception("Database execution failed")
        raise

    finally:
        if cursor:
            cursor.close()

        if conn:
            conn.close()


if __name__ == "__main__":

    columns, rows = execute_sql(
        "SELECT COUNT(*) AS total_orders FROM orders;"
    )

    print("Columns:", columns)
    print("Rows:", rows)
