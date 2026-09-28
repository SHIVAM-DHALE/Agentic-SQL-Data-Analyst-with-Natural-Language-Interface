# #"""
# agent_controller.py
# -------------------
# Coordinates the natural-language analytics workflow:
# question validation, SQL generation, SQL validation, execution, correction,
# insight generation, chart generation, report export, and memory retrieval.
# """

# import logging
# import socket
# import uuid
# from typing import Any, Dict, List, Optional, Tuple

# from agent1.chart_generator import generate_chart
# from agent1.correction_loop import fix_sql
# from agent1.export_report import export_session
# from agent1.insights import generate_insights
# from agent1.memory import get_history, get_history_text, save_ai_message, save_message
# from agent1.tools import execute_sql
# from evals.sql_quality_evaluator import evaluate_sql_quality

# from practice.sql_generator import SQLGenerator
# from practice.sql_validator import validate_sql


# logger = logging.getLogger(__name__)

# BUSINESS_QUERY_KEYWORDS = {
#     "show", "list", "total", "count", "revenue", "sales", "product",
#     "products", "customer", "customers", "order", "orders", "category",
#     "country", "highest", "lowest", "average", "maximum", "minimum",
#     "top", "latest", "status", "spending", "purchase", "purchased",
#     "quantity", "price", "value", "trend", "summary", "share",
#     "distribution", "month", "date", "growth"
# }


# def is_business_query(question: str) -> bool:
#     """Return True when a question appears related to the available business data."""
#     if not question:
#         return False

#     question_lower = question.lower()
#     return any(keyword in question_lower for keyword in BUSINESS_QUERY_KEYWORDS)


# def is_network_error(error: Exception) -> bool:
#     """Detect common network and DNS failures from model/API calls."""
#     error_text = str(error).lower()

#     return (
#         isinstance(error, socket.gaierror)
#         or "getaddrinfo failed" in error_text
#         or "name resolution" in error_text
#         or "dns" in error_text
#         or "connection" in error_text
#         or "timed out" in error_text
#         or "timeout" in error_text
#         or "network" in error_text
#     )


# def error_response(message: str, technical_detail: Optional[str] = None) -> Dict[str, Any]:
#     """Create a consistent error response."""
#     response = {"error": message}

#     if technical_detail:
#         response["technical_detail"] = technical_detail

#     return response


# def normalize_question(question: str) -> str:
#     """Clean user input before processing."""
#     return " ".join(question.strip().split())


# def validate_or_correct_sql(
#     generator: SQLGenerator,
#     question: str,
#     sql: str,
#     validation_message: str
# ) -> str:
#     """Attempt to correct SQL after validation failure."""
#     logger.info("SQL validation failed. Attempting correction: %s", validation_message)

#     corrected_sql = fix_sql(
#         generator=generator,
#         question=question,
#         wrong_sql=sql,
#         error_message=validation_message
#     )

#     is_valid, message = validate_sql(corrected_sql)

#     if not is_valid:
#         raise ValueError(f"Corrected SQL is still invalid: {message}")

#     return corrected_sql


# def execute_with_correction(
#     generator: SQLGenerator,
#     question: str,
#     sql: str
# ) -> Tuple[str, List[str], List[tuple]]:
#     """Execute SQL and attempt one correction pass if execution fails."""
#     try:
#         columns, result = execute_sql(sql)
#         return sql, columns, result

#     except Exception as execution_error:
#         logger.warning("SQL execution failed. Attempting correction: %s", execution_error)

#         corrected_sql = fix_sql(
#             generator=generator,
#             question=question,
#             wrong_sql=sql,
#             error_message=str(execution_error)
#         )

#         is_valid, message = validate_sql(corrected_sql)

#         if not is_valid:
#             raise ValueError(
#                 f"Corrected SQL after execution error is invalid: {message}"
#             )

#         columns, result = execute_sql(corrected_sql)
#         return corrected_sql, columns, result


