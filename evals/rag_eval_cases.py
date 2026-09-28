"""
rag_eval_cases.py
-----------------
Test cases for evaluating RAG retrieval quality.

These cases check whether the RAG retriever returns the expected
schema context, business rules, formulas, and relationship information
for common business questions.
"""

RAG_EVAL_CASES = [
    {
        "name": "Revenue by country context retrieval",
        "question": "Show revenue by country",
        "expected_context_terms": [
            "Revenue",
            "quantity",
            "price",
            "customers",
            "country",
            "orders",
            "order_items",
            "customer_id",
            "order_id",
        ],
    },
    {
        "name": "Completed orders revenue context retrieval",
        "question": "Show completed orders revenue",
        "expected_context_terms": [
            "Revenue",
            "quantity",
            "price",
            "orders",
            "status",
            "Completed",
            "order_items",
        ],
    },
    {
        "name": "Revenue by category context retrieval",
        "question": "Show revenue by category",
        "expected_context_terms": [
            "Revenue",
            "quantity",
            "price",
            "products",
            "category",
            "product_id",
            "order_items",
        ],
    },
    {
        "name": "Monthly revenue trend context retrieval",
        "question": "Show revenue trend by month",
        "expected_context_terms": [
            "Revenue",
            "quantity",
            "price",
            "DATE_TRUNC",
            "month",
            "order_date",
            "orders",
            "order_items",
        ],
    },
    {
        "name": "Top products by revenue context retrieval",
        "question": "Show top 5 products by revenue",
        "expected_context_terms": [
            "products",
            "product_name",
            "Revenue",
            "quantity",
            "price",
            "ORDER BY",
            "LIMIT",
        ],
    },
        {
        "name": "Customers above average order count context retrieval",
        "question": "Show customers who placed more orders than the average number of orders per customer",
        "expected_context_terms": [
            "customers",
            "orders",
            "customer_id",
            "order_id",
            "COUNT",
            "AVG",
            "average",
        ],
    },
]