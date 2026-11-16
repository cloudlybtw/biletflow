# Render deployment plan — 2026-11-16

Status: planning resumed; **Render is a provisional option for web/API/database**.
The user subsequently questioned the need for Render. Local Docker is sufficient
for a local demo; confirm public-hosting intent/provider/budget before provisioning.
No services, subscriptions, secrets, domains or public deployments have been
created. Budget is still awaiting the user's answer. Do not apply a paid Blueprint
or connect a repository until the concrete configuration/cost is reviewed.
Physical camera/printed-ticket acceptance remains explicitly deferred.

## Proposed topology

| Component | Render resource | Application configuration |
| --- | --- | --- |
| React/Vite | Static site | `npm ci && npm run build`, publish `dist`; build-time `VITE_API_BASE_URL=https://<api-host>/api/v1` |
| FastAPI + expiry/outbox | Docker web service, one instance/process initially | Bind `0.0.0.0:$PORT`, health `/api/v1/health`, no reload |
| Database | Managed PostgreSQL 16, same region as API | SQLAlchemy asyncpg DSN, strong service credentials, enforced/verified TLS where supported by the chosen endpoint |
| Event/support uploads | Persistent disk on API service | `MEDIA_ROOT=/var/data/media`; never store uploads on ephemeral root filesystem |
| Email | Transactional SMTP provider | Verified sending domain; authenticated TLS SMTP support is prepared locally |
| Recovery | Managed DB PITR/exports + persistent-upload snapshots + independent copy | Restore DB and matching uploads in isolation; protect backups and verify recovery before real data |

The background expiry/outbox loop already starts inside FastAPI's lifespan.
Do not add a second independent mail worker by accident. Keep one process/instance
while uploads are local and rate limits are process-local; scaling requires shared
storage/client-aware limits and a review of worker coordination.

Render static assets and API have different origins in this topology. Configure
`CORS_ORIGINS` to the exact HTTPS frontend origin; `WEB_BASE_URL` must be that
frontend origin for reset/verify/campaign links. Vite variables are baked into the
build: changing API host requires a frontend rebuild. Keep API-returned media URLs
compatible with the client's authenticated download logic. Configure static-host
security headers rather than assuming the Docker Nginx CSP also protects a Render
static site. Include the API origin in connect-src; do not loosen object/frame
policies. Current hash routes require no clean-path routing migration.

## Local preparation completed; target configuration still required

1. Authenticated SMTP is prepared locally with certificate-verified STARTTLS or
   implicit TLS. Set `SMTP_SECURITY=starttls` (usually port 587) or `ssl` (usually
   465), plus both `SMTP_USERNAME` and `SMTP_PASSWORD`. Partial credentials and
   plaintext authentication are rejected. Mailpit retains default `none` mode.
   Tests verify TLS precedes login, certificate/hostname validation, secret
   redaction and that TLS failure never sends credentials/messages.
   Choose provider, sender domain and credentials through secret configuration;
   never put passwords/API keys in a Blueprint, logs or browser assets.
2. Provider `postgres://` and `postgresql://` URLs now normalize to asyncpg.
   `DATABASE_SSL_MODE=verify-full` validates both certificate chain and hostname;
   an optional `DATABASE_SSL_CA_FILE` supports a private CA. URL TLS settings that
   conflict with the explicit mode are rejected. Production settings also reject
   development/placeholder JWT secrets, non-HTTPS origins and plaintext SMTP.
3. `backend/Dockerfile.production` is prepared with locked runtime dependencies,
   golang-migrate, a non-root user and one Uvicorn process bound to `$PORT`.
   `python -m app.scripts.migrate --confirm-up` applies forward migrations as a
   separate release step. Never run destructive demo reset or public demo seeds.
   Build and isolated local smoke tests passed: migrations through `0009`, repeat
   migration invocation, UID 10001 and HTTP/database health. This local smoke used
   disposable PostgreSQL with TLS disabled; it does not prove hosted TLS.
   See [production runtime instructions](production-runtime.md) and the placeholder
   configuration in `deploy/production.env.example`.
4. Prepare the Render Blueprint with actual selected plans, region, disk size,
   names/origins and runtime secrets. Keep automatic deployment disabled until
   first smoke test and rollback procedure are reviewed. Export Android/iOS demo
   builds with the deployed HTTPS API base only after API validation.
5. Configure DB/uploads backup retention, separate copies and failure alerts.
   The existing backup script calls Docker Compose, stops a local API container
   and writes local archives. **It is not a managed Render backup scheduler.**
   Retain it for local recovery drills; adapt hosted backup procedures to Render.
6. Verify provider DB/disk/snapshot encryption evidence and external TLS on both
   public services. Hosting a frontend on HTTPS alone does not establish SRS
   encryption for DB, uploads, SMTP and backups.

## Budget gate

- Free-only is acceptable for a disposable demonstration with explicit retention,
  sleep and recovery limitations; do not claim durable private uploads or managed
  recovery without the corresponding available service features.
- Persistent disks require paid services. Paid Postgres provides PITR; free
  Postgres does not provide Render recovery. Select plans after checking the live
  provider quote and user's monthly ceiling, including disk, DB, egress, SMTP,
  independent backups and any workspace fees. No recurring spend is authorized.
- Do not silently replace persistence/backup requirements with an ephemeral free
  service to fit a budget. If the budget cannot cover the selected features,
  present a disposable-demo scope or a revised topology for approval.

## Release and rollback sequence

1. Confirm budget, region, domain and data scope (demo only versus real users).
2. Review final Blueprint and estimated monthly cost; connect Render/GitHub only
   for this repository with the minimum necessary authorization.
3. Provision chosen DB/disk/API; configure secrets privately; migrate; verify API
   health and authenticated routes. Never expose the DB unnecessarily.
4. Build static frontend with actual HTTPS API origin; set exact CORS and headers.
5. Smoke-test verification/reset email, event images, private support attachments,
   checkout/payment/PDF, refunds/cancellation, calendar updates and check-in.
6. Restart/redeploy API and verify uploaded files remain. Test backup restore into
   an isolated DB/media instance with outbox sending disabled. Confirm no restored
   email queue accidentally sends historical mail.
7. Establish a baseline with paid/free checkout and reporting load, using agreed
   latency/capacity targets. Record limits instead of claiming production readiness.
8. Before future schema changes, back up and inspect migration compatibility.
   Roll back application only to compatible schema. Do not automate destructive
   database downgrade or overwrite production as a recovery shortcut.

## Decisions still needed

- Monthly budget (asked; not yet answered).
- Render account/workspace access, region and frontend/API names or custom domain.
- Email provider and verified sender domain; secret injection method.
- Upload volume/retention and independent backup destination/alerts.
- Demo-only versus real-user data and agreed recovery/performance objectives.

## Primary provider references (checked 2026-11-15)

- [Render FastAPI deployment](https://render.com/docs/deploy-fastapi)
- [Web services and port binding](https://render.com/docs/web-services)
- [Managed Postgres creation and connections](https://render.com/docs/postgresql-creating-connecting)
- [Postgres recovery and backups](https://render.com/docs/postgresql-backups)
- [Persistent disks, encryption and limits](https://render.com/docs/disks)
- [Blueprint reference](https://render.com/docs/blueprint-spec)
- [Current pricing](https://render.com/pricing)
