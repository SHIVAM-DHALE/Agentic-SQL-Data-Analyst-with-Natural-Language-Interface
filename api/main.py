"""Authenticated multi-user Agentic SQL Analytics API."""
import io
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from psycopg2 import sql as pg_sql
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from agent1.agent_controller import is_unsafe_user_intent, process_question, run_quality_eval
from agent1.chart_generator import generate_chart
from agent1.export_report import export_session
from agent1.insights import generate_insights
from agent1.tools import DB_CONFIG, execute_sql
from api.auth import router as auth_router
from api.dependencies import get_current_user, get_db
from database.user_models import Dataset, QueryHistory, User, create_tables
from practice.sql_generator import SQLGenerator
from practice.sql_validator import validate_sql

import psycopg2


def _positive_env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


MAX_UPLOAD_BYTES = _positive_env_int("MAX_UPLOAD_MB", 20) * 1024 * 1024
MAX_UPLOAD_ROWS = _positive_env_int("MAX_UPLOAD_ROWS", 100_000)
PREVIEW_ROW_LIMIT = 100
RESERVED_COLUMN_NAMES = {
    "all", "alter", "and", "as", "call", "copy", "create", "delete", "do", "drop",
    "from", "grant", "group", "insert", "into", "join", "limit", "merge", "offset",
    "order", "replace", "revoke", "select", "table", "truncate", "union", "update", "where", "with",
}
logger = logging.getLogger("agentic_sql.api")
BASE_DIR = Path(__file__).resolve().parent.parent
EXPORT_DIR = (BASE_DIR / "exports").resolve()


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_tables()
    yield


app = FastAPI(
    title="Agentic SQL Data Analyst API",
    description="Authenticated, read-only natural-language analytics for demo and user datasets.",
    version="3.0.0",
    lifespan=lifespan,
)
cors_origins = [item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501").split(",") if item.strip()]
app.add_middleware(CORSMiddleware, allow_origins=cors_origins, allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Authorization", "Content-Type", "X-Request-ID"])
trusted_hosts = [item.strip() for item in os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if item.strip()]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)
app.include_router(auth_router)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled request failure", extra={"request_id": request_id, "path": request.url.path})
        response = JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "An unexpected server error occurred.", "request_id": request_id}})
    duration_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.1f}"
    logger.info("request_complete", extra={"request_id": request_id, "method": request.method,
                                           "path": request.url.path, "status_code": response.status_code,
                                           "duration_ms": round(duration_ms, 1)})
    return response


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", request.headers.get("X-Request-ID", ""))
    return JSONResponse(status_code=exc.status_code, headers=exc.headers,
                        content={"detail": exc.detail, "error": {"code": "request_error", "message": str(exc.detail), "request_id": request_id}})


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=jsonable_encoder({"detail": "Request validation failed", "error": {"code": "validation_error", "message": "Check the submitted fields.", "fields": exc.errors()}}))


class QueryRequest(BaseModel):
    dataset_id: int
    question: str = Field(min_length=1, max_length=2000)


class DemoQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class RenameDatasetRequest(BaseModel):
    dataset_name: str = Field(min_length=1, max_length=200)


def json_safe(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime, pd.Timestamp)):
        return value.isoformat()
    if type(value).__module__.startswith("numpy") and hasattr(value, "item"):
        return json_safe(value.item())
    if pd.isna(value) if not isinstance(value, (list, dict, tuple)) else False:
        return None
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    return value


def dataset_dict(item: Dataset) -> dict:
    return json_safe({
        "id": item.id,
        "dataset_name": item.dataset_name,
        "original_filename": item.original_filename,
        "file_type": getattr(item, "file_type", Path(item.original_filename).suffix.lstrip(".").lower()),
        "columns": item.columns_json,
        "column_count": getattr(item, "column_count", len(item.columns_json or [])),
        "row_count": item.row_count,
        "profile": getattr(item, "profile_json", None),
        "created_at": item.created_at,
        "updated_at": getattr(item, "updated_at", None),
        "last_queried_at": getattr(item, "last_queried_at", None),
        "status": "ready",
    })


def owned_dataset(db: Session, dataset_id: int, user_id: int) -> Dataset:
    item = db.scalar(select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == user_id))
    if not item:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return item


def assert_internal_table_name(table_name: str) -> None:
    if not re.fullmatch(r"dataset_\d+_[a-f0-9]{10}", table_name):
        raise RuntimeError("Dataset metadata contains an invalid internal table identifier")


