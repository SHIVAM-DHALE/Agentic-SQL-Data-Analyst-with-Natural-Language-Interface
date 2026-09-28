"""Presentation helpers for the Streamlit analytics experience.

This module contains no Streamlit state and no database access, which keeps
formatting and visualization decisions deterministic and easy to test.
"""

from __future__ import annotations

import html
import math
import re
from datetime import datetime
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


CHART_COLORS = [
    "#4F46E5",
    "#0EA5E9",
    "#10B981",
    "#F59E0B",
    "#F43F5E",
    "#8B5CF6",
    "#06B6D4",
    "#84CC16",
]


def safe_html(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def compact_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—" if value in (None, "") else str(value)
    if not math.isfinite(number):
        return "—"
    absolute = abs(number)
    for threshold, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if absolute >= threshold:
            return f"{number / threshold:,.1f}{suffix}"
    return f"{number:,.0f}" if number.is_integer() else f"{number:,.2f}"


def currency(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def friendly_name(value: Any) -> str:
    text = re.sub(r"[_\-]+", " ", str(value or "")).strip()
    return text[:1].upper() + text[1:] if text else "Value"


def friendly_datetime(value: Any, include_time: bool = False) -> str:
    if not value:
        return "Not available"
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return str(value)
    return parsed.strftime("%d %b %Y, %H:%M UTC" if include_time else "%d %b %Y")


def result_dataframe(columns: list | None, rows: list | None) -> pd.DataFrame:
    rows = rows or []
    if rows and isinstance(rows[0], dict):
        frame = pd.DataFrame(rows)
        if columns:
            ordered = [column for column in columns if column in frame.columns]
            frame = frame[ordered + [column for column in frame.columns if column not in ordered]]
        return frame
    try:
        return pd.DataFrame(rows, columns=columns or None)
    except (TypeError, ValueError):
        return pd.DataFrame(rows)


def coerce_for_visualization(frame: pd.DataFrame) -> pd.DataFrame:
    """Infer useful numeric/date columns without mutating displayed raw data."""

    output = frame.copy()
    for column in output.columns:
        series = output[column]
        if pd.api.types.is_numeric_dtype(series) or pd.api.types.is_datetime64_any_dtype(series):
            continue
        non_null = series.dropna()
        if non_null.empty:
            continue
        name = str(column).lower()
        date_hint = any(token in name for token in ("date", "time", "month", "year", "week", "day"))
        if date_hint:
            parsed_date = pd.to_datetime(series, errors="coerce")
            if parsed_date.notna().mean() >= 0.75:
                output[column] = parsed_date
                continue
        parsed_number = pd.to_numeric(series.astype(str).str.replace(",", "", regex=False), errors="coerce")
        if parsed_number.notna().mean() >= 0.85:
            output[column] = parsed_number
    return output


def chart_columns(frame: pd.DataFrame) -> tuple[list[str], list[str], list[str]]:
    prepared = coerce_for_visualization(frame)
    numeric = prepared.select_dtypes(include="number").columns.astype(str).tolist()
    dates = [str(column) for column in prepared.columns if pd.api.types.is_datetime64_any_dtype(prepared[column])]
    categories = [str(column) for column in prepared.columns if str(column) not in numeric + dates]
    return numeric, dates, categories


def chart_recommendation(frame: pd.DataFrame, question: str = "") -> dict[str, str | None]:
    prepared = coerce_for_visualization(frame)
    numeric, dates, categories = chart_columns(prepared)
    lowered = question.lower()
    result: dict[str, str | None] = {"type": "Table", "x": None, "y": None, "color": None}
    if prepared.empty:
        return result
    if len(prepared) == 1 and numeric:
        return {"type": "KPI", "x": None, "y": numeric[0], "color": None}
    if dates and numeric:
        return {"type": "Line", "x": dates[0], "y": numeric[0], "color": categories[0] if categories else None}
    if len(numeric) >= 2 and any(token in lowered for token in ("correlation", "relationship", "versus", " vs ", "compare two")):
        return {"type": "Scatter", "x": numeric[0], "y": numeric[1], "color": categories[0] if categories else None}
    if categories and numeric:
        category = categories[0]
        unique = prepared[category].nunique(dropna=True)
        if unique <= 7 and any(token in lowered for token in ("share", "percent", "proportion", "distribution", "status")):
            return {"type": "Donut", "x": category, "y": numeric[0], "color": None}
        return {"type": "Horizontal bar" if unique > 6 else "Bar", "x": category, "y": numeric[0], "color": None}
    if numeric:
        return {"type": "Histogram", "x": numeric[0], "y": None, "color": categories[0] if categories else None}
    return result


def available_chart_types(frame: pd.DataFrame) -> list[str]:
    numeric, dates, categories = chart_columns(frame)
    options = ["Auto", "Table"]
    if numeric and (categories or dates or len(numeric) >= 2):
        options[1:1] = ["Bar", "Horizontal bar"]
    if numeric and (dates or categories):
        options[1:1] = ["Line", "Area"]
    if numeric and categories:
        options[1:1] = ["Donut"]
    if len(numeric) >= 2:
        options[1:1] = ["Scatter"]
    if numeric:
        options[1:1] = ["Histogram", "Box"]
    if numeric and len(categories) >= 2:
        options[1:1] = ["Heatmap"]
    return list(dict.fromkeys(options))


def _aggregate(frame: pd.DataFrame, x: str, y: str, color: str | None, aggregation: str) -> pd.DataFrame:
    if aggregation == "None" or not x or not y:
        return frame
    functions = {"Sum": "sum", "Average": "mean", "Count": "count", "Min": "min", "Max": "max"}
    group_columns = [x] + ([color] if color and color != x else [])
    return frame.groupby(group_columns, dropna=False, as_index=False)[y].agg(functions[aggregation])


def style_figure(fig: go.Figure, title: str, height: int = 420) -> go.Figure:
    fig.update_layout(
        title={"text": title, "x": 0.02, "xanchor": "left", "font": {"size": 17, "color": "#0F172A"}},
        height=height,
        margin={"l": 30, "r": 22, "t": 65, "b": 32},
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        colorway=CHART_COLORS,
        font={"family": "Inter, Segoe UI, sans-serif", "color": "#334155"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        hoverlabel={"bgcolor": "#0F172A", "font_color": "#FFFFFF"},
    )
    fig.update_xaxes(showgrid=False, linecolor="#E2E8F0", title_font={"color": "#64748B"})
    fig.update_yaxes(gridcolor="#EEF2F7", linecolor="#E2E8F0", title_font={"color": "#64748B"})
    return fig


def build_chart(
    frame: pd.DataFrame,
    question: str,
    chart_type: str = "Auto",
    x: str | None = None,
    y: str | None = None,
    color: str | None = None,
    aggregation: str = "None",
) -> tuple[go.Figure | None, dict[str, str | None]]:
    """Create a Plotly figure and return the effective chart configuration."""

    prepared = coerce_for_visualization(frame)
    recommendation = chart_recommendation(prepared, question)
    effective_type = recommendation["type"] if chart_type == "Auto" else chart_type
    numeric, dates, categories = chart_columns(prepared)
    x = x or recommendation.get("x")
    y = y or recommendation.get("y")
    color = color or recommendation.get("color")
    configuration = {"type": effective_type, "x": x, "y": y, "color": color}

    if prepared.empty or effective_type in ("Table", "KPI"):
        return None, configuration

    title = question.strip() or f"{friendly_name(y)} by {friendly_name(x)}"
    labels = {str(column): friendly_name(column) for column in prepared.columns}
    try:
        if effective_type in ("Bar", "Horizontal bar", "Line", "Area"):
            x = x or (dates[0] if dates else categories[0] if categories else numeric[0])
            y = y or next((column for column in numeric if column != x), numeric[0])
            chart_data = _aggregate(prepared, x, y, color, aggregation)
            if effective_type == "Bar":
                fig = px.bar(chart_data, x=x, y=y, color=color, labels=labels, color_discrete_sequence=CHART_COLORS)
            elif effective_type == "Horizontal bar":
                chart_data = chart_data.sort_values(y, ascending=True).tail(30)
                fig = px.bar(chart_data, x=y, y=x, color=color, orientation="h", labels=labels, color_discrete_sequence=CHART_COLORS)
            elif effective_type == "Area":
                chart_data = chart_data.sort_values(x)
                fig = px.area(chart_data, x=x, y=y, color=color, markers=True, labels=labels, color_discrete_sequence=CHART_COLORS)
            else:
                chart_data = chart_data.sort_values(x)
                fig = px.line(chart_data, x=x, y=y, color=color, markers=True, labels=labels, color_discrete_sequence=CHART_COLORS)
        elif effective_type == "Donut":
            x = x or categories[0]
            y = y or numeric[0]
            chart_data = _aggregate(prepared, x, y, None, "Sum" if aggregation == "None" else aggregation)
            chart_data = chart_data.sort_values(y, ascending=False).head(10)
            fig = px.pie(chart_data, names=x, values=y, hole=0.58, labels=labels, color_discrete_sequence=CHART_COLORS)
            fig.update_traces(textposition="inside", textinfo="percent+label")
        elif effective_type == "Scatter":
            x = x or numeric[0]
            y = y or next(column for column in numeric if column != x)
            fig = px.scatter(prepared, x=x, y=y, color=color, labels=labels, color_discrete_sequence=CHART_COLORS, opacity=0.8)
        elif effective_type == "Histogram":
            x = x if x in numeric else numeric[0]
            fig = px.histogram(prepared, x=x, color=color, labels=labels, color_discrete_sequence=CHART_COLORS, nbins=min(40, max(8, int(len(prepared) ** 0.5))))
        elif effective_type == "Box":
            y = y if y in numeric else numeric[0]
            x = x if x in categories and prepared[x].nunique(dropna=True) <= 20 else None
            fig = px.box(prepared, x=x, y=y, color=color if color in categories else x, points="outliers", labels=labels, color_discrete_sequence=CHART_COLORS)
        elif effective_type == "Heatmap":
            category_x = x if x in categories else categories[0]
            category_y = color if color in categories and color != category_x else categories[1]
            value = y if y in numeric else numeric[0]
            pivot = prepared.pivot_table(index=category_y, columns=category_x, values=value, aggfunc="sum", fill_value=0)
            pivot = pivot.iloc[:25, :25]
            fig = px.imshow(pivot, aspect="auto", color_continuous_scale="Blues", labels={"x": friendly_name(category_x), "y": friendly_name(category_y), "color": friendly_name(value)})
        else:
            return None, configuration
    except (KeyError, ValueError, TypeError, StopIteration):
        return None, configuration

    configuration = {"type": effective_type, "x": x, "y": y, "color": color}
    return style_figure(fig, title), configuration


def suggested_questions(columns: list[dict] | list[str] | None) -> list[str]:
    names = [item.get("name", "") if isinstance(item, dict) else str(item) for item in (columns or [])]
    names = [name for name in names if name]
    if not names:
        return ["Show the first 20 records", "How many rows are in this dataset?"]
    numeric_hints = ("amount", "price", "revenue", "sales", "cost", "quantity", "score", "total", "value")
    date_hints = ("date", "time", "month", "year")
    numeric = next((name for name in names if any(token in name.lower() for token in numeric_hints)), None)
    dated = next((name for name in names if any(token in name.lower() for token in date_hints)), None)
    category = next((name for name in names if name not in (numeric, dated)), names[0])
    prompts = [f"Show the top 10 records by {numeric}" if numeric else "Show the first 20 records"]
    if numeric and category:
        prompts.append(f"What is the total {numeric} by {category}?")
        prompts.append(f"Which {category} has the highest average {numeric}?")
    if dated and numeric:
        prompts.append(f"Show the {numeric} trend over {dated}")
    prompts.append(f"How many distinct {category} values are there?")
    return list(dict.fromkeys(prompts))[:4]


def password_strength(password: str) -> tuple[int, str, list[str]]:
    checks = {
        "Use at least 10 characters": len(password) >= 10,
        "Add an uppercase letter": bool(re.search(r"[A-Z]", password)),
        "Add a lowercase letter": bool(re.search(r"[a-z]", password)),
        "Add a number": bool(re.search(r"\d", password)),
        "Add a symbol": bool(re.search(r"[^A-Za-z0-9]", password)),
    }
    score = sum(checks.values())
    label = ("Very weak", "Weak", "Fair", "Good", "Strong", "Excellent")[score]
    return score, label, [message for message, passed in checks.items() if not passed]


def report_markdown(response: dict[str, Any], dataset_name: str) -> str:
    frame = result_dataframe(response.get("columns"), response.get("result") or response.get("rows"))
    quality = response.get("quality_eval") or response.get("quality") or {}
    score = quality.get("score", "Unavailable") if isinstance(quality, dict) else "Unavailable"
    rag_used = "Yes" if response.get("rag_used") else "No"
    sources = response.get("rag_sources") or []
    source_text = ", ".join(str(source) for source in sources) if sources else "Schema and dataset metadata"
    result_csv = frame.head(50).to_csv(index=False) if not frame.empty else "No rows returned"
    generated_at = response.get("generated_at") or response.get("created_at") or response.get("timestamp") or datetime.utcnow().isoformat() + "Z"
    return f"""# Agentic SQL Analysis Report

**Dataset:** {dataset_name}  
**Generated:** {friendly_datetime(generated_at, include_time=True)}  
**Read-only policy:** Passed and executed through the protected analytics API

## Business question

{response.get('question') or 'Not recorded'}

## Executive insight

{response.get('insight') or 'No AI insight was available for this result.'}

## Generated SQL

```sql
{response.get('sql') or response.get('generated_sql') or '-- SQL not available'}
```

## Result preview

```csv
{result_csv}
```

## Quality and retrieval

- SQL quality score: {score}
- RAG context used: {rag_used}
- Safe context sources: {source_text}
- Correction used: {'Yes' if response.get('correction_used') or response.get('correction_attempted') else 'No'}
- Returned rows: {response.get('row_count', len(frame))}

---
Generated by Agentic SQL Analyst. Validate material business decisions against the source system.
"""
