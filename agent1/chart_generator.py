"""
chart_generator.py
------------------
Generates charts based on SQL result.
Supports bar, horizontal bar, pie, and line charts.
"""

import os
from datetime import datetime

import matplotlib

matplotlib.use("Agg")

import pandas as pd
import matplotlib.pyplot as plt


CHART_DIR = "charts"


def generate_chart(question, columns, result):
    if not columns or not result:
        return None

    os.makedirs(CHART_DIR, exist_ok=True)

    df = pd.DataFrame(result, columns=columns)

    if df.empty or len(df.columns) < 2:
        return None

    question_lower = question.lower()

    numeric_cols = df.select_dtypes(include=["int64", "float64", "int32", "float32"]).columns.tolist()

    # Convert possible numeric object columns
    for col in df.columns:
        if col not in numeric_cols:
            converted = pd.to_numeric(df[col], errors="coerce")
            if converted.notna().sum() > 0:
                df[col] = converted
                numeric_cols.append(col)

    if not numeric_cols:
        return None

    value_col = numeric_cols[-1]

    label_cols = [col for col in df.columns if col != value_col]
    if not label_cols:
        return None

    label_col = label_cols[0]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    chart_path = os.path.join(CHART_DIR, f"chart_{timestamp}.png")

    plt.figure(figsize=(10, 5))

    # Pie chart
    if any(word in question_lower for word in ["pie", "share", "distribution", "percentage"]):
        plt.pie(
            df[value_col],
            labels=df[label_col],
            autopct="%1.1f%%",
            startangle=140
        )
        plt.title(f"{value_col} by {label_col}")
        plt.tight_layout()
        plt.savefig(chart_path, dpi=150)
        plt.close()
        return chart_path

    # Line chart
    if any(word in question_lower for word in ["trend", "month", "date", "daily", "weekly", "yearly", "growth"]):
        plt.plot(
            df[label_col].astype(str),
            df[value_col],
            marker="o",
            linewidth=2
        )
        plt.title(f"{value_col} Trend")
        plt.xlabel(label_col)
        plt.ylabel(value_col)
        plt.xticks(rotation=45, ha="right")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(chart_path, dpi=150)
        plt.close()
        return chart_path

    # Horizontal bar chart
    if any(word in question_lower for word in ["top", "lowest", "rank", "highest", "maximum", "minimum"]):
        plt.barh(
            df[label_col].astype(str),
            df[value_col]
        )
        plt.title(f"{value_col} by {label_col}")
        plt.xlabel(value_col)
        plt.ylabel(label_col)
        plt.gca().invert_yaxis()
        plt.tight_layout()
        plt.savefig(chart_path, dpi=150)
        plt.close()
        return chart_path

    # Default bar chart
    plt.bar(
        df[label_col].astype(str),
        df[value_col]
    )
    plt.title(f"{value_col} by {label_col}")
    plt.xlabel(label_col)
    plt.ylabel(value_col)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(chart_path, dpi=150)
    plt.close()

    return chart_path
