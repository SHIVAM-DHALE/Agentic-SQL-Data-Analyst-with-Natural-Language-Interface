# """
# #sql_generator.py
# ----------------
# LangChain-backed Natural Language to SQL generator.

# This file replaces the direct Gemini SDK call with a LangChain chain:
# Prompt Template -> Chat LLM -> Output Parser -> SQL Cleaner -> SQL Validator
# """

# #import re
# import sys
# from pathlib import Path

# if __package__ in (None, ""):
#     sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# from langchain_core.output_parsers import StrOutputParser
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_google_genai import ChatGoogleGenerativeAI

# from practice.config import GEMINI_API_KEY, GEMINI_MODEL
# from practice.prompt_template import build_sql_prompt
# from practice.sql_validator import validate_sql


# class SQLGenerator:
#     """
#     Generates PostgreSQL from natural language using LangChain.

#     This class keeps the same public method names as your old SQLGenerator:
#     - generate_sql()
#     - call_gemini_raw()

#     Because of this, agent_controller.py and correction_loop.py need minimum changes.
#     """

#     def __init__(self):
#         if not GEMINI_API_KEY:
#             raise ValueError(
#                 "GEMINI_API_KEY or GOOGLE_API_KEY not found in .env file"
#             )

#         self.model_name = GEMINI_MODEL

#         self.llm = ChatGoogleGenerativeAI(
#             model=self.model_name,
#             google_api_key=GEMINI_API_KEY,
#             temperature=0
#         )

#         self.sql_chain = (
#             ChatPromptTemplate.from_messages(
#                 [
#                     (
#                         "system",
#                         "You are an expert PostgreSQL assistant. "
#                         "Return only a safe SELECT or WITH SELECT SQL query."
#                     ),
#                     ("human", "{prompt}")
#                 ]
#             )
#             | self.llm
#             | StrOutputParser()
#         )

#         self.raw_chain = (
#             ChatPromptTemplate.from_messages(
#                 [
#                     (
#                         "system",
#                         "You are a precise SQL assistant. Return only the requested SQL or answer."
#                     ),
#                     ("human", "{prompt}")
#                 ]
#             )
#             | self.llm
#             | StrOutputParser()
#         )

#     def generate_sql(
#         self,
#         user_question: str,
#         conversation_history: str = "",
#         use_live_db: bool = False
#     ) -> str:
#         """
#         Converts a natural language business question into PostgreSQL.
#         """
#         if not user_question or not user_question.strip():
#             raise ValueError("Question cannot be empty")

#         predefined = self.predefined_sql(user_question)
#         if predefined:
#             sql = self._clean(predefined)
#             self._validate(sql)
#             return sql

#         prompt = build_sql_prompt(
#             user_question,
#             conversation_history,
#             use_live_db
#         )

#         try:
#             response_text = self.sql_chain.invoke({"prompt": prompt})
#         except Exception as exc:
#             error_text = str(exc).lower()
#             if (
#                 "getaddrinfo failed" in error_text
#                 or "name resolution" in error_text
#                 or "dns" in error_text
#                 or "connection" in error_text
#             ):
#                 raise ConnectionError(
#                     "Network/DNS error: Gemini API is not reachable. "
#                     "Please check internet, DNS, VPN/proxy, and API key."
#                 )
#             raise

#         sql = self._clean(response_text)
#         self._validate(sql)
#         return sql

#     def call_gemini_raw(self, prompt: str) -> str:
#         """
#         Backward-compatible raw LLM call.
#         correction_loop.py can call this without knowing LangChain internals.
#         """
#         if not prompt or not prompt.strip():
#             raise ValueError("Prompt cannot be empty")

#         return self.raw_chain.invoke({"prompt": prompt}).strip()

#     def fix_sql_with_langchain(
#         self,
#         question: str,
#         wrong_sql: str,
#         error_message: str
#     ) -> str:
#         """
#         LangChain-powered SQL correction chain.
#         """
#         correction_prompt = f"""
# Fix the PostgreSQL query.

# User question:
# {question}

# Wrong SQL:
# {wrong_sql}

# Error message:
# {error_message}

# Database schema:
# - customers(customer_id, country, signup_date)
# - products(product_id, product_name, category)
# - orders(order_id, customer_id, order_date, status)
# - order_items(order_id, product_id, quantity, price)

