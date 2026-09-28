"""
run_query.py
-------------
Standalone integration helper for SQL generation and PostgreSQL execution.
"""

import psycopg2
import pandas as pd
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from practice.sql_generator import SQLGenerator
from practice.config import DB_CONFIG

def get_connection():
    """Returns a live PostgreSQL connection from environment configuration."""
    return psycopg2.connect(**DB_CONFIG)


def run_pipeline(user_question: str) -> dict:
    """
    Full pipeline: natural language question -> SQL -> database results

    Args:
        user_question: plain English question from user

    Returns:
        {
          "question" : original question,
          "sql"      : generated SQL,
          "columns"  : list of column names,
          "rows"     : list of result rows,
          "df"       : pandas DataFrame for downstream analytics,
          "error"    : error message if failed
        }
    """
    print(f"\n{'='*55}")
    print(f" Question : {user_question}")
    print(f"{'='*55}")

    # Generate SQL from the user question.
    generator = SQLGenerator()
    try:
        sql = generator.generate_sql(user_question)
        print(f" SQL      : {sql}")
    except Exception as e:
        print(f" SQL Error: {e}")
        return {"question": user_question, "sql": None,
                "columns": [], "rows": [], "df": None, "error": str(e)}

    # Execute the generated SQL against PostgreSQL.
    try:
        conn = get_connection()
        df   = pd.read_sql(sql, conn)
        conn.close()

        print(f" Columns  : {list(df.columns)}")
        print(f" Rows     : {len(df)} rows returned")
        print(f" Preview  :\n{df.head(3).to_string(index=False)}")

        return {
            "question": user_question,
            "sql":      sql,
            "columns":  list(df.columns),
            "rows":     df.values.tolist(),
            "df":       df,
            "error":    None
        }

    except Exception as e:
        print(f" DB Error : {e}")
        return {
            "question": user_question,
            "sql":      sql,
            "columns":  [],
            "rows":     [],
            "df":       None,
            "error":    str(e)
        }


def test_connection() -> bool:
    """Quick test that checks if PostgreSQL is reachable."""
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
        tables = [r[0] for r in cur.fetchall()]
        conn.close()
        print("✅ DB Connected! Tables found:", tables)
        return True
    except Exception as e:
        print(f"❌ DB Connection failed: {e}")
        return False


# ── Run this file to test integration ─────────────────────────
if __name__ == "__main__":

    # First check DB is reachable
    print("Testing DB connection...")
    if not test_connection():
        print("\nMake sure PostgreSQL is running and the project database is set up.")
        exit()

    # Test representative questions against the configured database.
    test_questions = [
        "Show total revenue",
        "Show top 5 products by revenue",
        "Show revenue by category",
        "How many total orders are there",
        "Show top 5 customers by spending",
        "Show orders by country",
    ]

    for q in test_questions:
        result = run_pipeline(q)
        if result["error"]:
            print(f" ❌ Error: {result['error']}")
        else:
            print(f" ✅ Success — {len(result['rows'])} rows")
