from fastapi.testclient import TestClient
from main import app, _get_allowed_origins

client = TestClient(app)


# ========== CORS middleware 實際行為（用預設白名單 http://localhost:3000）==========

def test_allowed_origin_gets_reflected_back():
    """白名單內的來源（http://localhost:3000）→ 回應要帶 access-control-allow-origin，並原樣回填該來源。"""
    res = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_unlisted_origin_does_not_get_cors_header():
    """不在白名單的來源 → 請求照常處理（200），但回應不能帶允許跨站的標頭，瀏覽器就會擋下。"""
    res = client.get("/health", headers={"Origin": "https://evil.example.com"})
    # request 本身仍會被處理（FastAPI 不會擋 request），但瀏覽器端不會拿到允許跨站的標頭
    assert res.status_code == 200
    assert "access-control-allow-origin" not in res.headers


def test_cors_never_uses_wildcard_when_credentials_allowed():
    """允許帶憑證（cookie / token）時，allow-origin 絕不能是 *（瀏覽器規定，也是安全底線）。"""
    res = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert res.headers.get("access-control-allow-origin") != "*"


def test_preflight_request_for_unlisted_origin_is_rejected():
    """不在白名單的來源送預檢請求（OPTIONS）→ 不能拿到允許跨站的標頭。"""
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
    """CORS_ALLOWED_ORIGINS 用逗號分隔多個來源，每個來源前後的空白要去掉。"""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://a.com, https://b.com ,https://c.com")
    assert _get_allowed_origins() == ["https://a.com", "https://b.com", "https://c.com"]


def test_defaults_to_localhost_when_unset(monkeypatch):
    """沒設定 CORS_ALLOWED_ORIGINS → 預設只允許 http://localhost:3000。"""
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    assert _get_allowed_origins() == ["http://localhost:3000"]


def test_ignores_blank_entries(monkeypatch):
    """逗號之間的空白項目要忽略，不能變成空字串來源。"""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://a.com,,  ,https://b.com")
    assert _get_allowed_origins() == ["https://a.com", "https://b.com"]
