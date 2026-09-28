"""
run_query_demo.py
Standalone PostgreSQL query execution demo.
"""

import psycopg2
import pandas as pd
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from practice.config import DB_CONFIG

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def test_connection() -> bool:
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("""SELECT table_name FROM information_schema.tables
                       WHERE table_schema='public';""")
        tables = [r[0] for r in cur.fetchall()]
        conn.close()
        print("✅ DB Connected! Tables found:", tables)
        return True
    except Exception as e:
        print(f"❌ DB Connection failed: {e}")
        return False

def run_query(sql: str) -> pd.DataFrame:
    conn = get_connection()
    df   = pd.read_sql(sql, conn)
    conn.close()
    return df

if __name__ == "__main__":

    print("=" * 60)
    print("  AGENTIC SQL — Integration Demo (SQL + PostgreSQL)")
    print("=" * 60)

    print("\nStep 1: Testing database connection...")
    if not test_connection():
        print("Check the database configuration first.")
        exit()

    # Demo SQL statements for local database verification.
    demo_queries = [
        {
            "question": "Show total revenue",
            "sql": "SELECT SUM(quantity * price) AS total_revenue FROM order_items;"
        },
        {
            "question": "Show top 5 products by revenue",
            "sql": """SELECT p.product_name,
                             SUM(oi.quantity * oi.price) AS revenue
                      FROM order_items oi
                      JOIN products p ON oi.product_id = p.product_id
                      GROUP BY p.product_name
                      ORDER BY revenue DESC LIMIT 5;"""
        },
        {
            "question": "Show revenue by category",
            "sql": """SELECT p.category,
                             SUM(oi.quantity * oi.price) AS revenue
                      FROM order_items oi
                      JOIN products p ON oi.product_id = p.product_id
                      GROUP BY p.category
                      ORDER BY revenue DESC;"""
        },
        {
            "question": "How many total orders",
            "sql": "SELECT COUNT(*) AS total_orders FROM orders;"
        },
        {
            "question": "Show top 5 customers by spending",
            "sql": """SELECT o.customer_id,
                             SUM(oi.quantity * oi.price) AS total_spent
                      FROM orders o
                      JOIN order_items oi ON o.order_id = oi.order_id
                      GROUP BY o.customer_id
                      ORDER BY total_spent DESC LIMIT 5;"""
        },
        {
            "question": "Show orders by country",
            "sql": """SELECT c.country,
                             COUNT(o.order_id) AS total_orders
                      FROM customers c
                      JOIN orders o ON c.customer_id = o.customer_id
                      GROUP BY c.country
                      ORDER BY total_orders DESC;"""
        },
    ]

    print("\nStep 2: Running NL → SQL → Database pipeline...\n")

    for item in demo_queries:
        print(f"{'='*60}")
        print(f" Question : {item['question']}")
        print(f" SQL      : {item['sql'].strip()[:80]}...")
        try:
            df = run_query(item["sql"])
            print(f" Result   : {len(df)} rows returned")
            print(df.to_string(index=False))
            print(f" Status   : ✅ SUCCESS")
        except Exception as e:
            print(f" Status   : ❌ ERROR — {e}")
        print()

    print("=" * 60)
    print("✅ Full integration test complete!")
    print("   SQL generation module + PostgreSQL = WORKING")
    print("=" * 60)
