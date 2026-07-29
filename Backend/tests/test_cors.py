from fastapi.testclient import TestClient
from main import app, _get_allowed_origins

client = TestClient(app)


# ========== CORS middleware 實際行為（用預設白名單 http://localhost:3000）==========

def test_allowed_origin_gets_reflected_back():
    res = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_unlisted_origin_does_not_get_cors_header():
    res = client.get("/health", headers={"Origin": "https://evil.example.com"})
    # request 本身仍會被處理（FastAPI 不會擋 request），但瀏覽器端不會拿到允許跨站的標頭
    assert res.status_code == 200
    assert "access-control-allow-origin" not in res.headers


def test_cors_never_uses_wildcard_when_credentials_allowed():
    res = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert res.headers.get("access-control-allow-origin") != "*"


def test_preflight_request_for_unlisted_origin_is_rejected():
    res = client.options(
        "/health",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in res.headers


# ========== _get_allowed_origins() 的白名單解析邏輯 ==========

def test_parses_comma_separated_origins(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://a.com, https://b.com ,https://c.com")
    assert _get_allowed_origins() == ["https://a.com", "https://b.com", "https://c.com"]


def test_defaults_to_localhost_when_unset(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    assert _get_allowed_origins() == ["http://localhost:3000"]


def test_ignores_blank_entries(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://a.com,,  ,https://b.com")
    assert _get_allowed_origins() == ["https://a.com", "https://b.com"]