# def build_success_response(
#     question: str,
#     sql: str,
#     columns: List[str],
#     result: List[tuple],
#     insight: str,
#     chart_path: Optional[str],
#     report_path: Optional[str],
#     history: List[Any],
#     quality_eval: Optional[Dict[str, Any]] = None
# ) -> Dict[str, Any]:
#     """Create a consistent successful analysis response."""
#     return {
#         "run_id": uuid.uuid4().hex[:8],
#         "question": question,
#         "sql": sql,
#         "columns": columns,
#         "result": result,
#         "insight": insight,
#         "chart_path": chart_path,
#         "report_path": report_path,
#         "history": history,
#         "quality_eval": quality_eval,
#     }


# def process_question(question: str) -> Dict[str, Any]:
#     """Run the full analytics workflow for one user question."""

#     if not question or not question.strip():
#         return error_response("Please enter a valid business question.")

#     question = normalize_question(question)

#     if not is_business_query(question):
#         return error_response(
#             "This does not look like a question about the available business data. "
#             "Try asking something like 'show revenue by category' or "
#             "'show top 5 products by revenue'."
#         )

#     try:
#         conversation_history = get_history_text()
#     except Exception as exc:
#         logger.warning("Unable to fetch conversation history for prompt: %s", exc)
#         conversation_history = ""

#     try:
#         generator = SQLGenerator()
#         sql = generator.generate_sql(question, conversation_history)

#     except Exception as exc:
#         if is_network_error(exc):
#             return error_response(
#                 "The AI service is not reachable right now. Please check internet, "
#                 "DNS, VPN/proxy settings, and the configured API key.",
#                 technical_detail=str(exc)
#             )

#         return error_response(
#             "Unable to generate SQL for this question.",
#             technical_detail=str(exc)
#         )

#     try:
#         save_message(question)
#     except Exception as exc:
#         logger.warning("Unable to save question to memory: %s", exc)

#     try:
#         is_valid, validation_message = validate_sql(sql)

#         if not is_valid:
#             sql = validate_or_correct_sql(
#                 generator=generator,
#                 question=question,
#                 sql=sql,
#                 validation_message=validation_message
#             )

#     except Exception as exc:
#         return error_response(
#             "SQL validation failed and automatic correction was unsuccessful.",
#             technical_detail=str(exc)
#         )

#     try:
#         sql, columns, result = execute_with_correction(generator, question, sql)

#     except Exception as exc:
#         return error_response(
#             "The query could not be executed after automatic correction.",
#             technical_detail=str(exc)
#         )

#     try:
#         quality_eval = evaluate_sql_quality(
#             question=question,
#             sql=sql,
#             actual_columns=columns
#         )

#     except Exception as exc:
#         logger.warning("SQL quality evaluation failed: %s", exc)
#         quality_eval = {
#             "score": 0,
#             "confidence": "Unknown",
#             "passed": False,
#             "detected_intent": "unknown",
#             "detected_label": "Unknown request",
#             "explanation": [],
#             "recommendation": (
#                 "The SQL ran, but the quality evaluation could not be completed. "
#                 "Review the generated SQL or re-run the question."
#             ),
#             "next_steps": [
#                 "Check whether the returned columns match your question.",
#                 "Rephrase the question with a clear metric and grouping if needed.",
#                 "Use the result only after reviewing it.",
#             ],
#             "checks": [
#                 {
#                     "name": "SQL Quality Evaluation",
#                     "passed": False,
#                     "message": "Quality evaluation could not be completed."
#                 }
#             ]
#         }

#     try:
#         insight = generate_insights(question, columns, result)

#     except Exception as exc:
#         logger.warning("Insight generation failed: %s", exc)
#         insight = "The query ran successfully, but an insight summary could not be generated."

#     try:
#         chart_path = generate_chart(question, columns, result)

#     except Exception as exc:
#         logger.warning("Chart generation failed: %s", exc)
#         chart_path = None

#     try:
#         report_path = export_session(
#             question=question,
#             sql=sql,
#             columns=columns,
#             result=result,
#             insight=insight,
#             chart_path=chart_path
#         )

#     except TypeError:
#         report_path = export_session(
#             question,
#             sql,
#             columns,
#             result,
#             insight,
#             chart_path
#         )

#     except Exception as exc:
#         logger.warning("Report export failed: %s", exc)
#         report_path = None

#     try:
#         save_ai_message(f"SQL: {sql}\nInsight: {insight}")
#         history = get_history()

