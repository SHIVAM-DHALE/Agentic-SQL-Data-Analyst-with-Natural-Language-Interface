"""Owner-isolation tests that do not require PostgreSQL or Gemini."""
import io

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.dependencies import get_current_user, get_db
from api.main import app
from database.user_models import Base, Dataset, QueryHistory, User


def _isolated_app():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with Session() as db:
        user = User(email="owner@example.com", full_name="Dataset Owner", hashed_password="unused")
        db.add(user); db.commit(); current_id = user.id

    def override_db():
        with Session() as db:
            yield db

    def override_user():
        with Session() as db:
            yield db.get(User, current_id)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return engine, Session, TestClient(app)


def test_dataset_and_history_routes_are_owner_scoped():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with Session() as db:
        user_a = User(email="a@example.com", full_name="Analyst A", hashed_password="unused")
        user_b = User(email="b@example.com", full_name="Analyst B", hashed_password="unused")
        db.add_all([user_a, user_b]); db.flush()
        dataset_a = Dataset(user_id=user_a.id, dataset_name="A Sales", original_filename="a.csv",
                            table_name=f"dataset_{user_a.id}_abcdef1234", columns_json=[{"name": "sales", "type": "int64"}], row_count=1)
        dataset_b = Dataset(user_id=user_b.id, dataset_name="B Sales", original_filename="b.csv",
                            table_name=f"dataset_{user_b.id}_abcdef5678", columns_json=[{"name": "sales", "type": "int64"}], row_count=1)
        db.add_all([dataset_a, dataset_b]); db.flush()
        db.add_all([
            QueryHistory(user_id=user_a.id, dataset_id=dataset_a.id, question="A question", generated_sql="SELECT 1", insight="A"),
            QueryHistory(user_id=user_b.id, dataset_id=dataset_b.id, question="B question", generated_sql="SELECT 1", insight="B"),
        ])
        db.commit()
        a_id, b_id, current_id = dataset_a.id, dataset_b.id, user_a.id

    def override_db():
        with Session() as db:
            yield db

    def override_user():
        with Session() as db:
            yield db.get(User, current_id)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    client = TestClient(app)
    try:
        datasets = client.get("/datasets").json()["datasets"]
        assert [item["id"] for item in datasets] == [a_id]
        assert client.get(f"/datasets/{b_id}").status_code == 404
        assert client.get(f"/datasets/{b_id}/preview").status_code == 404
        assert client.get(f"/datasets/{b_id}/download").status_code == 404
        assert client.delete(f"/datasets/{b_id}").status_code == 404
        assert client.post("/query", json={"dataset_id": b_id, "question": "show total sales"}).status_code == 404
        history = client.get("/history").json()["history"]
        assert [item["question"] for item in history] == ["A question"]
        assert client.get(f"/history/{b_id}").status_code == 404
    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_csv_upload_sanitizes_and_profiles_data():
    engine, Session, client = _isolated_app()
    try:
        response = client.post(
            "/datasets/upload",
            data={"dataset_name": "Regional Sales"},
            files={"file": ("../Unsafe Sales!.csv", b"Sales $,Sales $,Order Date\n10,20,2026-01-01\n30,,2026-01-02\n", "text/csv")},
        )
        assert response.status_code == 201, response.text
        payload = response.json()
        assert payload["dataset_name"] == "Regional Sales"
        assert payload["original_filename"] == "Unsafe Sales!.csv"
        names = [item["name"] for item in payload["columns"]]
        assert names[0] == "sales" and names[-1] == "order_date"
        assert len(names) == len(set(names)) == 3
        assert payload["profile"]["row_count"] == 2
        with Session() as db:
            item = db.scalar(select(Dataset))
            assert item.table_name.startswith(f"dataset_{item.user_id}_")
            assert item.table_name in inspect(engine).get_table_names()
            assert db.execute(text(f'SELECT COUNT(*) FROM "{item.table_name}"')).scalar_one() == 2
    finally:
        client.close(); app.dependency_overrides.clear(); Base.metadata.drop_all(engine); engine.dispose()


def test_upload_rejects_unsupported_and_empty_files():
    engine, _, client = _isolated_app()
    try:
        unsupported = client.post("/datasets/upload", files={"file": ("data.json", b"{}", "application/json")})
        empty = client.post("/datasets/upload", files={"file": ("data.csv", b"", "text/csv")})
        assert unsupported.status_code == 415
        assert empty.status_code == 400
    finally:
        client.close(); app.dependency_overrides.clear(); Base.metadata.drop_all(engine); engine.dispose()


def test_xlsx_upload_accepts_selected_sheet():
    engine, _, client = _isolated_app()
    workbook = io.BytesIO()
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame({"ignore": [1]}).to_excel(writer, sheet_name="First", index=False)
        pd.DataFrame({"Region": ["North"], "Profit": [25]}).to_excel(writer, sheet_name="Analysis", index=False)
    try:
        response = client.post(
            "/datasets/upload",
            data={"dataset_name": "Workbook", "sheet_name": "Analysis"},
            files={"file": ("workbook.xlsx", workbook.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert response.status_code == 201, response.text
        assert [item["name"] for item in response.json()["columns"]] == ["region", "profit"]
    finally:
        client.close(); app.dependency_overrides.clear(); Base.metadata.drop_all(engine); engine.dispose()
