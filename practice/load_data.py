import pandas as pd
import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from practice.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER

DATA_DIR = Path(__file__).resolve().parent

engine = create_engine(
    URL.create(
        "postgresql+psycopg2",
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=int(DB_PORT),
        database=DB_NAME,
    )
)

customers = pd.read_csv(DATA_DIR / "customers.csv")
products = pd.read_csv(DATA_DIR / "products.csv")
orders = pd.read_csv(DATA_DIR / "orders.csv", parse_dates=["order_date"])
order_items = pd.read_csv(DATA_DIR / "order_items.csv")

customers.to_sql("customers",     engine, if_exists="replace", index=False)
products.to_sql("products",       engine, if_exists="replace", index=False)
orders.to_sql("orders",           engine, if_exists="replace", index=False)
order_items.to_sql("order_items", engine, if_exists="replace", index=False)

print("✅ All data loaded successfully!")
