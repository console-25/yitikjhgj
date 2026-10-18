# Deployment reference — Ubuntu 24.04

These are deployment examples, not evidence of a deployed production system. Complete the feature/security gaps in IMPLEMENTATION-STATUS.md before accepting real customers. Do not deploy the development database, demo users or static archive alone.

## Host setup

Use a dedicated non-root `noryx` system user. Install Python 3.12/venv, PostgreSQL, Redis and Nginx using Ubuntu packages. Create `/opt/noryx/app` for this source and `/opt/noryx/venv` for dependencies. Keep application source owned by a deployment account/root and readable but not writable by the application user; only `/opt/noryx/app/instance` must be writable. Install `requirements.txt` into the virtual environment.

Create a PostgreSQL role and database dedicated to Noryx using an interactive administrative session. Use a randomly generated database password. Keep PostgreSQL and Redis on loopback or a private protected network, not the public Internet. Enable authenticated/encrypted connections when crossing machines. A separate migration role and restricted runtime role are recommended before launch.

Copy `.env.example` to `/etc/noryx.env`, owned by root and readable only by root/noryx (mode 0640). Set:

- `NORYX_ENV=production`
- `SECRET_KEY`: fresh output from `python3 -c "import secrets; print(secrets.token_hex(32))"`
- `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@127.0.0.1/DBNAME` (URL-escape credentials)
- `REDIS_URL`: your authenticated Redis URL
- `PUBLIC_URL=https://YOUR-VERIFIED-DOMAIN`
- `TRUST_PROXY=1` only with the supplied single trusted proxy topology
- Verified SMTP settings when enabling email

No default production secret is provided. EnvironmentFile values must be valid systemd environment assignments. Keep all actual credentials out of source, screenshots and support tickets.

## Migrate and create the administrator

Load the environment through your service/deployment mechanism, then from `/opt/noryx/app` run the virtual environment's commands:

```bash
flask --app wsgi db upgrade
flask --app wsgi create-admin
flask --app wsgi import-catalog
flask --app wsgi db check
```

Do not run `db.create_all()` on a deployment database. Do not seed demo users in production. Use a clean production database; startup rejects flagged demo accounts. Import is review-only. Verify/publish products after deployment validation. Back up before every schema upgrade and inspect migration code first. Downgrades can delete data and are not a routine rollback mechanism.

## Application and proxy

Install `deploy/noryx.service` into `/etc/systemd/system/` and adapt paths if needed. It binds Gunicorn to loopback. Install the Nginx example, replace every placeholder domain/certificate path, provision a TLS certificate using your trusted certificate automation, and validate `nginx -t` before reloading. Do not leave placeholder `hosting.example` in the live configuration. Use Secure cookies, HTTPS and HSTS.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now noryx
sudo systemctl status noryx
```

Proxy every route to Flask so legacy client paths cannot bypass authentication by serving archived HTML directly. Do not configure PHP-FPM. Restrict SSH and firewall access appropriately; Gunicorn, Redis and PostgreSQL must not be public.

## Email worker

Configure SMTP_HOST/PORT/USER/PASSWORD/FROM and STARTTLS. Install and enable `noryx-worker.service` and `noryx-mail-dispatch.timer`/`.service`. The dispatcher requires Redis and SMTP configuration; it does not pretend to deliver email when disabled.

```bash
sudo systemctl enable --now noryx-worker noryx-mail-dispatch.timer
```

The outbox persists jobs; the worker sends SMTP mail with RQ retries. Observe failed jobs through your Redis/RQ operations tooling. Verify delivery in a provider sandbox before real password resets. Reset emails contain sensitive short-lived links; restrict database/outbox access and backups. Bodies are cleared after successful delivery. SMTP cannot guarantee exactly-once delivery; a crash after acceptance may result in a repeated email. This release has no built-in admin email-log/retry screen.

## Cloudflare Tunnel

A tunnel can target the loopback Nginx origin. Keep PUBLIC_URL set to the external HTTPS address and use HTTPS between tunnel and origin when practical. Confirm the exact trusted proxy chain before using ProxyFix. The supplied Nginx config overwrites forwarded headers, so client rate limits may aggregate at the tunnel's address unless you configure trusted Cloudflare real-IP handling. Do not blindly trust arbitrary `CF-Connecting-IP` or X-Forwarded-For headers. Keep origins inaccessible directly. Validate Secure-cookie, CSRF and client-IP behavior through the tunnel before launch.

## Operations and backups

- `/health/live`: process liveness. `/health/ready`: database schema query and Redis connectivity if configured; returns 503 on dependency failure without leaking credentials.
- Capture Gunicorn/systemd errors and failed RQ jobs. Do not log request bodies, passwords, reset URLs or full environment values.
- Create scheduled encrypted `pg_dump --format=custom` backups using a private credential mechanism such as protected `.pgpass`, not passwords in shell history. Store copies separately, limit retention/access, and test `pg_restore` into an isolated database.
- Back up source/migrations and protected configuration separately. Redis queue persistence/backup should match your mail delivery policy. Monitor disk usage, DB connections and mail failures.
- Restore-test schema and representative rows, then run readiness, login and read-only account smoke tests. A successful dump alone is not a verified backup.
- Before upgrading, record application version and database revision, back up, stage migration, run tests, deploy, migrate and restart. Roll back code only when compatible with the migrated schema.

PostgreSQL concurrency, Redis multi-worker behavior, real SMTP delivery, TLS/tunnel and server service files were not exercised in the local SQLite/browser checks. They remain deployment acceptance tasks.
