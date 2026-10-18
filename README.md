# Noryx Hosting — Python backend foundation

The v4 public website and your About/Careers changes are preserved. This release adds a Flask application with shared login, client/admin panels, a maintained catalog, orders, manual billing/fulfillment, support and content tools.

**This is a phased implementation, not the complete production platform.** Read `docs/IMPLEMENTATION-STATUS.md` for implemented features and remaining work. In particular, original marketing product cards still contain archived prices; only the new `/catalog` is database-driven. Live payments and automatic provisioning are not connected.

## Run locally (Python 3.12+)

Extract the ZIP into a fresh folder, then open a terminal in `Noryx-Hosting`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask --app wsgi db upgrade
flask --app wsgi import-catalog
flask --app wsgi seed-demo
flask --app wsgi run --host 127.0.0.1 --port 8081
```

On Windows, activate with `.venv\Scripts\activate` and copy `.env.example` using `copy .env.example .env` instead.

Open http://127.0.0.1:8081/ or http://127.0.0.1:8081/login . Both demo users use the same login page:

- `client@noryx.test` → client dashboard.
- `admin@noryx.test` → admin dashboard.

The seed command prints two newly generated unique passwords in your terminal. Copy them then; they are not stored in documentation. No accounts are automatically created. Running the seed command again retains existing accounts. To generate replacement credentials:

```bash
flask --app wsgi reset-demo-credentials
```

To remove demo accounts and their owned development activity:

```bash
flask --app wsgi remove-demo
```

A development signing key and SQLite database are created in `instance/`, which is excluded from the deliverable. Production needs a configured random SECRET_KEY, PostgreSQL, Redis and HTTPS PUBLIC_URL. For a real Super Admin, run `flask --app wsgi create-admin` and enter a private password at the hidden prompt. The development demo admin intentionally has the Admin role; only a Super Admin can change account roles or grant elevated access.

## Try the workflows

1. Sign in as the admin and open Hosting catalog. Imported plans start in review with zero stock. Verify the draft source evidence, prices and resources; set available stock and publish a plan. Create/verify any optional location/processor records.
2. Sign in as the client in another browser/profile. Open `/catalog`, choose a billing cycle and place an order. The server calculates price; an invoice is generated. No money is collected.
3. In admin Orders & payments, independently verify a real offline payment before recording its reference. For development, use clearly labeled test references only.
4. Manually configure the service, then record completed fulfillment with its actual reference. The client can view their service and request renewal/change/cancellation.
5. Create/reply to support tickets. Staff internal notes remain private. Edit announcements/articles in Content.

For a visual-only copy of the old public export, `python3 preview.py` remains available. It does **not** run the backend, and account/catalog links need Flask. Use the Flask command above for this release.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
flask --app wsgi db check
```

Browser test source: `tests/browser.cjs`. Install Playwright separately (`npm install --no-save playwright`, `npx playwright install chromium`). With the app running and the two seeded demo accounts, provide a private JSON mapping each demo email to its generated password:

```bash
BASE_URL=http://127.0.0.1:8081 CREDENTIALS=/private/credentials.json node tests/browser.cjs
```

Do not commit that JSON. The browser suite creates test support tickets and edits the disposable demo client profile; it expects a published test plan with price ID 1 in a disposable database. Optional `CHROMIUM_PATH` chooses an installed browser. No browser binaries or node_modules are included.

## Documentation

- `docs/AUDIT.md`: recovered source, architecture, route mapping, import scope.
- `docs/IMPLEMENTATION-STATUS.md`: honest completion checklist and next phases.
- `docs/SECURITY.md`: protections, test scope and limits.
- `docs/DEPLOYMENT.md`: Ubuntu deployment, SMTP/Redis, backups and Cloudflare notes.
- `docs/STATIC-EXPORT-HISTORY.md`: preserved v4 repair history; its backend limitation is historical.

No PHP runtime is required. Serve the application through Flask/Gunicorn, not the `site/` directory alone.
