"""Small, defensive HTTP client used by the Streamlit application.

The UI deliberately talks to FastAPI for every private operation.  It never
opens database connections or server-side artifact paths directly.
"""

from __future__ import annotations

import os
import re
import uuid
from typing import Any

import requests
from dotenv import load_dotenv


load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
DEFAULT_TIMEOUT = float(os.getenv("API_TIMEOUT_SECONDS", "20"))
QUERY_TIMEOUT = float(os.getenv("API_QUERY_TIMEOUT_SECONDS", "120"))
UPLOAD_TIMEOUT = float(os.getenv("API_UPLOAD_TIMEOUT_SECONDS", "120"))

_SESSION = requests.Session()
_SESSION.headers.update({"Accept": "application/json", "User-Agent": "agentic-sql-streamlit/3"})


def _error_message(payload: Any, fallback: str) -> str:
    """Extract a safe human-readable error from FastAPI response variants."""

    if not isinstance(payload, dict):
        return fallback
    nested = payload.get("error")
    if isinstance(nested, dict) and nested.get("message"):
        return str(nested["message"])
    if isinstance(nested, str) and nested:
        return nested
    detail = payload.get("detail")
    if isinstance(detail, str) and detail:
        return detail
    if isinstance(detail, dict) and detail.get("message"):
        return str(detail["message"])
    if isinstance(detail, list):
        messages = []
        for item in detail[:4]:
            if isinstance(item, dict) and item.get("msg"):
                location = ".".join(str(part) for part in item.get("loc", []) if part != "body")
                messages.append(f"{location}: {item['msg']}" if location else str(item["msg"]))
        if messages:
            return "; ".join(messages)
    return fallback


def _filename_from_headers(headers: requests.structures.CaseInsensitiveDict, fallback: str) -> str:
    disposition = headers.get("Content-Disposition", "")
    match = re.search(r"filename\*?=(?:UTF-8''|\"?)([^\";]+)", disposition, re.IGNORECASE)
    if not match:
        return fallback
    filename = match.group(1).strip().strip('"').replace("\\", "_").replace("/", "_")
    return filename or fallback


def _call(
    method: str,
    path: str,
    token: str | None = None,
    *,
    timeout: float | None = None,
    expect_bytes: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    """Call the API and normalize success, auth, validation, and network errors."""

    headers = dict(kwargs.pop("headers", {}) or {})
    headers["X-Request-ID"] = uuid.uuid4().hex
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = _SESSION.request(
            method,
            f"{API_BASE_URL}{path}",
            headers=headers,
            timeout=timeout or DEFAULT_TIMEOUT,
            **kwargs,
        )
    except requests.Timeout:
        return {
            "error": "The request took too long. The service may still be processing; please try again.",
            "status_code": 0,
            "error_code": "timeout",
        }
    except requests.RequestException:
        return {
            "error": "The analytics API is unavailable. Confirm the backend is running and try again.",
            "status_code": 0,
            "error_code": "connection_error",
        }

    request_id = response.headers.get("X-Request-ID")
    if expect_bytes and response.ok:
        content_type = response.headers.get("Content-Type", "application/octet-stream").split(";", 1)[0]
        return {
            "content": response.content,
            "content_type": content_type,
            "filename": _filename_from_headers(response.headers, "download"),
            "status_code": response.status_code,
            "request_id": request_id,
        }

    try:
        payload: Any = response.json()
    except ValueError:
        payload = {}

    if response.ok:
        if isinstance(payload, dict):
            return payload
        return {"data": payload}

    fallback = {
        400: "The request could not be completed.",
        401: "Your session is invalid or has expired.",
        403: "You do not have permission to perform this action.",
        404: "The requested resource was not found.",
        409: "That action conflicts with an existing record.",
        413: "The uploaded file is larger than the allowed limit.",
        415: "This file type is not supported.",
        422: "The submitted information could not be processed.",
        429: "Too many requests. Please wait and try again.",
        500: "The service encountered an unexpected error.",
        502: "An upstream AI service is temporarily unavailable.",
        503: "The service is temporarily unavailable.",
    }.get(response.status_code, "The request failed.")

    nested_error = payload.get("error", {}) if isinstance(payload, dict) else {}
    return {
        "error": _error_message(payload, fallback),
        "status_code": response.status_code,
        "error_code": nested_error.get("code") if isinstance(nested_error, dict) else None,
        "request_id": request_id or (nested_error.get("request_id") if isinstance(nested_error, dict) else None),
    }


# Authentication -----------------------------------------------------------------


def register_api(email: str, full_name: str, password: str) -> dict[str, Any]:
    return _call("POST", "/auth/register", json={"email": email, "full_name": full_name, "password": password})


def login_api(email: str, password: str) -> dict[str, Any]:
    return _call("POST", "/auth/login", json={"email": email, "password": password})


def me_api(token: str) -> dict[str, Any]:
    return _call("GET", "/auth/me", token)


def forgot_password_api(email: str) -> dict[str, Any]:
    return _call("POST", "/auth/forgot-password", json={"email": email})


def reset_password_api(reset_token: str, new_password: str) -> dict[str, Any]:
    return _call(
        "POST",
        "/auth/reset-password",
        json={"token": reset_token, "new_password": new_password},
    )


def change_password_api(token: str, current_password: str, new_password: str) -> dict[str, Any]:
    return _call(
        "POST",
        "/auth/change-password",
        token,
        json={"current_password": current_password, "new_password": new_password},
    )


# Datasets -----------------------------------------------------------------------


def datasets_api(token: str) -> dict[str, Any]:
    return _call("GET", "/datasets", token)


def dataset_api(token: str, dataset_id: int) -> dict[str, Any]:
    return _call("GET", f"/datasets/{dataset_id}", token)


def dataset_preview_api(token: str, dataset_id: int, limit: int = 25) -> dict[str, Any]:
    return _call("GET", f"/datasets/{dataset_id}/preview", token, params={"limit": limit})


def dataset_download_api(token: str, dataset_id: int) -> dict[str, Any]:
    return _call("GET", f"/datasets/{dataset_id}/download", token, expect_bytes=True, timeout=UPLOAD_TIMEOUT)


def rename_dataset_api(token: str, dataset_id: int, dataset_name: str) -> dict[str, Any]:
    return _call("PUT", f"/datasets/{dataset_id}", token, json={"dataset_name": dataset_name})


def delete_dataset_api(token: str, dataset_id: int) -> dict[str, Any]:
    return _call("DELETE", f"/datasets/{dataset_id}", token)


def upload_dataset_api(
    token: str,
    name: str,
    uploaded_file: Any,
    sheet_name: str | None = None,
) -> dict[str, Any]:
    mime = getattr(uploaded_file, "type", None) or "application/octet-stream"
    fields = {"dataset_name": name, "sheet_name": sheet_name or ""}
    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), mime)}
    return _call("POST", "/datasets/upload", token, data=fields, files=files, timeout=UPLOAD_TIMEOUT)


