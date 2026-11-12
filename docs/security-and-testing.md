# Hardening and verification

## Request and session boundaries

All private routes use shared identity/event/case dependencies. Suspension is
checked on each request. Passwords use Argon2; refresh/reset/verification tokens
are stored hashed; refresh rotates and password reset revokes sessions. React
keeps session tokens in sessionStorage (memory fallback), never in URLs or
analytics calls; Flutter uses secure storage. SessionStorage remains readable to
same-origin JavaScript, so XSS prevention and trusted dependencies matter.
There is no GA4 client or PII forwarding endpoint in this checkout.

React serializes text through normal JSX, never arbitrary HTML. The Nginx web
container applies a CSP, nosniff, and no-referrer policy; query-token links do not
send tokens in Referer headers. Protected downloads use authenticated fetch and
revoked object URLs. API responses default to no-store. Event screenshots and
support screenshots are decoded/re-encoded; support storage is private.

CORS uses the JSON `CORS_ORIGINS` allowlist and Authorization/Content-Type
headers. Cross-origin cookies are disabled. Production web uses the same-origin
Nginx `/api/` proxy. Set `VITE_API_BASE_URL` for a separate development API origin
and allow that frontend origin explicitly. Nginx CSP connect-src is same-origin;
change it deliberately if deploying the web against a separate API domain.

## Rate limits

Login defaults to 30 attempts per 60 seconds per direct client IP; promo preview
to 120. Configure `RATE_LIMIT_LOGIN_REQUESTS`, `RATE_LIMIT_PROMO_REQUESTS`, and
`RATE_LIMIT_WINDOW_SECONDS`. HTTP 429 includes the normal error envelope and
Retry-After. Caller-supplied X-Forwarded-For does not bypass these limits.
Buckets are bounded to 20,000 recent client/action keys per API process.

This is an MVP process-local limiter. Multiple API processes do not share it;
behind the included proxy, requests share the proxy's direct client IP. For a
multi-worker/public deployment, enforce a shared client-aware ingress/Redis
limit rather than trusting arbitrary forwarding headers. Restart clears buckets.

## Checks

```sh
npm ci
npm run lint
npm test
npm run build
cd backend
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python -m app.scripts.export_openapi
```

Frontend tests include rotating concurrent refresh, logout races, failures,
pagination, multipart uploads, role gates, rejected login, real checkout request
construction and organizer creation. DOM component tests use jsdom and Vite's
SSR loader; they do not substitute for a visual browser/device test.

Backend tests include permissions, rollback, inventory/payment/promo races,
50 distinct buyers competing for 10 tickets (free and paid), seat holds,
calendar access/escaping, screenshot privacy, query plans and migrations. The
50-buyer test verifies correctness under contention, not a throughput SLA.
Business-rule coverage is mapped in `demo-flow.md`; no numerical coverage claim
is made without instrumentation.

The npm lockfile contains compatible security updates. A minimatch override
selects patched 11.x because ESLint's 10.x transitive range remains vulnerable;
lint and the component suite validate this toolchain. Review the override when
ESLint adopts a patched range. Do not use `npm audit fix --force` blindly.

## Integration triage

`.github/ISSUE_TEMPLATE/integration_bug.yml` captures device/commit, steps,
expected/actual behavior and regression coverage, without credentials. A Jira
board still needs the team's Jira project and access; no external board or
messages have been created. Every confirmed integration fix should include a
regression test or a documented device reproduction.
