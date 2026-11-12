"""Bounded process-local admission limits; do not trust forwarded client headers."""

import math
import re
import time
from collections import OrderedDict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

PROMO_PATH = re.compile(r"^/api/v1/events/[^/]+/promo/validate$")


class RequestLimits:
    def __init__(self, max_clients=20_000):
        self.clients = OrderedDict()
        self.max_clients = max_clients

    def retry_after(self, key, limit, window, now=None):
        now = time.monotonic() if now is None else now
        bucket = self.clients.pop(key, deque())
        while bucket and bucket[0] <= now - window:
            bucket.popleft()
        retry = max(1, math.ceil(window - (now - bucket[0]))) if len(bucket) >= limit else 0
        if not retry:
            bucket.append(now)
        self.clients[key] = bucket
        while len(self.clients) > self.max_clients:
            self.clients.popitem(last=False)
        return retry


def install_http_middleware(app: FastAPI, settings):
    @app.middleware("http")
    async def limits_and_headers(request: Request, call_next):
        path = request.url.path
        login = request.method == "POST" and path == "/api/v1/auth/login"
        promo = request.method == "POST" and PROMO_PATH.fullmatch(path)
        if login or promo:
            limit = (
                settings.rate_limit_login_requests if login else settings.rate_limit_promo_requests
            )
            client = request.client.host if request.client else "unknown"
            retry = app.state.request_limits.retry_after(
                ("login" if login else "promo", client), limit, settings.rate_limit_window_seconds
            )
            if retry:
                return JSONResponse(
                    {
                        "error": {
                            "code": "RATE_LIMITED",
                            "message": "Too many requests. Try again shortly.",
                            "details": {"retry_after_seconds": retry},
                        }
                    },
                    status_code=429,
                    headers={
                        "Retry-After": str(retry),
                        "Cache-Control": "no-store",
                        "X-Content-Type-Options": "nosniff",
                        "Referrer-Policy": "no-referrer",
                    },
                )
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        return response
