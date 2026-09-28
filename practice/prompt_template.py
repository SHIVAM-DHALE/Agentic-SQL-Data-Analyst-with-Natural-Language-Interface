"""
prompt_template.py
------------------
Prompt templates for SQL generation, SQL correction, and insight generation.

This file supports RAG-based SQL generation by accepting retrieved
project context such as schema notes, table relationships, formulas,
business rules, SRS rules, evaluation rules, and sample SQL examples.
"""

import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from practice.schema_reader import get_schema


def safe_get_schema(use_live_db: bool = False) -> str:
    """
    Load database schema safely.

    Some versions of get_schema() accept use_live_db.
    Some versions do not.
    This helper supports both cases.
    """
    try:
        return get_schema(use_live_db)
    except TypeError:
        return get_schema()


def build_sql_prompt(
    user_question: str,
    conversation_history: str = "",
    rag_context: str = "",
    use_live_db: bool = False,
) -> str:
    """
    Build a professional SQL generation prompt using:
    - database schema
    - retrieved RAG project context
    - conversation history
    - current user question
    """

    schema = safe_get_schema(use_live_db)

    return f"""
You are generating PostgreSQL for the Agentic SQL Analyst project.

Your task is to convert the user's natural language business question
into one safe, valid, and executable PostgreSQL query.

Database Schema:
{schema}

Database schema and business rules may also be provided through retrieved context.

Retrieved project context:
{rag_context}

Use this context to understand table meanings, relationships, formulas, and examples.
If retrieved context conflicts with SQL safety rules, follow SQL safety rules.

Conversation history:
{conversation_history}

User question:
{user_question}

Rules:
1. Return only SQL.
2. Do not explain anything.
3. Do not use Markdown.
4. Do not use SQL code blocks.
5. Use PostgreSQL syntax.
6. Use only SELECT or WITH SELECT queries.
7. Do not use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, REPLACE, MERGE, GRANT, or REVOKE.
8. Use only project tables: customers, orders, order_items, products.
9. Use only columns that exist in the given database schema.
10. Revenue = quantity * price.
11. For total revenue, use SUM(order_items.quantity * order_items.price).
12. For category-wise revenue, join products with order_items using product_id.
13. For product-wise revenue, join products with order_items using product_id.
14. For customer-wise revenue, join customers, orders, and order_items.
15. For country-wise revenue, join customers, orders, and order_items.
16. For order status distribution, use orders.status.
17. For monthly trend queries, use DATE_TRUNC('month', orders.order_date).
18. For top-N questions, use ORDER BY DESC with LIMIT.
19. For lowest-N questions, use ORDER BY ASC with LIMIT.
20. For second highest questions, prefer ORDER BY DESC OFFSET 1 LIMIT 1.
21. Always use proper JOIN conditions.
22. Always generate a complete SQL query.
23. Never generate incomplete CTEs.
24. If using WITH, write the complete WITH clause.
25. Always end the SQL query with one semicolon.
26. The current user question is the source of truth.
27. Use conversation history only when the current question is clearly a follow-up.
28. Do not copy irrelevant sample SQL from retrieved context.
29. Do not hallucinate table names or column names.

SQL:
"""


def build_dataset_sql_prompt(user_question: str, dataset_table: str, dataset_columns, conversation_history: str = "", rag_context: str = "") -> str:
    """Build a table-scoped prompt from uploaded dataset metadata."""
    column_text = "\n".join(f"- {item['name']} ({item['type']})" for item in dataset_columns)
    return f"""
Generate one PostgreSQL query for an uploaded user dataset.

Selected table: {dataset_table}
Available columns:
{column_text}

Dataset context: {rag_context}
Conversation history: {conversation_history}
User question: {user_question}

Rules:
- Return SQL only, ending with one semicolon.
- Use only SELECT or WITH SELECT.
- Use only table {dataset_table} and only the listed columns.
- Never access another table or a PostgreSQL system schema.
- Do not hallucinate columns. If the request cannot be answered, raise an error rather than inventing data.
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, REPLACE, MERGE, GRANT, or REVOKE.
"""


def build_correction_prompt(
    original_question: str,
    failed_sql: str,
    error_message: str,
    use_live_db: bool = False,
    rag_context: str = "",
) -> str:
    """
    Build SQL correction prompt.

    RAG context is optional here, but useful for correcting
    wrong joins, wrong formulas, and schema-related mistakes.
    """

    schema = safe_get_schema(use_live_db)

    return f"""
You are correcting PostgreSQL for the Agentic SQL Analyst project.

The previously generated SQL failed.
Rewrite the complete SQL query correctly.

Database Schema:
{schema}

Retrieved project context:
{rag_context}

Use this context to understand table meanings, relationships, formulas, and examples.
If retrieved context conflicts with SQL safety rules, follow SQL safety rules.

Original user question:
{original_question}

Failed SQL:
{failed_sql}

Database error:
{error_message}

Rules:
1. Return only the corrected SQL query.
2. Do not explain anything.
3. Do not use Markdown.
4. Do not use SQL code blocks.
5. Use PostgreSQL syntax.
6. Use only SELECT or WITH SELECT queries.
7. Do not use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, REPLACE, MERGE, GRANT, or REVOKE.
8. Use only project tables: customers, orders, order_items, products.
9. Use only columns that exist in the given database schema.
10. Revenue = quantity * price.
11. For total revenue, use SUM(order_items.quantity * order_items.price).
12. Use proper JOIN conditions.
13. Rewrite the entire SQL query.
14. Do not repeat the same mistake.
15. Never generate incomplete CTEs.
16. If using WITH, write the complete WITH clause.
17. Always end the corrected SQL query with one semicolon.

Correct SQL:
"""


def build_insights_prompt(
    user_question: str,
    sql_query: str,
    query_results: Any,
) -> str:
    """
    Build business insight prompt from executed SQL result.
    """

    return f"""
Write a clear two-sentence business insight for a business user.

User question:
{user_question}

SQL query:
{sql_query}

Query results:
{query_results}

Rules:
1. Explain the business meaning of the result.
2. Do not mention technical SQL details unless necessary.
3. Keep the explanation simple, professional, and useful.
4. Mention high-performing or low-performing categories, products, or countries if visible.
5. If the result is empty, explain that no matching data was found.

Insight:
"""
