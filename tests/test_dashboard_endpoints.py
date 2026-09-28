"""Regression tests for the preloaded ecommerce dashboard contract."""

import api.main as api_main


def test_monthly_revenue_casts_csv_text_dates(monkeypatch):
    captured: dict[str, str] = {}

    def fake_records(statement: str) -> list[dict]:
        captured["statement"] = statement
        return [{"month": "2024-10-01", "revenue": 123.0}]

    monkeypatch.setattr(api_main, "_records", fake_records)

    response = api_main.monthly_revenue(None)

    assert response == {"data": [{"month": "2024-10-01", "revenue": 123.0}]}
    assert "CAST(o.order_date AS date)" in captured["statement"]
    assert "GROUP BY month ORDER BY month" in captured["statement"]
