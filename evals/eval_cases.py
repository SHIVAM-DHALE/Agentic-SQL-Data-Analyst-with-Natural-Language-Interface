EVAL_CASES = [
    {
        "question": "Show total revenue",
        "expected_intent": "total_revenue",
        "required_terms": ["SUM", "quantity", "price", "order_items"],
        "expected_columns": ["total_revenue"],
    },
    {
        "question": "Show revenue by category",
        "expected_intent": "revenue_by_category",
        "required_terms": ["category", "SUM", "quantity", "price", "GROUP BY"],
        "expected_columns": ["category", "revenue"],
    },
    {
        "question": "Show top 5 products by revenue",
        "expected_intent": "top_products_by_revenue",
        "required_terms": ["products", "order_items", "SUM", "ORDER BY", "LIMIT"],
        "expected_columns": ["product_name", "revenue"],
    },
    {
        "question": "How many total orders are there",
        "expected_intent": "total_orders",
        "required_terms": ["COUNT", "orders"],
        "expected_columns": ["total_orders"],
    },
    {
        "question": "Show orders by country",
        "expected_intent": "orders_by_country",
        "required_terms": ["customers", "orders", "country", "COUNT", "GROUP BY"],
        "expected_columns": ["country", "total_orders"],
    },
]