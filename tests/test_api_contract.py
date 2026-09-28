from fastapi.testclient import TestClient

from api.main import app


def test_private_dataset_endpoint_requires_bearer_token():
    client = TestClient(app)
    try:
        response = client.get("/datasets", headers={"X-Request-ID": "unit-test-request"})
        assert response.status_code == 401
        assert response.headers["X-Request-ID"] == "unit-test-request"
        assert response.json()["error"]["message"] == "Not authenticated"
    finally:
        client.close()


def test_openapi_exposes_industry_workspace_contract():
    paths = app.openapi()["paths"]
    required = {
        "/auth/register", "/auth/login", "/auth/forgot-password", "/auth/reset-password",
        "/auth/change-password", "/datasets/upload", "/datasets/{dataset_id}/preview",
        "/datasets/{dataset_id}/download", "/query", "/query/demo", "/history",
        "/reports/{history_id}/download", "/dashboard/monthly-revenue",
    }
    assert required <= set(paths)