# Rules:
# - Return only corrected SQL.
# - Use PostgreSQL syntax.
# - Use only SELECT or WITH SELECT queries.
# - Do not explain anything.
# - Do not include SQL comments.
# - Do not use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, REPLACE, MERGE, GRANT, or REVOKE.
# - End the SQL with one semicolon.
# """
#         corrected = self.raw_chain.invoke({"prompt": correction_prompt})
#         sql = self._clean(corrected)
#         self._validate(sql)
#         return sql

#     @staticmethod
#     def predefined_sql(user_question: str):
#         """
#         Reliable fallback for important demo questions.
#         This prevents demo failure for common complex CTE queries.
#         """
#         q = re.sub(r"\s+", " ", user_question.lower()).strip()

#         if (
#             "customer" in q
#             and "average" in q
#             and ("spend" in q or "spent" in q or "spending" in q)
#             and ("order" in q or "orders" in q)
#             and "categor" in q
#             and ("completed" in q or "complete" in q)
#         ):
#             return """
#             WITH customer_metrics AS (
#                 SELECT
#                     o.customer_id,
#                     COUNT(DISTINCT o.order_id) AS total_orders,
#                     COALESCE(SUM(oi.quantity * oi.price), 0) AS total_spending
#                 FROM orders o
#                 JOIN order_items oi
#                     ON o.order_id = oi.order_id
#                 GROUP BY o.customer_id
#             ),
#             average_metrics AS (
#                 SELECT
#                     AVG(total_orders) AS average_orders,
#                     AVG(total_spending) AS average_spending
#                 FROM customer_metrics
#             ),
#             category_revenue AS (
#                 SELECT
#                     p.category,
#                     SUM(oi.quantity * oi.price) AS revenue
#                 FROM products p
#                 JOIN order_items oi
#                     ON p.product_id = oi.product_id
#                 GROUP BY p.category
#             ),
#             high_revenue_categories AS (
#                 SELECT category
#                 FROM category_revenue
#                 WHERE revenue > (
#                     SELECT AVG(revenue)
#                     FROM category_revenue
#                 )
#             ),
#             customer_high_revenue_categories AS (
#                 SELECT
#                     o.customer_id,
#                     COUNT(DISTINCT p.category) AS high_revenue_categories_purchased
#                 FROM orders o
#                 JOIN order_items oi
#                     ON o.order_id = oi.order_id
#                 JOIN products p
#                     ON oi.product_id = p.product_id
#                 JOIN high_revenue_categories hrc
#                     ON p.category = hrc.category
#                 GROUP BY o.customer_id
#             ),
#             customer_unique_categories AS (
#                 SELECT
#                     o.customer_id,
#                     COUNT(DISTINCT p.category) AS unique_categories_purchased
#                 FROM orders o
#                 JOIN order_items oi
#                     ON o.order_id = oi.order_id
#                 JOIN products p
#                     ON oi.product_id = p.product_id
#                 GROUP BY o.customer_id
#             ),
#             latest_orders AS (
#                 SELECT
#                     customer_id,
#                     order_date AS latest_order_date,
#                     status AS latest_order_status
#                 FROM (
#                     SELECT
#                         customer_id,
#                         order_date,
#                         status,
#                         ROW_NUMBER() OVER (
#                             PARTITION BY customer_id
#                             ORDER BY order_date DESC, order_id DESC
#                         ) AS row_number
#                     FROM orders
#                 ) ranked_orders
#                 WHERE row_number = 1
#             ),
#             high_revenue_category_count AS (
#                 SELECT COUNT(*) AS category_count
#                 FROM high_revenue_categories
#             )
#             SELECT
#                 cm.customer_id,
#                 cm.total_spending,
#                 cm.total_orders,
#                 lo.latest_order_date,
#                 cuc.unique_categories_purchased
#             FROM customer_metrics cm
#             JOIN average_metrics am
#                 ON TRUE
#             JOIN latest_orders lo
#                 ON cm.customer_id = lo.customer_id
#             JOIN customer_unique_categories cuc
#                 ON cm.customer_id = cuc.customer_id
#             LEFT JOIN customer_high_revenue_categories chrc
#                 ON cm.customer_id = chrc.customer_id
#             CROSS JOIN high_revenue_category_count hrcc
#             WHERE cm.total_orders > am.average_orders
#               AND cm.total_spending > am.average_spending
#               AND COALESCE(chrc.high_revenue_categories_purchased, 0) = hrcc.category_count
#               AND lo.latest_order_status = 'Completed'
#             ORDER BY cm.total_spending DESC;
#             """

