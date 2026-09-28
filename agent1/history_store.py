"""
history_store.py
Stores and retrieves user analysis history permanently in PostgreSQL.
"""

import json
from decimal import Decimal
from datetime import date, datetime

import psycopg2
from psycopg2.extras import Json

from agent1.tools import DB_CONFIG


def make_json_safe(value):
    """
    Converts Python objects like Decimal, date, datetime, tuple
    into JSON-safe values.
    """

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (date, datetime)):
        return value.isoformat()

    if isinstance(value, tuple):
        return [make_json_safe(item) for item in value]

    if isinstance(value, list):
        return [make_json_safe(item) for item in value]

    if isinstance(value, dict):
        return {
            key: make_json_safe(val)
            for key, val in value.items()
        }

    return value


def create_history_table():
    """
    Creates analysis_history table if it does not already exist.
    """

    conn = None
    cursor = None

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_history (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100),
                question TEXT,
                sql_query TEXT,
                columns_json JSONB,
                result_json JSONB,
                insight TEXT,
                chart_path TEXT,
                report_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        conn.commit()

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def save_analysis(username, response):
    """
    Saves one analysis response permanently in PostgreSQL.
    """

    create_history_table()

    columns = make_json_safe(response.get("columns", []))
    result = make_json_safe(response.get("result", []))

    conn = None
    cursor = None

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO analysis_history (
                username,
                question,
                sql_query,
                columns_json,
                result_json,
                insight,
                chart_path,
                report_path
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (
                username,
                response.get("question", ""),
                response.get("sql", ""),
                Json(columns),
                Json(result),
                response.get("insight", ""),
                response.get("chart_path", ""),
                response.get("report_path", "")
            )
        )

        conn.commit()

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def get_analysis_history(username, limit=None):
    """
    Gets saved analysis history for one user.
    """

    create_history_table()

    conn = None
    cursor = None

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        query = """
            SELECT
                id,
                question,
                sql_query,
                columns_json,
                result_json,
                insight,
                chart_path,
                report_path,
                created_at
            FROM analysis_history
            WHERE username = %s
            ORDER BY created_at DESC
        """

        params = [username]

        if limit is not None:
            query += " LIMIT %s"
            params.append(limit)

        cursor.execute(query + ";", tuple(params))

        rows = cursor.fetchall()

        history = []

        for row in rows:
            history.append(
                {
                    "id": row[0],
                    "question": row[1],
                    "sql": row[2],
                    "columns": row[3],
                    "result": row[4],
                    "insight": row[5],
                    "chart_path": row[6],
                    "report_path": row[7],
                    "created_at": row[8]
                }
            )

        return history

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def clear_user_history(username):
    """
    Deletes all saved history for one user.
    """

    create_history_table()

    conn = None
    cursor = None

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM analysis_history
            WHERE username = %s;
            """,
            (username,)
        )

        conn.commit()

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
