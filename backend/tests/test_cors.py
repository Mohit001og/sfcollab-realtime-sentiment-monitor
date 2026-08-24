from fastapi.testclient import TestClient

from app.main import app, parse_frontend_origins


client = TestClient(app)


def test_parse_frontend_origins_strips_whitespace_and_ignores_empty_entries() -> None:
    origins = parse_frontend_origins(" http://localhost:5173, ,https://example-frontend.com ")

    assert origins == ["http://localhost:5173", "https://example-frontend.com"]


def test_configured_frontend_origin_is_allowed() -> None:
    response = client.options(
        "/messages",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_disallowed_origin_is_not_granted_cors_access() -> None:
    response = client.options(
        "/messages",
        headers={
            "Origin": "https://not-the-dashboard.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_api_response_schema_is_unchanged_with_allowed_origin() -> None:
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
