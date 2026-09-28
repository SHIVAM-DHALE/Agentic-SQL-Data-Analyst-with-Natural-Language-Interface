"""Create a portable, user-facing analysis report artifact."""

import csv
import os
import uuid
from datetime import datetime


def export_session(
    question,
    sql,
    columns,
    result,
    insight,
    chart_path=None,
    dataset_name="Ecommerce Demo",
    quality_eval=None,
    rag_used=False,
):

    os.makedirs("exports", exist_ok=True)

    timestamp = datetime.now()
    filename = os.path.join(
        "exports",
        f"analysis_{timestamp:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}.txt",
    )

    with open(filename, "w", encoding="utf-8") as file:

        file.write("AGENTIC SQL ANALYST — ANALYSIS REPORT\n")
        file.write("=" * 64 + "\n")
        file.write(f"Generated: {timestamp.isoformat(timespec='seconds')}\n")
        file.write(f"Dataset: {dataset_name}\n")
        file.write("Execution policy: Read-only, validated SQL\n")
        file.write(f"RAG context used: {'Yes' if rag_used else 'No'}\n\n")

        file.write(f"Question:\n{question}\n\n")

        file.write("Generated SQL:\n")
        file.write(sql + "\n\n")

        file.write("Result preview (up to 100 rows):\n")
        writer = csv.writer(file)
        writer.writerow(columns)
        writer.writerows(result[:100])

        file.write("\nInsight:\n")
        file.write(insight + "\n\n")

        if quality_eval:
            file.write("\nSQL Quality Evaluation:\n")
            file.write(f"Score: {quality_eval.get('score', 'Unavailable')}\n")
            file.write(f"Confidence: {quality_eval.get('confidence', 'Unavailable')}\n")

    return filename
