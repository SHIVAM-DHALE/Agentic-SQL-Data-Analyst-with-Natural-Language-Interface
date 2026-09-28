import re
from typing import Dict, List, Optional, Tuple

ALLOWED_TABLES = {
    "customers",
    "products",
    "orders",
    "order_items",
}

BLOCKED_TABLES = {
    "sales",
    "employees",
    "users",
}

QUESTION_INTENT_RULES = [
    {
        "intent": "advanced_customer_filter",
        "label": "advanced customer filter",
        "question_terms": ["customer", "average", "order", "category", "completed"],
        "any_question_terms": ["spend", "spent", "spending"],
        "required_sql_terms": [
            "customer_metrics",
            "average_metrics",
            "high_revenue_categories",
            "latest_orders",
            "Completed",
        ],
        "expected_columns": [
            "customer_id",
            "total_spending",
            "total_orders",
            "latest_order_date",
            "unique_categories_purchased",
        ],
        "explanation": [
            "The question asks for customers filtered by above-average spending and order count.",
            "The SQL calculates customer-level spending and order totals before applying filters.",
            "The SQL checks high-revenue categories and latest completed order status.",
            "The result returns customer ID, spending, orders, latest order date, and category count.",
        ],
    },
    {
        "intent": "total_revenue",
        "label": "total revenue",
        "question_terms": ["revenue"],
        "any_question_terms": ["total", "overall"],
        "required_sql_terms": ["SUM", "quantity", "price", "order_items"],
        "expected_columns": ["total_revenue"],
        "explanation": [
            "The question asks for total revenue.",
            "The SQL uses order_items because revenue is calculated from sold items.",
            "The SQL uses quantity multiplied by price and sums it into total_revenue.",
        ],
    },
    {
        "intent": "revenue_by_category",
        "label": "revenue by category",
        "question_terms": ["revenue", "category"],
        "required_sql_terms": ["category", "SUM", "quantity", "price", "GROUP BY"],
        "expected_columns": ["category", "revenue"],
        "explanation": [
            "The question asks for revenue split by product category.",
            "The SQL uses product category as the grouping field.",
            "The SQL calculates revenue with quantity multiplied by price.",
            "The result returns category and revenue columns.",
        ],
    },
    {
        "intent": "top_products_by_revenue",
        "label": "top products by revenue",
        "question_terms": ["product", "revenue"],
        "any_question_terms": ["top", "highest", "best"],
        "required_sql_terms": ["products", "order_items", "SUM", "ORDER BY", "LIMIT"],
        "expected_columns": ["product_name", "revenue"],
        "explanation": [
            "The question asks for products ranked by revenue.",
            "The SQL joins products with order_items to calculate product revenue.",
            "The SQL orders revenue from highest to lowest and limits the result.",
            "The result returns product name and revenue columns.",
        ],
    },
    {
        "intent": "total_orders",
        "label": "total orders",
        "question_terms": ["orders"],
        "any_question_terms": ["total", "count", "many"],
        "required_sql_terms": ["COUNT", "orders"],
        "expected_columns": ["total_orders"],
        "explanation": [
            "The question asks for the total number of orders.",
            "The SQL counts records from the orders table.",
            "The result returns total_orders.",
        ],
    },
    {
        "intent": "orders_by_country",
        "label": "orders by country",
        "question_terms": ["orders", "country"],
        "required_sql_terms": ["customers", "orders", "country", "COUNT", "GROUP BY"],
        "expected_columns": ["country", "total_orders"],
        "explanation": [
            "The question asks for order counts by country.",
            "The SQL joins customers and orders so each order can be mapped to a country.",
            "The SQL groups by country and counts orders.",
            "The result returns country and total_orders columns.",
        ],
    },
]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def detect_intent(question: str) -> Optional[Dict]:
    question_lower = normalize(question)

    for rule in QUESTION_INTENT_RULES:
        if not all(term in question_lower for term in rule["question_terms"]):
            continue

        any_terms = rule.get("any_question_terms", [])
        if any_terms and not any(term in question_lower for term in any_terms):
            continue

        return rule

    return None


