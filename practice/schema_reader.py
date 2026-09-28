"""
Schema reader for the analytics database.

The model should use the actual project tables:
customers, products, orders, and order_items.
"""

HARDCODED_SCHEMA = """
Table: customers
  - customer_id  INTEGER   PRIMARY KEY
  - country      VARCHAR   (e.g. Spain, Italy, France)
  - signup_date  DATE

Table: products
  - product_id   INTEGER   PRIMARY KEY
  - product_name VARCHAR   (e.g. Product_1, Product_2)
  - category     VARCHAR   (e.g. Body, Skin)

Table: orders
  - order_id     INTEGER   PRIMARY KEY
  - customer_id  INTEGER   FK -> customers.customer_id
  - order_date   DATE
  - status       VARCHAR   (e.g. Completed, Pending)

Table: order_items
  - order_id     INTEGER   FK -> orders.order_id
  - product_id   INTEGER   FK -> products.product_id
  - quantity     INTEGER
  - price        DECIMAL   (price per unit)

IMPORTANT NOTES for writing queries:
- Revenue = quantity * price  (there is no sale_amount column)
- Use order_items to get revenue, not orders
- customers table has NO name column, only country
- Join order_items with products on product_id for product details
- Join orders with order_items on order_id for order details
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from practice.config import DB_CONFIG

def get_schema(use_live_db: bool = False) -> str:
    if use_live_db:
        return _get_live_schema()
    return HARDCODED_SCHEMA.strip()

def _get_live_schema() -> str:
    try:
        import psycopg2
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema='public' ORDER BY table_name;
        """)
        tables = [r[0] for r in cur.fetchall()]
        schema = ""
        for t in tables:
            schema += f"\nTable: {t}\n"
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name=%s ORDER BY ordinal_position;
            """, (t,))
            for col, dtype in cur.fetchall():
                schema += f"  - {col}  {dtype.upper()}\n"
        cur.close(); conn.close()
        return schema.strip()
    except Exception as e:
        print(f"[schema_reader] DB failed ({e}), using hardcoded.")
        return HARDCODED_SCHEMA.strip()

if __name__ == "__main__":
    print(get_schema())
