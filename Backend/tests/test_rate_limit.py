import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from rate_limit import rate_limit_key, rate_limit_exceeded_handler


# ========== rate_limit_key：純函式，不需要真的發請求 ==========

def _fake_request(headers: dict, client_host: str = "1.2.3.4"):
    class FakeClient:
        host = client_host

    class FakeRequest:
        pass

    req = FakeRequest()
    req.headers = headers
    req.client = FakeClient()
    return req


def test_rate_limit_key_uses_hashed_authorization_header_when_present():
    req = _fake_request({"Authorization": "Bearer abc123"})
    key = rate_limit_key(req)

    assert key.startswith("user:")
    assert "abc123" not in key  # 明文 token 不該出現在 key 裡（雜湊過）


def test_rate_limit_key_same_token_produces_same_key():
    req1 = _fake_request({"Authorization": "Bearer abc123"})
    req2 = _fake_request({"Authorization": "Bearer abc123"}, client_host="9.9.9.9")

    # 同一個 token，就算換了來源 IP，也該被視為同一個使用者
    assert rate_limit_key(req1) == rate_limit_key(req2)


def test_rate_limit_key_different_tokens_produce_different_keys():
    req1 = _fake_request({"Authorization": "Bearer abc123"})
    req2 = _fake_request({"Authorization": "Bearer xyz789"})

    assert rate_limit_key(req1) != rate_limit_key(req2)


def test_rate_limit_key_falls_back_to_ip_when_no_auth_header():
    req = _fake_request({})
    key = rate_limit_key(req)

    assert key.startswith("ip:")


# ========== 實際限流行為：用獨立的 Limiter 實例，不受測試環境關閉限流影響 ==========

@pytest.fixture
def limited_app():
    app = FastAPI()
    limiter = Limiter(key_func=lambda request: "fixed-key-for-test", storage_uri="memory://", enabled=True)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    @app.get("/ping")
    @limiter.limit("2/minute")
    async def ping(request: Request):
        return {"status": "ok"}

    return TestClient(app)


def test_requests_within_limit_succeed(limited_app):
    assert limited_app.get("/ping").status_code == 200
    assert limited_app.get("/ping").status_code == 200


def test_exceeding_limit_returns_429_with_friendly_body(limited_app):
    limited_app.get("/ping")
    limited_app.get("/ping")
    response = limited_app.get("/ping")  # 第 3 次，超過 "2/minute"

    assert response.status_code == 429
    body = response.json()
    assert body["error_code"] == "RATE_LIMITED"
    assert "太頻繁" in body["detail"]


def test_disabled_limiter_never_blocks():
    app = FastAPI()
    limiter = Limiter(key_func=lambda request: "fixed-key", storage_uri="memory://", enabled=False)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    @app.get("/ping")
    @limiter.limit("1/minute")
    async def ping(request: Request):
        return {"status": "ok"}

    client = TestClient(app)
    for _ in range(5):
        assert client.get("/ping").status_code == 200