def check_required_terms(sql: str, required_terms: List[str]) -> Tuple[bool, List[str]]:
    sql_upper = sql.upper()
    missing = []

    for term in required_terms:
        if term.upper() not in sql_upper:
            missing.append(term)

    return len(missing) == 0, missing


def check_blocked_tables(sql: str) -> Tuple[bool, List[str]]:
    sql_lower = normalize(sql)
    found = []

    for table in BLOCKED_TABLES:
        if re.search(rf"\b{table}\b", sql_lower):
            found.append(table)

    return len(found) == 0, found


def evaluate_sql_quality(
    question: str,
    sql: str,
    expected_columns: Optional[List[str]] = None,
    actual_columns: Optional[List[str]] = None,
    required_terms: Optional[List[str]] = None,
    columns: Optional[List[str]] = None,
) -> Dict:
    required_terms = required_terms or []
    expected_columns = expected_columns or []
    if actual_columns is None and columns is not None:
        actual_columns = columns
    actual_columns = actual_columns or []

    checks = []
    detected_intent = "unknown"
    detected_label = "Unknown request"
    explanation = []
    intent_rule = detect_intent(question)

    if intent_rule:
        detected_intent = intent_rule["intent"]
        detected_label = intent_rule.get("label", intent_rule["intent"])
        explanation = intent_rule.get("explanation", [])
        required_terms = required_terms or intent_rule["required_sql_terms"]
        expected_columns = expected_columns or intent_rule["expected_columns"]
        checks.append({
            "name": "Intent detection",
            "passed": True,
            "message": f"Detected request: {detected_label}",
        })
    else:
        checks.append({
            "name": "Intent detection",
            "passed": False,
            "message": "No predefined intent rule matched this question.",
        })

    terms_ok, missing_terms = check_required_terms(sql, required_terms)
    checks.append({
        "name": "Intent term match",
        "passed": terms_ok,
        "message": "Required SQL terms found" if terms_ok else f"Missing terms: {missing_terms}",
    })

    tables_ok, blocked_tables = check_blocked_tables(sql)
    checks.append({
        "name": "Schema/table check",
        "passed": tables_ok,
        "message": "No blocked tables found" if tables_ok else f"Unexpected tables: {blocked_tables}",
    })

    actual_columns_lower = [col.lower() for col in actual_columns]
    missing_columns = [
        col for col in expected_columns
        if col.lower() not in actual_columns_lower
    ]

    columns_ok = len(missing_columns) == 0
    checks.append({
        "name": "Result column check",
        "passed": columns_ok,
        "message": "Expected result columns found" if columns_ok else f"Missing columns: {missing_columns}",
    })

    passed_count = sum(1 for check in checks if check["passed"])
    score = round((passed_count / len(checks)) * 100, 2)

    if score >= 90:
        confidence = "High"
        recommendation = "SQL looks aligned with the detected business intent. Review the query if this is a high-stakes decision."
        next_steps = [
            "Use the result for analysis.",
            "Check the displayed columns match what you expected.",
            "For important decisions, review the generated SQL or ask a teammate to verify it.",
        ]
    elif score >= 70:
        confidence = "Medium"
        recommendation = "SQL is usable but should be reviewed. Check warnings, verify selected columns, and rephrase the question if intent looks wrong."
        next_steps = [
            "Read the failed or warning checks below.",
            "Confirm the detected request matches your actual question.",
            "If it does not match, rephrase with clear metric and grouping words.",
        ]
    else:
        confidence = "Low"
        recommendation = "Do not rely on this SQL yet. Rephrase the question with table/metric names or ask for a simpler query, then run analysis again."
        next_steps = [
            "Do not use this result for decision-making.",
            "Ask a simpler question with one metric and one grouping.",
            "Use clear words such as revenue, orders, customers, category, country, or product.",
        ]

    return {
        "score": score,
        "confidence": confidence,
        "passed": score >= 70,
        "detected_intent": detected_intent,
        "detected_label": detected_label,
        "explanation": explanation,
        "recommendation": recommendation,
        "next_steps": next_steps,
        "checks": checks,
    }