#     except Exception as exc:
#         logger.warning("Unable to fetch conversation history: %s", exc)
#         history = []

#     return build_success_response(
#         question=question,
#         sql=sql,
#         columns=columns,
#         result=result,
#         insight=insight,
#         chart_path=chart_path,
#         report_path=report_path,
#         history=history,
#         quality_eval=quality_eval
#     )


# if __name__ == "__main__":
#     response = process_question("show revenue by category")
#     print(response)
"""
agent_controller.py
-------------------
Coordinates the natural-language analytics workflow:
question validation, unsafe intent blocking, SQL generation, SQL validation,
execution, correction, insight generation, chart generation, report export,
memory retrieval, SQL quality evaluation, and RAG metadata return.
"""

import logging
import re
import socket
import uuid
from typing import Any, Dict, List, Optional, Tuple

from agent1.chart_generator import generate_chart
from agent1.correction_loop import fix_sql
from agent1.export_report import export_session
from agent1.insights import generate_insights
from agent1.memory import get_history, get_history_text, save_ai_message, save_message
from agent1.tools import execute_sql

from practice.sql_generator import SQLGenerator
from practice.sql_validator import validate_sql

try:
    from evals.sql_quality_evaluator import evaluate_sql_quality
except Exception:
    evaluate_sql_quality = None


logger = logging.getLogger(__name__)


BUSINESS_QUERY_KEYWORDS = {
    "show", "list", "total", "count", "revenue", "sales", "product",
    "products", "customer", "customers", "order", "orders", "category",
    "country", "highest", "lowest", "average", "maximum", "minimum",
    "top", "latest", "status", "spending", "purchase", "purchased",
    "quantity", "price", "value", "trend", "summary", "share",
    "distribution", "month", "date", "growth", "completed"
}


UNSAFE_INTENT_PATTERNS = [
    r"\binsert\b",
    r"\binsert\s+into\b",
    r"\badd\s+new\b",
    r"\badd\s+a\s+new\b",
    r"\bcreate\s+new\b",
    r"\bupdate\b",
    r"\bdelete\b",
    r"\bdrop\b",
    r"\balter\b",
    r"\btruncate\b",
    r"\bremove\b",
    r"\breplace\b",
    r"\bmerge\b",
    r"\bgrant\b",
    r"\brevoke\b",
    r"\bmodify\b",
    r"\bchange\b",
    r"\bset\b",
    r"\bclear\b",
    r"\berase\b",
]


def is_business_query(question: str) -> bool:
    """
    Return True when a question appears related to the available business data.
    """

    if not question:
        return False

    question_lower = question.lower()
    return any(keyword in question_lower for keyword in BUSINESS_QUERY_KEYWORDS)


def is_unsafe_user_intent(question: str) -> bool:
    """
    Detect user requests that try to modify database data or schema.

    This checks the original user question before SQL generation.
    It prevents unsafe write requests from being converted into harmless SELECT queries.

    Examples blocked:
    - insert a new customer
    - update product price
    - delete all orders
    - drop products table
    - alter customers table
    """

    if not question:
        return False

    question_lower = question.lower()

    for pattern in UNSAFE_INTENT_PATTERNS:
        if re.search(pattern, question_lower):
            return True

    return False


def is_network_error(error: Exception) -> bool:
    """
    Detect common network and DNS failures from model/API calls.
    """

    error_text = str(error).lower()

    return (
        isinstance(error, socket.gaierror)
        or "getaddrinfo failed" in error_text
        or "name resolution" in error_text
        or "dns" in error_text
        or "connection" in error_text
        or "timed out" in error_text
        or "timeout" in error_text
        or "network" in error_text
    )