#         if "total revenue" in q or ("show revenue" in q and "by" not in q and "trend" not in q):
#             return """
#             SELECT COALESCE(SUM(quantity * price), 0) AS total_revenue
#             FROM order_items;
#             """

#         if ("top" in q or "highest" in q or "best" in q) and "product" in q and "revenue" in q:
#             limit_match = re.search(r"\btop\s+(\d+)\b", q)
#             limit = int(limit_match.group(1)) if limit_match else 5
#             return f"""
#             SELECT
#                 p.product_name,
#                 SUM(oi.quantity * oi.price) AS revenue
#             FROM order_items oi
#             JOIN products p
#                 ON oi.product_id = p.product_id
#             GROUP BY p.product_name
#             ORDER BY revenue DESC
#             LIMIT {limit};
#             """

#         if "revenue" in q and "category" in q:
#             return """
#             SELECT
#                 p.category,
#                 SUM(oi.quantity * oi.price) AS revenue
#             FROM order_items oi
#             JOIN products p
#                 ON oi.product_id = p.product_id
#             GROUP BY p.category
#             ORDER BY revenue DESC;
#             """

#         if "revenue" in q and "country" in q:
#             return """
#             SELECT
#                 c.country,
#                 SUM(oi.quantity * oi.price) AS revenue
#             FROM order_items oi
#             JOIN orders o
#                 ON oi.order_id = o.order_id
#             JOIN customers c
#                 ON o.customer_id = c.customer_id
#             GROUP BY c.country
#             ORDER BY revenue DESC;
#             """

#         if "revenue" in q and ("month" in q or "trend" in q):
#             return """
#             SELECT
#                 DATE_TRUNC('month', o.order_date)::date AS month,
#                 SUM(oi.quantity * oi.price) AS revenue
#             FROM orders o
#             JOIN order_items oi
#                 ON o.order_id = oi.order_id
#             GROUP BY month
#             ORDER BY month;
#             """

#         if ("total orders" in q or "how many orders" in q or "count orders" in q) and "country" not in q and "status" not in q:
#             return """
#             SELECT COUNT(*) AS total_orders
#             FROM orders;
#             """

#         if "orders" in q and "country" in q:
#             return """
#             SELECT
#                 c.country,
#                 COUNT(o.order_id) AS total_orders
#             FROM customers c
#             JOIN orders o
#                 ON c.customer_id = o.customer_id
#             GROUP BY c.country
#             ORDER BY total_orders DESC;
#             """

#         if "orders" in q and "status" in q:
#             return """
#             SELECT
#                 status,
#                 COUNT(*) AS total_orders
#             FROM orders
#             GROUP BY status
#             ORDER BY total_orders DESC;
#             """

#         if ("top" in q or "highest" in q or "best" in q) and "customer" in q and ("spending" in q or "spent" in q or "revenue" in q):
#             limit_match = re.search(r"\btop\s+(\d+)\b", q)
#             limit = int(limit_match.group(1)) if limit_match else 5
#             return f"""
#             SELECT
#                 o.customer_id,
#                 SUM(oi.quantity * oi.price) AS total_spent
#             FROM orders o
#             JOIN order_items oi
#                 ON o.order_id = oi.order_id
#             GROUP BY o.customer_id
#             ORDER BY total_spent DESC
#             LIMIT {limit};
#             """

#         if "total customers" in q or "how many customers" in q or "count customers" in q:
#             return """
#             SELECT COUNT(*) AS total_customers
#             FROM customers;
#             """

#         if "total products" in q or "how many products" in q or "count products" in q:
#             return """
#             SELECT COUNT(*) AS total_products
#             FROM products;
#             """

#         if "show all orders" in q or "list all orders" in q:
#             return """
#             SELECT
#                 order_id,
#                 customer_id,
#                 order_date,
#                 status
#             FROM orders
#             ORDER BY order_id DESC;
#             """

#         if "show all products" in q or "list all products" in q:
#             return """
#             SELECT
#                 product_id,
#                 product_name,
#                 category,
#                 price
#             FROM products
#             ORDER BY product_id;
#             """

