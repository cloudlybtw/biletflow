from app.core.http import RequestLimits


def test_rate_limit_window_and_bounded_memory():
    limits = RequestLimits(max_clients=2)
    assert limits.retry_after(("login", "a"), 2, 60, 0) == 0
    assert limits.retry_after(("login", "a"), 2, 60, 1) == 0
    assert limits.retry_after(("login", "a"), 2, 60, 2) == 58
    assert limits.retry_after(("login", "a"), 2, 60, 60) == 0
    limits.retry_after(("login", "b"), 2, 60, 60)
    limits.retry_after(("promo", "a"), 2, 60, 60)
    assert len(limits.clients) == 2


async def test_login_limit_has_error_envelope_retry_header_and_cors(client, app):
    # Pre-fill only this app's login bucket; forwarded headers cannot bypass it.
    app.state.request_limits.retry_after(("login", "127.0.0.1"), 1, 60)
    from app.core.config import get_settings

    for _ in range(get_settings().rate_limit_login_requests - 1):
        app.state.request_limits.retry_after(("login", "127.0.0.1"), 999, 60)
    response = await client.post(
        "/api/v1/auth/login",
        headers={"Origin": "http://localhost:5173", "X-Forwarded-For": "203.0.113.99"},
        json={"email": "nobody@example.com", "password": "wrong"},
    )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    assert int(response.headers["Retry-After"]) > 0
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"


async def test_cors_preflight_only_allows_configured_origins(client):
    good = await client.options(
        "/api/v1/me",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "Authorization,Content-Type",
        },
    )
    assert good.status_code == 200
    assert good.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    bad = await client.options(
        "/api/v1/me",
        headers={"Origin": "https://untrusted.invalid", "Access-Control-Request-Method": "GET"},
    )
    assert "Access-Control-Allow-Origin" not in bad.headers


async def test_api_responses_disable_caching_and_sniffing(client):
    response = await client.get("/api/v1/me")
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