def error_response(message: str, technical_detail: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a consistent error response.
    """

    response = {"error": message}

    if technical_detail:
        response["technical_detail"] = technical_detail

    return response


def normalize_question(question: str) -> str:
    """
    Clean user input before processing.
    """

    return " ".join(question.strip().split())


def validate_or_correct_sql(
    generator: SQLGenerator,
    question: str,
    sql: str,
    validation_message: str
) -> str:
    """
    Attempt to correct SQL after validation failure.
    """

    logger.info("SQL validation failed. Attempting correction: %s", validation_message)

    corrected_sql = fix_sql(
        generator=generator,
        question=question,
        wrong_sql=sql,
        error_message=validation_message
    )

    is_valid, message = validate_sql(corrected_sql)

    if not is_valid:
        raise ValueError(f"Corrected SQL is still invalid: {message}")

    return corrected_sql


def execute_with_correction(
    generator: SQLGenerator,
    question: str,
    sql: str
) -> Tuple[str, List[str], List[tuple]]:
    """
    Execute SQL and attempt one correction pass if execution fails.
    """

    try:
        columns, result = execute_sql(sql)
        return sql, columns, result

    except Exception as execution_error:
        logger.warning("SQL execution failed. Attempting correction: %s", execution_error)

        corrected_sql = fix_sql(
            generator=generator,
            question=question,
            wrong_sql=sql,
            error_message=str(execution_error)
        )

        is_valid, message = validate_sql(corrected_sql)

        if not is_valid:
            raise ValueError(
                f"Corrected SQL after execution error is invalid: {message}"
            )

        columns, result = execute_sql(corrected_sql)
        return corrected_sql, columns, result


def quality_eval_fallback(
    message: str = "Quality evaluation could not be completed."
) -> Dict[str, Any]:
    """
    Fallback response when SQL quality evaluation is unavailable or fails.
    """

    return {
        "score": None,
        "confidence": "Unavailable",
        "passed": False,
        "available": False,
        "detected_intent": "unknown",
        "detected_label": "Unknown request",
        "explanation": [],
        "recommendation": (
            "The SQL ran, but the quality evaluation could not be completed. "
            "Review the generated SQL or re-run the question."
        ),
        "next_steps": [
            "Check whether the returned columns match your question.",
            "Rephrase the question with a clear metric and grouping if needed.",
            "Use the result only after reviewing it.",
        ],
        "checks": [
            {
                "name": "SQL Quality Evaluation",
                "passed": False,
                "message": message,
            }
        ],
    }


def run_quality_eval(
    question: str,
    sql: str,
    columns: List[str]
) -> Dict[str, Any]:
    """
    Run SQL quality evaluation safely.

    Supports both possible evaluator signatures:
    - evaluate_sql_quality(question=..., sql=..., actual_columns=...)
    - evaluate_sql_quality(question=..., sql=..., columns=...)
    """

    if evaluate_sql_quality is None:
        return quality_eval_fallback(
            "Quality evaluator module is not available."
        )

    try:
        return evaluate_sql_quality(
            question=question,
            sql=sql,
            actual_columns=columns
        )

    except TypeError:
        return evaluate_sql_quality(
            question=question,
            sql=sql,
            columns=columns
        )


def build_success_response(
    question: str,
    sql: str,
    columns: List[str],
    result: List[tuple],
    insight: str,
    chart_path: Optional[str],
    report_path: Optional[str],
    history: List[Any],
    quality_eval: Optional[Dict[str, Any]] = None,
    rag_used: bool = False,
    rag_sources: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Create a consistent successful analysis response.

    RAG metadata is intentionally limited:
    - rag_used tells whether retrieved RAG context was used.
    - rag_sources shows source file names.
    - full RAG context is not returned to frontend.
    """

    return {
        "run_id": uuid.uuid4().hex[:8],
        "question": question,
        "sql": sql,
        "columns": columns,
        "result": result,
        "insight": insight,
        "chart_path": chart_path,
        "report_path": report_path,
        "history": history,
        "quality_eval": quality_eval,
        "rag_used": rag_used,
        "rag_sources": rag_sources or [],
    }


def process_question(
    question: str,
    conversation_history_override: Optional[str] = None,
    persist_memory: bool = True,
) -> Dict[str, Any]:
    """
    Run the full analytics workflow for one user question.
    """

    if not question or not question.strip():
        return error_response("Please enter a valid business question.")

    question = normalize_question(question)

    # Step 1: Block unsafe user intent before SQL generation.
    # This prevents INSERT/UPDATE/DELETE/DROP requests from being converted into SELECT.
    if is_unsafe_user_intent(question):
        return error_response(
            "This request is blocked because it asks to modify the database. "
            "Only read-only SELECT analytics questions are allowed. "
            "Try asking questions like 'show revenue by category' or "
            "'show top 5 products by revenue'."
        )

    # Step 2: Check whether question belongs to available business data.
    if not is_business_query(question):
        return error_response(
            "This does not look like a question about the available business data. "
            "Try asking something like 'show revenue by category' or "
            "'show top 5 products by revenue'."
        )

    # Step 3: Fetch conversation history for contextual SQL generation.
    if conversation_history_override is not None:
        conversation_history = conversation_history_override
    elif persist_memory:
        try:
            conversation_history = get_history_text()
        except Exception as exc:
            logger.warning("Unable to fetch conversation history for prompt: %s", exc)
            conversation_history = ""
    else:
        conversation_history = ""

    # Step 4: Generate SQL using LangChain/Gemini + RAG.
    try:
        generator = SQLGenerator()
        sql = generator.generate_sql(question, conversation_history)

    except Exception as exc:
        if is_network_error(exc):
            return error_response(
                "The AI service is not reachable right now. Please check internet, "
                "DNS, VPN/proxy settings, and the configured API key.",
                technical_detail=str(exc)
            )

        return error_response(
            "Unable to generate SQL for this question.",
            technical_detail=str(exc)
        )

    # Step 5: Save user question to memory.
    if persist_memory:
        try:
            save_message(question)
        except Exception as exc:
            logger.warning("Unable to save question to memory: %s", exc)

    # Step 6: Validate generated SQL and correct if needed.
    try:
        is_valid, validation_message = validate_sql(sql)

        if not is_valid:
            sql = validate_or_correct_sql(
                generator=generator,
                question=question,
                sql=sql,
                validation_message=validation_message
            )

    except Exception as exc:
        return error_response(
            "SQL validation failed and automatic correction was unsuccessful.",
            technical_detail=str(exc)
        )

    # Step 7: Execute SQL and correct if execution fails.
    try:
        sql, columns, result = execute_with_correction(generator, question, sql)

    except Exception as exc:
        return error_response(
            "The query could not be executed after automatic correction.",
            technical_detail=str(exc)
        )

    # Step 8: Run SQL quality evaluation.
    try:
        quality_eval = run_quality_eval(
            question=question,
            sql=sql,
            columns=columns
        )

    except Exception as exc:
        logger.warning("SQL quality evaluation failed: %s", exc)
        quality_eval = quality_eval_fallback(
            "Quality evaluation could not be completed."
        )

    # Step 9: Generate business insight.
    try:
        insight = generate_insights(question, columns, result)

    except Exception as exc:
        logger.warning("Insight generation failed: %s", exc)
        insight = "The query ran successfully, but an insight summary could not be generated."

    # Step 10: Generate chart.
    try:
        chart_path = generate_chart(question, columns, result)

    except Exception as exc:
        logger.warning("Chart generation failed: %s", exc)
        chart_path = None

    # Step 11: Export report.
    try:
        report_path = export_session(
            question=question,
            sql=sql,
            columns=columns,
            result=result,
            insight=insight,
            chart_path=chart_path
        )

    except TypeError:
        report_path = export_session(
            question,
            sql,
            columns,
            result,
            insight,
            chart_path
        )

    except Exception as exc:
        logger.warning("Report export failed: %s", exc)
        report_path = None

    # Step 12: Save AI response and fetch history.
    if persist_memory:
        try:
            save_ai_message(f"SQL: {sql}\nInsight: {insight}")
            history = get_history()
        except Exception as exc:
            logger.warning("Unable to fetch conversation history: %s", exc)
            history = []
    else:
        history = []

    # Step 13: Return final response with safe RAG metadata.
    return build_success_response(
        question=question,
        sql=sql,
        columns=columns,
        result=result,
        insight=insight,
        chart_path=chart_path,
        report_path=report_path,
        history=history,
        quality_eval=quality_eval,
        rag_used=getattr(generator, "last_rag_used", False),
        rag_sources=getattr(generator, "last_rag_sources", []),
    )


if __name__ == "__main__":
    response = process_question("show revenue by category")
    print(response)