# Query, history, and reports ----------------------------------------------------


def run_query_api(token: str, dataset_id: int | str, question: str | None = None) -> dict[str, Any]:
    """Run an uploaded-dataset query; two arguments remain a demo compatibility form."""

    if question is None:
        return run_demo_query_api(token, str(dataset_id))
    return _call(
        "POST",
        "/query",
        token,
        json={"dataset_id": int(dataset_id), "question": question},
        timeout=QUERY_TIMEOUT,
    )


def run_demo_query_api(token: str, question: str) -> dict[str, Any]:
    return _call("POST", "/query/demo", token, json={"question": question}, timeout=QUERY_TIMEOUT)


def history_api(token: str, dataset_id: int | None = None, **filters: Any) -> dict[str, Any]:
    path = f"/history/{dataset_id}" if dataset_id is not None else "/history"
    params = {key: value for key, value in filters.items() if value not in (None, "")}
    return _call("GET", path, token, params=params or None)


def delete_history_api(token: str, history_id: int) -> dict[str, Any]:
    return _call("DELETE", f"/history/item/{history_id}", token)


def clear_history_api(token: str, dataset_id: int | None = None) -> dict[str, Any]:
    params = {"dataset_id": dataset_id} if dataset_id is not None else None
    return _call("DELETE", "/history", token, params=params)


def download_report_api(token: str, history_id: int) -> dict[str, Any]:
    return _call("GET", f"/reports/{history_id}/download", token, expect_bytes=True, timeout=UPLOAD_TIMEOUT)


# Demo dashboard -----------------------------------------------------------------


def health_api() -> dict[str, Any]:
    return _call("GET", "/health")


def dashboard_metrics_api(token: str) -> dict[str, Any]:
    return _call("GET", "/dashboard/metrics", token)


def revenue_by_category_api(token: str) -> dict[str, Any]:
    return _call("GET", "/dashboard/revenue-by-category", token)


def top_products_api(token: str) -> dict[str, Any]:
    return _call("GET", "/dashboard/top-products", token)


def orders_by_status_api(token: str) -> dict[str, Any]:
    return _call("GET", "/dashboard/orders-by-status", token)


def revenue_by_country_api(token: str) -> dict[str, Any]:
    return _call("GET", "/dashboard/revenue-by-country", token)


def monthly_revenue_api(token: str) -> dict[str, Any]:
    return _call("GET", "/dashboard/monthly-revenue", token)


# Compatibility aliases used by the original dashboard module.
get_dashboard_metrics = dashboard_metrics_api
get_revenue_by_category = revenue_by_category_api
get_top_products = top_products_api
get_orders_by_status = orders_by_status_api
get_revenue_by_country = revenue_by_country_api
get_monthly_revenue = monthly_revenue_api
get_history_api = history_api
