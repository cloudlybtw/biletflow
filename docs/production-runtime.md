# Production runtime preparation

This is a provider-independent release recipe. Local Docker remains enough for
the demo. No public deployment, resource purchase or secret provisioning has
been performed. The Render plan is optional and requires a destination/budget.

## Build and configure

From the repository root:

```sh
docker build -f backend/Dockerfile.production -t biletflow-api:review backend
```

Use `deploy/production.env.example` as a list of settings to populate privately in
the host's secret manager. Never commit real values. The image excludes `.env`,
local uploads, dumps and development dependencies. It runs as UID 10001 and uses
one Uvicorn process without reload, listening on `0.0.0.0:$PORT` (default 8000).

- Set `ENVIRONMENT=production` and a unique random `JWT_SECRET` of at least 32
  characters. The development secret and `REPLACE_` placeholder are rejected.
- Set `DATABASE_URL` to the selected PostgreSQL endpoint. Provider `postgres://`
  and `postgresql://` URLs are normalized to SQLAlchemy's asyncpg driver without
  decoding/rebuilding credentials by string substitution.
- Set `DATABASE_SSL_MODE=verify-full`; certificate chain and hostname checks are
  enabled. If required, mount the provider CA certificate and set
  `DATABASE_SSL_CA_FILE` to its runtime path. A URL `sslmode` must match this
  setting. Replace provider `sslmode=require` with `verify-full` and supply the
  correct CA if necessary; do not disable verification to resolve a failure.
- Set exact HTTPS `WEB_BASE_URL` and JSON `CORS_ORIGINS` for the actual frontend.
  Set `VITE_API_BASE_URL=https://<api-host>/api/v1` at frontend build time.
- Mount persistent uploads at `MEDIA_ROOT=/var/data/media`, writable by UID 10001.
  Keep one API instance/process until shared storage and rate limits are designed.
- Configure an actual sender and SMTP secrets: `SMTP_SECURITY=starttls` (usually
  587) or `ssl` (usually 465), with both username/password if authentication is
  required. TLS validates certificates/hostnames before credentials are sent.
  Mailpit's unencrypted mode is only for local development.

## Release

Run this command once in the built image, with the same database settings and CA
mount as the API, before accepting traffic:

```sh
python -m app.scripts.migrate --confirm-up
```

It invokes the bundled golang-migrate binary directly with forward SQL migrations
and the configured TLS policy. It does not print the DSN from Python. Run it in a
private release job; database credentials are still present in the migration
process arguments, so do not share process listings or enable shell tracing.
Do not automatically downgrade, reset the database or seed public demo accounts.

Start the image's default command; configure `/api/v1/health` as the health check.
Validate login, authenticated routes, actual email delivery, checkout, PDF/calendar,
private support downloads and uploads after restart. Configure frontend security
headers for its actual API origin. Back up before later schema changes and only
roll back the application to a compatible schema.

## Verification recorded on 2026-11-16

- Full backend regression: 728 passed; Ruff lint/format checks passed.
- Production image built successfully with locked dependencies.
- Disposable isolated PostgreSQL database: forward migrations applied, repeat
  invocation succeeded, non-root UID 10001 confirmed, HTTP health returned 200
  with `database=ok`. The temporary database/container were removed afterward.
- TLS policy tests cover certificate/hostname validation, conflicting URL options,
  secure production settings and SMTP ordering/failure behavior.

The local container smoke used development mode and a local non-TLS database.
It does not establish real provider connectivity, domain ownership, delivery,
encrypted disks/backups, hosted restore success or deployment-scale performance.
Those checks require the chosen target and credentials. Follow
`render-deployment-plan.md` if Render is confirmed; use `backup-recovery.md` only
where its Linux/Compose commands fit the actual host.