#         if (
#             "product" in q
#             and "revenue" in q
#             and "average" in q
#             and ("greater" in q or "above" in q or "more than" in q)
#         ):
#             return """
#             WITH product_revenue AS (
#                 SELECT
#                     p.product_id,
#                     p.product_name,
#                     p.category,
#                     SUM(oi.quantity * oi.price) AS total_revenue
#                 FROM products p
#                 JOIN order_items oi
#                     ON p.product_id = oi.product_id
#                 GROUP BY p.product_id, p.product_name, p.category
#             )
#             SELECT
#                 product_id,
#                 product_name,
#                 category,
#                 total_revenue
#             FROM product_revenue
#             WHERE total_revenue > (
#                 SELECT AVG(total_revenue)
#                 FROM product_revenue
#             )
#             ORDER BY total_revenue DESC;
#             """

#         return None

#     @staticmethod
#     def _clean(text: str) -> str:
#         if not text:
#             raise ValueError("LLM returned empty response")

#         text = text.strip()
#         text = re.sub(r"```sql", "", text, flags=re.IGNORECASE)
#         text = text.replace("```", "").strip()

#         match = re.search(
#             r"\b(WITH|SELECT)\b[\s\S]*?;",
#             text,
#             flags=re.IGNORECASE
#         )

#         if match:
#             sql = match.group(0).strip()
#         else:
#             lines = text.splitlines()
#             collecting = False
#             parts = []

#             for line in lines:
#                 clean_line = line.strip()
#                 upper_line = clean_line.upper()

#                 if upper_line.startswith("SELECT") or upper_line.startswith("WITH"):
#                     collecting = True

#                 if collecting:
#                     parts.append(clean_line)

#             sql = " ".join(parts) if parts else text.strip()

#         sql = re.sub(r"\s+", " ", sql).strip()

#         if sql and not sql.endswith(";"):
#             sql += ";"

#         return sql

#     @staticmethod
#     def _validate(sql: str):
#         is_valid, message = validate_sql(sql)

#         if not is_valid:
#             raise ValueError(message)


# def generate_sql(question):
#     """
#     Wrapper function for older modules.
#     """
#     generator = SQLGenerator()
#     return generator.generate_sql(question)


# if __name__ == "__main__":
#     gen = SQLGenerator()

#     questions = [
#         "show revenue by category",
#         "show top 5 products by revenue",
#         "show revenue trend by month",
#         "show all products whose revenue is greater than the average revenue of all products",
#     ]

#     for q in questions:
#         print(f"\nQ: {q}")
#         try:
#             print(f"SQL: {gen.generate_sql(q)}")
#         except Exception as e:
#             print(f"ERROR: {e}")
"""
sql_generator.py
----------------
LangChain-backed Natural Language to SQL generator with RAG integration.

Final flow:
User Question + Conversation Memory + Retrieved RAG Context
-> Professional Prompt
-> LangChain/Gemini
-> SQL Cleaner
-> SQL Validator
-> Safe PostgreSQL SQL
"""

import re
import sys
from pathlib import Path
from typing import Iterable, List, Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from practice.config import GEMINI_API_KEY, GEMINI_MODEL
from practice.prompt_template import build_correction_prompt, build_dataset_sql_prompt, build_sql_prompt
from practice.sql_validator import validate_sql

try:
    from rag.retriever import get_rag_context
except Exception:
    def get_rag_context(question: str, k: int = 4) -> str:
        return ""