def clean_columns(columns) -> list[str]:
    used, output = set(), []
    for index, original in enumerate(columns, 1):
        name = re.sub(r"[^a-z0-9_]+", "_", str(original).strip().lower()).strip("_")
        name = re.sub(r"_+", "_", name) or f"column_{index}"
        if name[0].isdigit():
            name = f"col_{name}"
        if name in RESERVED_COLUMN_NAMES:
            name = f"col_{name}"
        base, suffix = name[:55], 2
        name = base
        while name in used:
            name = f"{base}_{suffix}"
            suffix += 1
        used.add(name)
        output.append(name)
    return output


def column_metadata(frame: pd.DataFrame) -> list[dict]:
    metadata = []
    for name, dtype in frame.dtypes.items():
        series = frame[name]
        metadata.append({
            "name": name,
            "type": str(dtype),
            "null_count": int(series.isna().sum()),
            "distinct_count": int(series.nunique(dropna=True)),
        })
    return metadata


def infer_dataframe_types(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply conservative date inference after pandas' numeric/boolean inference."""
    for column in frame.select_dtypes(include=["object", "string"]).columns:
        if not re.search(r"(?:^|_)(date|time|timestamp|datetime)(?:_|$)", column):
            continue
        non_null = frame[column].dropna()
        if non_null.empty:
            continue
        converted = pd.to_datetime(frame[column], errors="coerce")
        if float(converted.notna().sum()) / len(non_null) >= 0.9:
            frame[column] = converted
    return frame


def build_profile(frame: pd.DataFrame) -> dict:
    """Return bounded, JSON-safe profiling statistics for the dataset workspace."""
    warnings = []
    duplicate_rows = int(frame.duplicated().sum())
    if duplicate_rows:
        warnings.append(f"{duplicate_rows:,} duplicate rows detected")
    columns = []
    for name in frame.columns:
        series = frame[name]
        item = {
            "name": name,
            "type": str(series.dtype),
            "null_count": int(series.isna().sum()),
            "null_percent": round(float(series.isna().mean() * 100), 2),
            "distinct_count": int(series.nunique(dropna=True)),
        }
        if pd.api.types.is_numeric_dtype(series):
            clean = series.dropna()
            if not clean.empty:
                item["statistics"] = {
                    "min": json_safe(clean.min()), "max": json_safe(clean.max()),
                    "mean": json_safe(clean.mean()), "median": json_safe(clean.median()),
                }
        elif pd.api.types.is_datetime64_any_dtype(series):
            clean = series.dropna()
            if not clean.empty:
                item["date_range"] = {"min": json_safe(clean.min()), "max": json_safe(clean.max())}
        columns.append(item)
        if item["null_percent"] >= 25:
            warnings.append(f"{name} is {item['null_percent']}% empty")
        if re.search(r"(?:^|_)(email|phone|mobile|address|ssn|passport|credit_card)(?:_|$)", name):
            warnings.append(f"{name} may contain sensitive personal data; review access and retention policies")
    return json_safe({
        "row_count": int(len(frame)), "column_count": int(len(frame.columns)),
        "duplicate_rows": duplicate_rows, "columns": columns,
        "sample_rows": frame.head(10).where(pd.notna(frame.head(10)), None).to_dict(orient="records"),
        "warnings": warnings[:20],
    })


def deterministic_insight(columns, rows) -> str:
    if not rows:
        return "No records matched this question. Try broadening the filters or checking the selected dataset columns."
    if len(rows) == 1 and len(columns) == 1:
        return f"The query returned {columns[0].replace('_', ' ')}: {json_safe(rows[0][0])}."
    return f"The analysis returned {len(rows):,} rows across {len(columns)} columns. Review the visualization and result table for the strongest patterns."


def dynamic_quality(sql: str, table_name: str, columns: list[str]) -> dict:
    valid, validation_message = validate_sql(sql, allowed_tables=[table_name])
    checks = [
        {"name": "Read-only SQL safety", "passed": valid, "message": validation_message},
        {"name": "Selected-table isolation", "passed": valid, "message": "Only the selected dataset table is allowed." if valid else validation_message},
        {"name": "Query execution", "passed": True, "message": "PostgreSQL executed the statement successfully."},
        {"name": "Result schema", "passed": bool(columns), "message": f"Returned {len(columns)} result columns." if columns else "No result columns were returned."},
    ]
    score = round(sum(check["passed"] for check in checks) / len(checks) * 100, 2)
    return {"score": score, "confidence": "High" if score == 100 else "Medium", "passed": score >= 75, "available": True,
            "detected_intent": "dynamic_dataset_analysis", "detected_label": "Uploaded dataset analysis",
            "explanation": ["The SQL was evaluated against the selected dataset's physical table allowlist."],
            "recommendation": "Review the returned columns before using the result for a high-stakes decision.",
            "next_steps": ["Inspect the generated SQL.", "Confirm the result columns match the requested metric."], "checks": checks}


def set_if_mapped(instance, values: dict) -> None:
    for key, value in values.items():
        if hasattr(instance, key):
            setattr(instance, key, value)


@app.get("/")
def home():
    return {"message": "Agentic SQL Data Analyst API is running", "version": "2.0.0"}


@app.get("/health")
def health():
    try:
        execute_sql("SELECT 1;")
        return {"status": "healthy", "database": "connected"}
    except Exception as exc:
        logger.warning("Health database check failed: %s", type(exc).__name__)
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "unavailable"})


