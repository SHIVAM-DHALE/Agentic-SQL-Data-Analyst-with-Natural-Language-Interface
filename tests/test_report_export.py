from pathlib import Path

from agent1.export_report import export_session


def test_report_is_unique_professional_and_does_not_expose_chart_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = export_session(
        "Show sales by region",
        "SELECT region, SUM(sales) FROM dataset_1_abcdef1234 GROUP BY region;",
        ["region", "sales"],
        [("North", 100), ("South", 80)],
        "North has the highest sales.",
        chart_path="C:/private/server/chart.png",
        dataset_name="Regional Sales",
        quality_eval={"score": 100, "confidence": "High"},
        rag_used=True,
    )
    report = Path(path)
    content = report.read_text(encoding="utf-8")
    assert report.is_file()
    assert "Regional Sales" in content
    assert "Read-only, validated SQL" in content
    assert "Score: 100" in content
    assert "C:/private/server/chart.png" not in content