class SQLGenerator:
    """
    Generates PostgreSQL from natural language using LangChain + Gemini + RAG.

    Public methods:
    - generate_sql()
    - call_gemini_raw()
    - fix_sql_with_langchain()

    RAG metadata stored after each generation:
    - last_rag_context
    - last_rag_used
    - last_rag_sources
    """

    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY or GOOGLE_API_KEY not found in .env file"
            )

        self.model_name = GEMINI_MODEL

        # RAG metadata for API response
        self.last_rag_context = ""
        self.last_rag_used = False
        self.last_rag_sources: List[str] = []

        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=GEMINI_API_KEY,
            temperature=0
        )

        self.sql_chain = (
            ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "You are an expert PostgreSQL assistant for the "
                        "Agentic SQL Analyst project. Return only one safe "
                        "SELECT or WITH SELECT SQL query."
                    ),
                    ("human", "{prompt}")
                ]
            )
            | self.llm
            | StrOutputParser()
        )

        self.raw_chain = (
            ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "You are a precise SQL assistant. "
                        "Return only the requested SQL or answer."
                    ),
                    ("human", "{prompt}")
                ]
            )
            | self.llm
            | StrOutputParser()
        )

    def generate_sql(
        self,
        user_question: str,
        conversation_history: str = "",
        use_live_db: bool = False
    ) -> str:
        """
        Convert a natural language business question into PostgreSQL using:

        User Question
        + Conversation Memory
        + Retrieved RAG Context
        -> LangChain/Gemini
        -> Safe SQL
        """

        if not user_question or not user_question.strip():
            raise ValueError("Question cannot be empty")

        rag_context = self._safe_rag_context(user_question)

        # Store RAG metadata for agent_controller.py
        self.last_rag_context = rag_context
        self.last_rag_used = bool(rag_context.strip())
        self.last_rag_sources = self._extract_rag_sources(rag_context)

        prompt = build_sql_prompt(
            user_question=user_question,
            conversation_history=conversation_history,
            rag_context=rag_context,
            use_live_db=use_live_db,
        )

        try:
            response_text = self.sql_chain.invoke({"prompt": prompt})

            sql = self._clean(response_text)
            self._validate(sql)

            return sql

        except Exception as exc:
            error_text = str(exc).lower()

            if self._is_network_error(error_text):
                raise ConnectionError(
                    "Network/DNS error: Gemini API is not reachable. "
                    "Please check internet, DNS, VPN/proxy, and API key."
                ) from exc

            predefined = self.predefined_sql(user_question)

            if predefined:
                sql = self._clean(predefined)
                self._validate(sql)
                return sql

            raise

    def call_gemini_raw(self, prompt: str) -> str:
        """
        Backward-compatible raw LLM call.
        correction_loop.py can call this without knowing LangChain internals.
        """

        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        return self.raw_chain.invoke({"prompt": prompt}).strip()

    def generate_sql_for_dataset(
        self,
        user_question,
        dataset_table,
        dataset_columns,
        conversation_history="",
    ) -> str:
        """Generate and validate SQL constrained to one uploaded table."""
        if not user_question or not user_question.strip():
            raise ValueError("Question cannot be empty")

        dataset_table = self._safe_table_identifier(dataset_table)
        safe_columns = self._safe_dataset_columns(dataset_columns)
        column_lines = [
            f"- {item['name']} ({item['type']})" for item in safe_columns
        ] or ["- Schema metadata unavailable; do not invent columns"]
        dynamic_context = (
            f"The selected dataset is {dataset_table}. Available columns are "
            + ", ".join(line.removeprefix("- ") for line in column_lines)
            + ". Use only this table."
        )
        prompt = build_dataset_sql_prompt(
            user_question,
            dataset_table,
            safe_columns,
            conversation_history,
            dynamic_context,
        )
        response_text = self.sql_chain.invoke({"prompt": prompt})
        sql = self._clean(response_text)
        valid, message = validate_sql(sql, allowed_tables=[dataset_table])
        if not valid:
            raise ValueError(message)
        self.last_rag_context = dynamic_context
        self.last_rag_used = True
        self.last_rag_sources = ["dataset metadata"]
        return sql

    def fix_sql_with_langchain(
        self,
        question: str,
        wrong_sql: str,
        error_message: str,
        dataset_table: Optional[str] = None,
        dataset_columns=None,
        allowed_tables: Optional[Iterable[str]] = None,
    ) -> str:
        """
        LangChain-powered SQL correction chain.

        ``dataset_table``, ``dataset_columns``, and ``allowed_tables`` are
        optional so existing demo callers keep working.  Uploaded-dataset
        callers should pass all three; correction then receives only the
        selected dataset schema and the corrected SQL is validated against the
        same physical-table allowlist.
        """

        effective_allowed = self._effective_allowed_tables(
            dataset_table=dataset_table,
            allowed_tables=allowed_tables,
        )

        if dataset_table is not None:
            dataset_table = self._safe_table_identifier(dataset_table)
            column_lines = self._safe_dataset_column_lines(dataset_columns)
            allowed_text = ", ".join(effective_allowed or [dataset_table])
            correction_prompt = f"""
You are correcting PostgreSQL for one uploaded user dataset.

Original user question:
{question}

Failed SQL:
{wrong_sql}

Safe database error:
{error_message}

Selected physical table:
{dataset_table}

Available columns:
{chr(10).join(column_lines)}

Exact allowed physical tables:
{allowed_text}

Rules:
1. Return only one complete corrected SQL query ending with one semicolon.
2. Use PostgreSQL syntax and only SELECT or WITH ... SELECT.
3. Use only the selected physical table and the listed columns.
4. CTE aliases are allowed, but they must read only from the selected table.
5. Never reference a different table, schema, or PostgreSQL system catalog.
6. Never use comments, multiple statements, quoted identifiers, or dollar quoting.
7. Never use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE,
   REPLACE, MERGE, GRANT, REVOKE, COPY, CALL, DO, or transaction commands.
8. Never use filesystem, network, dblink, large-object, or administrative functions.
9. Rewrite the entire query and do not repeat the failed query's mistake.
"""
        else:
            rag_context = self._safe_rag_context(question)
            correction_prompt = build_correction_prompt(
                original_question=question,
                failed_sql=wrong_sql,
                error_message=error_message,
                rag_context=rag_context,
            )

        corrected = self.raw_chain.invoke({"prompt": correction_prompt})

        sql = self._clean(corrected)
        self._validate(sql, allowed_tables=effective_allowed)

        return sql

    def fix_sql_for_dataset(
        self,
        question: str,
        wrong_sql: str,
        error_message: str,
        dataset_table: str,
        dataset_columns,
    ) -> str:
        """Correct SQL while remaining bound to one uploaded dataset.

        This positional signature is intentionally small for the FastAPI query
        workflow.  ``fix_sql_with_langchain`` remains the general,
        backward-compatible entry point.
        """

        selected_table = self._safe_table_identifier(dataset_table)
        return self.fix_sql_with_langchain(
            question=question,
            wrong_sql=wrong_sql,
            error_message=error_message,
            dataset_table=selected_table,
            dataset_columns=dataset_columns,
            allowed_tables=[selected_table],
        )

    @staticmethod
    def _safe_table_identifier(dataset_table: str) -> str:
        """Validate a metadata-owned PostgreSQL table identifier."""

        if not isinstance(dataset_table, str) or not dataset_table.strip():
            raise ValueError("Dataset table name is missing")
        parts = dataset_table.strip().split(".")
        if len(parts) > 2 or any(
            not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", part)
            for part in parts
        ):
            raise ValueError("Dataset table name is not a safe SQL identifier")
        return ".".join(part.lower() for part in parts)

    @staticmethod
    def _safe_dataset_columns(dataset_columns) -> List[dict]:
        """Normalize dataset metadata without allowing prompt injection."""

        if not dataset_columns:
            return []

        columns: List[dict] = []
        for item in dataset_columns:
            if isinstance(item, dict):
                name = item.get("name")
                data_type = item.get("type", "unknown")
            else:
                name = item
                data_type = "unknown"

            if not isinstance(name, str) or not re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_$]*", name
            ):
                raise ValueError("Dataset schema contains an unsafe column identifier")

            safe_type = re.sub(r"[^A-Za-z0-9_ (),.\[\]+-]", "", str(data_type))[:80]
            columns.append(
                {"name": name.lower(), "type": safe_type or "unknown"}
            )
        return columns

    @classmethod
    def _safe_dataset_column_lines(cls, dataset_columns) -> List[str]:
        """Format trusted dataset metadata for a correction prompt."""

        columns = cls._safe_dataset_columns(dataset_columns)
        if not columns:
            return ["- Schema metadata unavailable; do not invent columns"]
        return [f"- {item['name']} ({item['type']})" for item in columns]

    @classmethod
    def _effective_allowed_tables(
        cls,
        dataset_table: Optional[str],
        allowed_tables: Optional[Iterable[str]],
    ) -> Optional[List[str]]:
        """Resolve correction allowlists without an empty-list demo fallback."""

        if allowed_tables is None:
            return [cls._safe_table_identifier(dataset_table)] if dataset_table else None

        raw_tables = [allowed_tables] if isinstance(allowed_tables, str) else list(allowed_tables)
        normalized = [cls._safe_table_identifier(item) for item in raw_tables]
        if dataset_table is not None:
            selected = cls._safe_table_identifier(dataset_table)
            if normalized != [selected]:
                raise ValueError(
                    "Uploaded dataset correction requires exactly the selected table in allowed_tables"
                )
        return normalized

    @staticmethod
    def _is_network_error(error_text: str) -> bool:
        """
        Detect common network and DNS failures.
        """

        return (
            "getaddrinfo failed" in error_text
            or "name resolution" in error_text
            or "dns" in error_text
            or "connection" in error_text
            or "timed out" in error_text
            or "timeout" in error_text
            or "network" in error_text
        )

    @staticmethod
    def _safe_rag_context(question: str) -> str:
        """
        Retrieve RAG context safely.

        If RAG fails, return an empty string.
        SQL generation should continue using the normal prompt.
        """

        try:
            return get_rag_context(question) or ""
        except Exception:
            return ""

    @staticmethod
    def _extract_rag_sources(rag_context: str) -> List[str]:
        """
        Extract source file names from retrieved RAG context.

        Example expected line:
        Source: schema_context.md | Chunk: 1
        """

        if not rag_context:
            return []

        sources: List[str] = []

        for line in rag_context.splitlines():
            line = line.strip()

            if line.startswith("Source:"):
                source_part = line.replace("Source:", "").strip()
                source_name = source_part.split("|")[0].strip()

                if source_name and source_name not in sources:
                    sources.append(source_name)

        return sources

    @staticmethod
    def predefined_sql(user_question: str):
        """
        Reliable fallback for important demo questions.

        Main final flow is:
        Question + Memory + RAG Context -> LangChain/Gemini -> SQL

        This fallback is only used if model generation fails.
        """

        q = re.sub(r"\s+", " ", user_question.lower()).strip()

        if "total revenue" in q or (
            "show revenue" in q and "by" not in q and "trend" not in q
        ):
            return """
            SELECT COALESCE(SUM(quantity * price), 0) AS total_revenue
            FROM order_items;
            """

        if (
            ("top" in q or "highest" in q or "best" in q)
            and "product" in q
            and "revenue" in q
        ):
            limit_match = re.search(r"\btop\s+(\d+)\b", q)
            limit = int(limit_match.group(1)) if limit_match else 5

            return f"""
            SELECT
                p.product_name,
                SUM(oi.quantity * oi.price) AS revenue
            FROM order_items oi
            JOIN products p
                ON oi.product_id = p.product_id
            GROUP BY p.product_name
            ORDER BY revenue DESC
            LIMIT {limit};
            """

        if "revenue" in q and "category" in q:
            return """
            SELECT
                p.category,
                SUM(oi.quantity * oi.price) AS revenue
            FROM order_items oi
            JOIN products p
                ON oi.product_id = p.product_id
            GROUP BY p.category
            ORDER BY revenue DESC;
            """

        if "revenue" in q and "country" in q:
            return """
            SELECT
                c.country,
                SUM(oi.quantity * oi.price) AS revenue
            FROM order_items oi
            JOIN orders o
                ON oi.order_id = o.order_id
            JOIN customers c
                ON o.customer_id = c.customer_id
            GROUP BY c.country
            ORDER BY revenue DESC;
            """

        if "revenue" in q and ("month" in q or "trend" in q):
            return """
            SELECT
                DATE_TRUNC('month', o.order_date)::date AS month,
                SUM(oi.quantity * oi.price) AS revenue
            FROM orders o
            JOIN order_items oi
                ON o.order_id = oi.order_id
            GROUP BY month
            ORDER BY month;
            """

        if (
            "total orders" in q
            or "how many orders" in q
            or "count orders" in q
        ) and "country" not in q and "status" not in q:
            return """
            SELECT COUNT(*) AS total_orders
            FROM orders;
            """

        if "orders" in q and "country" in q:
            return """
            SELECT
                c.country,
                COUNT(o.order_id) AS total_orders
            FROM customers c
            JOIN orders o
                ON c.customer_id = o.customer_id
            GROUP BY c.country
            ORDER BY total_orders DESC;
            """

        if "orders" in q and "status" in q:
            return """
            SELECT
                status,
                COUNT(*) AS total_orders
            FROM orders
            GROUP BY status
            ORDER BY total_orders DESC;
            """

        if (
            ("top" in q or "highest" in q or "best" in q)
            and "customer" in q
            and ("spending" in q or "spent" in q or "revenue" in q)
        ):
            limit_match = re.search(r"\btop\s+(\d+)\b", q)
            limit = int(limit_match.group(1)) if limit_match else 5

            return f"""
            SELECT
                o.customer_id,
                SUM(oi.quantity * oi.price) AS total_spent
            FROM orders o
            JOIN order_items oi
                ON o.order_id = oi.order_id
            GROUP BY o.customer_id
            ORDER BY total_spent DESC
            LIMIT {limit};
            """

        if (
            "total customers" in q
            or "how many customers" in q
            or "count customers" in q
        ):
            return """
            SELECT COUNT(*) AS total_customers
            FROM customers;
            """

        if (
            "total products" in q
            or "how many products" in q
            or "count products" in q
        ):
            return """
            SELECT COUNT(*) AS total_products
            FROM products;
            """

        if "show all orders" in q or "list all orders" in q:
            return """
            SELECT
                order_id,
                customer_id,
                order_date,
                status
            FROM orders
            ORDER BY order_id DESC;
            """

        if "show all products" in q or "list all products" in q:
            return """
            SELECT
                product_id,
                product_name,
                category
            FROM products
            ORDER BY product_id;
            """

        if (
            "product" in q
            and "revenue" in q
            and "average" in q
            and ("greater" in q or "above" in q or "more than" in q)
        ):
            return """
            WITH product_revenue AS (
                SELECT
                    p.product_id,
                    p.product_name,
                    p.category,
                    SUM(oi.quantity * oi.price) AS total_revenue
                FROM products p
                JOIN order_items oi
                    ON p.product_id = oi.product_id
                GROUP BY p.product_id, p.product_name, p.category
            )
            SELECT
                product_id,
                product_name,
                category,
                total_revenue
            FROM product_revenue
            WHERE total_revenue > (
                SELECT AVG(total_revenue)
                FROM product_revenue
            )
            ORDER BY total_revenue DESC;
            """
        if (
            "customer" in q
            and "order" in q
            and "average" in q
            and ("more" in q or "greater" in q or "above" in q)
        ):
            return """
            WITH customer_order_counts AS (
                SELECT
                    c.customer_id,
                    c.country,
                    c.signup_date,
                    COUNT(o.order_id) AS order_count
                FROM customers c
                JOIN orders o
                    ON c.customer_id = o.customer_id
                GROUP BY
                    c.customer_id,
                    c.country,
                    c.signup_date
            ),
            average_orders AS (
                SELECT
                    AVG(order_count) AS avg_orders_per_customer
                FROM customer_order_counts
            )
            SELECT
                coc.customer_id,
                coc.country,
                coc.signup_date,
                coc.order_count
            FROM customer_order_counts coc
            CROSS JOIN average_orders ao
            WHERE coc.order_count > ao.avg_orders_per_customer
            ORDER BY coc.order_count DESC;
            """

        return None

    @staticmethod
    def _clean(text: str) -> str:
        """
        Clean LLM output and extract SQL only.
        Supports SELECT and WITH queries.
        """

        if not text:
            raise ValueError("LLM returned empty response")

        text = text.strip()
        text = re.sub(r"```sql", "", text, flags=re.IGNORECASE)
        text = text.replace("```", "").strip()

        match = re.search(
            r"\b(WITH|SELECT)\b[\s\S]*?;",
            text,
            flags=re.IGNORECASE
        )

        if match:
            sql = match.group(0).strip()
        else:
            lines = text.splitlines()
            collecting = False
            parts = []

            for line in lines:
                clean_line = line.strip()
                upper_line = clean_line.upper()

                if upper_line.startswith("SELECT") or upper_line.startswith("WITH"):
                    collecting = True

                if collecting:
                    parts.append(clean_line)

            sql = " ".join(parts) if parts else text.strip()

        sql = re.sub(r"\s+", " ", sql).strip()

        if sql and not sql.endswith(";"):
            sql += ";"

        return sql

    @staticmethod
    def _validate(sql: str, allowed_tables: Optional[Iterable[str]] = None):
        """
        Validate SQL using project SQL validator.
        """

        is_valid, message = validate_sql(sql, allowed_tables=allowed_tables)

        if not is_valid:
            raise ValueError(message)


def generate_sql(question):
    """
    Wrapper function for older modules.
    """

    generator = SQLGenerator()
    return generator.generate_sql(question)


if __name__ == "__main__":
    gen = SQLGenerator()

    questions = [
        "show revenue by category",
        "show top 5 products by revenue",
        "show revenue trend by month",
        "show all products whose revenue is greater than the average revenue of all products",
    ]

    for q in questions:
        print(f"\nQ: {q}")

        try:
            print(f"SQL: {gen.generate_sql(q)}")
        except Exception as e:
            print(f"ERROR: {e}")