@app.post("/datasets/upload", status_code=201)
async def upload_dataset(dataset_name: str = Form(""), sheet_name: str = Form(""), file: UploadFile = File(...),
                         current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    filename = Path((file.filename or "upload").replace("\\", "/")).name
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in {"csv", "xlsx"}:
        raise HTTPException(status_code=415, detail="Only CSV and XLSX files are supported")
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Upload exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit")
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    try:
        frame = pd.read_csv(io.BytesIO(raw)) if extension == "csv" else pd.read_excel(
            io.BytesIO(raw), sheet_name=sheet_name.strip() or 0
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="The uploaded file could not be parsed") from exc
    if frame.empty or not len(frame.columns):
        raise HTTPException(status_code=400, detail="Uploaded file contains no data")
    if len(frame) > MAX_UPLOAD_ROWS:
        raise HTTPException(status_code=413, detail=f"Dataset exceeds the {MAX_UPLOAD_ROWS:,} row limit")
    frame.columns = clean_columns(frame.columns)
    frame = infer_dataframe_types(frame)
    table_name = f"dataset_{current_user.id}_{uuid.uuid4().hex[:10]}"
    profile = build_profile(frame)
    metadata = Dataset(user_id=current_user.id, dataset_name=(dataset_name.strip() or filename.rsplit(".", 1)[0])[:200],
                       original_filename=filename[:255], table_name=table_name,
                       columns_json=column_metadata(frame), row_count=len(frame))
    optional_values = {"file_type": extension, "column_count": len(frame.columns), "profile_json": profile}
    for key, value in optional_values.items():
        if hasattr(metadata, key):
            setattr(metadata, key, value)
    try:
        frame.to_sql(table_name, con=db.get_bind(), index=False, if_exists="fail", method="multi", chunksize=1000)
        db.add(metadata)
        db.commit()
        db.refresh(metadata)
    except Exception as exc:
        db.rollback()
        with db.get_bind().begin() as connection:
            connection.exec_driver_sql(f'DROP TABLE IF EXISTS "{table_name}"')
        raise HTTPException(status_code=500, detail="Dataset import failed") from exc
    return dataset_dict(metadata)


@app.get("/datasets")
def list_datasets(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(Dataset).where(Dataset.user_id == current_user.id).order_by(Dataset.created_at.desc())).all()
    return {"datasets": [dataset_dict(item) for item in items]}


@app.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return dataset_dict(owned_dataset(db, dataset_id, current_user.id))


@app.put("/datasets/{dataset_id}")
def rename_dataset(dataset_id: int, payload: RenameDatasetRequest,
                   current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = owned_dataset(db, dataset_id, current_user.id)
    item.dataset_name = payload.dataset_name.strip()
    if hasattr(item, "updated_at"):
        item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return dataset_dict(item)


def _dataset_rows(item: Dataset, limit: int = PREVIEW_ROW_LIMIT):
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                pg_sql.SQL("SELECT * FROM {} LIMIT %s").format(pg_sql.Identifier(item.table_name)),
                (min(max(limit, 1), PREVIEW_ROW_LIMIT),),
            )
            columns = [description[0] for description in cursor.description]
            return columns, cursor.fetchall()
    finally:
        conn.close()


@app.get("/datasets/{dataset_id}/preview")
def preview_dataset(dataset_id: int, limit: int = 25, current_user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    item = owned_dataset(db, dataset_id, current_user.id)
    columns, rows = _dataset_rows(item, limit)
    return json_safe({"dataset_id": item.id, "columns": columns, "rows": rows, "row_count": item.row_count})


@app.get("/datasets/{dataset_id}/download")
def download_dataset(dataset_id: int, current_user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    item = owned_dataset(db, dataset_id, current_user.id)
    conn = psycopg2.connect(**DB_CONFIG)
    buffer = io.StringIO()
    try:
        with conn.cursor() as cursor:
            statement = pg_sql.SQL("COPY {} TO STDOUT WITH CSV HEADER").format(pg_sql.Identifier(item.table_name))
            cursor.copy_expert(statement.as_string(conn), buffer)
    finally:
        conn.close()
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", item.dataset_name).strip("_") or "dataset"
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{safe_name}.csv"'})


@app.delete("/datasets/{dataset_id}")
def delete_dataset(dataset_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = owned_dataset(db, dataset_id, current_user.id)
    try:
        assert_internal_table_name(item.table_name)
        db.execute(text(f'DROP TABLE "{item.table_name}"'))
        db.delete(item)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"success": True}


@app.post("/query")
def query_dataset(payload: QueryRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    started = time.perf_counter()
    item = owned_dataset(db, payload.dataset_id, current_user.id)
    question = " ".join(payload.question.split())
    if is_unsafe_user_intent(question):
        raise HTTPException(status_code=400, detail="Only read-only analytics questions are allowed")
    correction_attempted = False
    correction_attempts = 0
    try:
        generator = SQLGenerator()
        generated = generator.generate_sql_for_dataset(question, item.table_name, item.columns_json)
    except Exception as exc:
        logger.warning("Dataset SQL generation failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="The AI service could not generate SQL. Check the model configuration and try again.") from exc
    valid, message = validate_sql(generated, allowed_tables=[item.table_name])
    if not valid:
        if hasattr(generator, "fix_sql_for_dataset"):
            correction_attempted = True
            correction_attempts = 1
            try:
                generated = generator.fix_sql_for_dataset(question, generated, message, item.table_name, item.columns_json)
                valid, message = validate_sql(generated, allowed_tables=[item.table_name])
            except Exception:
                valid = False
        if not valid:
            raise HTTPException(status_code=400, detail=f"Generated SQL did not pass the read-only security policy: {message}")
    try:
        columns, rows = execute_sql(generated, allowed_tables=[item.table_name])
    except Exception as exc:
        if hasattr(generator, "fix_sql_for_dataset") and correction_attempts == 0:
            correction_attempted = True
            correction_attempts = 1
            try:
                corrected = generator.fix_sql_for_dataset(question, generated, "PostgreSQL could not execute the query", item.table_name, item.columns_json)
                valid, message = validate_sql(corrected, allowed_tables=[item.table_name])
                if not valid:
                    raise ValueError(message)
                columns, rows = execute_sql(corrected, allowed_tables=[item.table_name])
                generated = corrected
            except Exception as correction_error:
                logger.warning("Dataset SQL correction failed: %s", type(correction_error).__name__)
                raise HTTPException(status_code=422, detail="The generated query could not be executed safely. Try a simpler question using the displayed column names.") from exc
        else:
            raise HTTPException(status_code=422, detail="The generated query could not be executed safely. Try a simpler question using the displayed column names.") from exc
    try:
        insight = generate_insights(question, columns, rows)
    except Exception:
        insight = deterministic_insight(columns, rows)
    try:
        chart_path = generate_chart(question, columns, rows)
    except Exception:
        chart_path = None
    quality = dynamic_quality(generated, item.table_name, columns)
    try:
        report_path = export_session(question, generated, columns, rows, insight, chart_path,
                                     dataset_name=item.dataset_name, quality_eval=quality, rag_used=True)
    except Exception:
        report_path = None
    elapsed_ms = int(round((time.perf_counter() - started) * 1000))
    history_item = QueryHistory(user_id=current_user.id, dataset_id=item.id, question=question,
                                generated_sql=generated, insight=insight)
    set_if_mapped(history_item, {
        "result_columns_json": json_safe(columns), "result_json": json_safe(rows[:500]),
        "row_count": len(rows), "quality_json": json_safe(quality), "quality_score": quality.get("score"),
        "rag_used": True, "correction_used": correction_attempted, "execution_ms": elapsed_ms,
        "status": "success", "report_path": report_path,
    })
    if hasattr(item, "last_queried_at"):
        item.last_queried_at = datetime.now(timezone.utc)
    db.add(history_item)
    db.commit()
    db.refresh(history_item)
    return json_safe({"question": question, "dataset_id": item.id, "dataset_name": item.dataset_name,
                      "sql": generated, "columns": columns, "result": rows, "row_count": len(rows),
                      "insight": insight, "quality_eval": quality, "rag_used": True,
                      "rag_context_type": "Dataset metadata and schema", "rag_sources": ["dataset metadata"],
                      "correction_attempted": correction_attempted, "correction_attempts": correction_attempts,
                      "execution_ms": elapsed_ms, "generated_at": datetime.now(timezone.utc),
                      "history_id": history_item.id, "report_available": bool(report_path)})


@app.post("/query/demo")
def query_demo(payload: DemoQueryRequest, current_user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """Backward-compatible ecommerce demo workflow."""
    response = process_question(payload.question, conversation_history_override="", persist_memory=False)
    if response.get("error"):
        raise HTTPException(status_code=422, detail=response["error"])
    response.pop("history", None)
    chart_path = response.pop("chart_path", None)
    report_path = response.pop("report_path", None)
    history_item = QueryHistory(user_id=current_user.id, dataset_id=None, question=response.get("question", payload.question),
                                generated_sql=response.get("sql", ""), insight=response.get("insight", ""))
    set_if_mapped(history_item, {
        "result_columns_json": json_safe(response.get("columns", [])),
        "result_json": json_safe(response.get("result", [])[:500]),
        "row_count": len(response.get("result", [])), "quality_json": json_safe(response.get("quality_eval")),
        "quality_score": (response.get("quality_eval") or {}).get("score"),
        "rag_used": bool(response.get("rag_used")), "correction_used": False,
        "status": "success", "report_path": report_path,
    })
    db.add(history_item)
    db.commit()
    db.refresh(history_item)
    response["chart_available"] = bool(chart_path)
    response["report_available"] = bool(report_path)
    response["history_id"] = history_item.id
    response["dataset_name"] = "Ecommerce Demo"
    response["generated_at"] = datetime.now(timezone.utc)
    return json_safe(response)


def history_dict(item: QueryHistory) -> dict:
    return json_safe({
        "id": item.id, "dataset_id": item.dataset_id, "question": item.question,
        "dataset_name": item.dataset.dataset_name if getattr(item, "dataset", None) else "Ecommerce Demo",
        "sql": item.generated_sql, "insight": item.insight, "created_at": item.created_at,
        "columns": getattr(item, "result_columns_json", None), "result": getattr(item, "result_json", None),
        "row_count": getattr(item, "row_count", None), "quality_eval": getattr(item, "quality_json", None),
        "quality_score": getattr(item, "quality_score", None), "rag_used": getattr(item, "rag_used", None),
        "correction_used": getattr(item, "correction_used", None), "execution_ms": getattr(item, "execution_ms", None),
        "status": getattr(item, "status", "success"), "report_available": bool(getattr(item, "report_path", None)),
    })


@app.get("/history")
def history(dataset_id: int | None = None, search: str = "", order: str = "desc", limit: int = 100,
            current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    statement = select(QueryHistory).where(QueryHistory.user_id == current_user.id)
    if dataset_id is not None:
        owned_dataset(db, dataset_id, current_user.id)
        statement = statement.where(QueryHistory.dataset_id == dataset_id)
    if search.strip():
        statement = statement.where(QueryHistory.question.ilike(f"%{search.strip()[:200]}%"))
    ordering = QueryHistory.created_at.asc() if order.lower() == "asc" else QueryHistory.created_at.desc()
    items = db.scalars(statement.order_by(ordering).limit(min(max(limit, 1), 500))).all()
    return {"history": [history_dict(item) for item in items]}


@app.get("/history/{dataset_id}")
def dataset_history(dataset_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_dataset(db, dataset_id, current_user.id)
    items = db.scalars(select(QueryHistory).where(QueryHistory.user_id == current_user.id,
                                                   QueryHistory.dataset_id == dataset_id).order_by(QueryHistory.created_at.desc())).all()
    return {"history": [history_dict(item) for item in items]}


@app.delete("/history")
def clear_history(dataset_id: int | None = None, current_user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    statement = delete(QueryHistory).where(QueryHistory.user_id == current_user.id)
    if dataset_id is not None:
        owned_dataset(db, dataset_id, current_user.id)
        statement = statement.where(QueryHistory.dataset_id == dataset_id)
    result = db.execute(statement)
    db.commit()
    return {"success": True, "deleted_count": result.rowcount or 0}


@app.delete("/history/item/{history_id}")
def delete_history_item(history_id: int, current_user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    item = db.scalar(select(QueryHistory).where(QueryHistory.id == history_id,
                                                QueryHistory.user_id == current_user.id))
    if not item:
        raise HTTPException(status_code=404, detail="History item not found")
    db.delete(item)
    db.commit()
    return {"success": True}


@app.get("/reports/{history_id}/download")
def download_report(history_id: int, current_user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    item = db.scalar(select(QueryHistory).where(QueryHistory.id == history_id,
                                                QueryHistory.user_id == current_user.id))
    if not item or not getattr(item, "report_path", None):
        raise HTTPException(status_code=404, detail="Report not found")
    report_path = (BASE_DIR / item.report_path).resolve()
    if not report_path.is_relative_to(EXPORT_DIR) or not report_path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(report_path, media_type="text/plain", filename=f"agentic_sql_report_{history_id}.txt")


# Demo mode remains available, but is private like every analytics endpoint.
@app.get("/dashboard/metrics")
def dashboard_metrics(_: User = Depends(get_current_user)):
    def scalar(statement):
        return json_safe(execute_sql(statement)[1][0][0])
    total_revenue = scalar("SELECT COALESCE(SUM(quantity * price), 0) FROM order_items;")
    total_orders = scalar("SELECT COUNT(*) FROM orders;")
    completed_orders = scalar("SELECT COUNT(*) FROM orders WHERE LOWER(status) = 'completed';")
    return {"total_revenue": total_revenue,
            "total_orders": total_orders,
            "total_customers": scalar("SELECT COUNT(*) FROM customers;"),
            "total_products": scalar("SELECT COUNT(*) FROM products;"),
            "average_order_value": round(float(total_revenue) / total_orders, 2) if total_orders else 0,
            "completion_rate": round(float(completed_orders) / total_orders * 100, 2) if total_orders else 0}


def _records(statement: str) -> list[dict]:
    columns, rows = execute_sql(statement)
    return [dict(zip(columns, json_safe(row))) for row in rows]


@app.get("/dashboard/revenue-by-category")
def revenue_by_category(_: User = Depends(get_current_user)):
    return {"data": _records("SELECT p.category, SUM(oi.quantity * oi.price) AS revenue FROM order_items oi JOIN products p ON oi.product_id=p.product_id GROUP BY p.category ORDER BY revenue DESC;")}


@app.get("/dashboard/top-products")
def top_products(_: User = Depends(get_current_user)):
    return {"data": _records("SELECT p.product_name, SUM(oi.quantity * oi.price) AS revenue FROM order_items oi JOIN products p ON oi.product_id=p.product_id GROUP BY p.product_name ORDER BY revenue DESC LIMIT 5;")}


@app.get("/dashboard/orders-by-status")
def orders_by_status(_: User = Depends(get_current_user)):
    return {"data": _records("SELECT status, COUNT(*) AS total_orders FROM orders GROUP BY status ORDER BY total_orders DESC;")}


@app.get("/dashboard/revenue-by-country")
def revenue_by_country(_: User = Depends(get_current_user)):
    return {"data": _records("SELECT c.country, SUM(oi.quantity * oi.price) AS revenue FROM order_items oi JOIN orders o ON oi.order_id=o.order_id JOIN customers c ON o.customer_id=c.customer_id GROUP BY c.country ORDER BY revenue DESC LIMIT 8;")}


@app.get("/dashboard/monthly-revenue")
def monthly_revenue(_: User = Depends(get_current_user)):
    # The bundled CSV loader creates ``orders.order_date`` as TEXT. Cast it
    # explicitly so this endpoint works for both existing demo databases and
    # installations that use a native DATE column.
    return {"data": _records(
        "SELECT DATE_TRUNC('month', CAST(o.order_date AS date))::date AS month, "
        "SUM(oi.quantity * oi.price) AS revenue "
        "FROM orders o JOIN order_items oi ON o.order_id=oi.order_id "
        "GROUP BY month ORDER BY month;"
    )}
