# Local verification — 2026-10-18

- Python 3.12, dependency versions recorded in `requirements-tested.lock`.
- `pytest -q`: **36 passed**, 21.24 seconds, isolated temporary SQLite databases. Source in `tests/`.
- Chromium browser checks: **145 route/viewport checks**, desktop 1920/1440/1024px and tablet/mobile 768/390/360px. Covered shared login and role redirects, both panels, guided plan creation and public catalog sync, profile edit reflected in client view, tickets, mobile drawer, logout, and preserved Home/About/Careers pages. Checked headings, document overflow and uncaught page exceptions. External requests were blocked; expected browser console messages from those blocked third-party assets are excluded from app-error checks. Source in `tests/browser.cjs`.
- Login screenshots inspected for desktop and mobile layouts. Screenshots are not included in the deliverable.
- User-directory migration applied to both a fresh SQLite database and a populated copy of the prior schema; the existing user row and role survived and the new Super Admin role constraint was verified. `flask db check`: no new upgrade operations detected.
- `flask import-catalog`: 102 visible draft plans on first import; 0 added on repeat import.
- Python compilation succeeded.

No live payment, provisioning, external email, PostgreSQL server, Redis server, Nginx deployment or Cloudflare tunnel was exercised. Tests do not claim those integrations work. SMTP worker behavior was tested with a mocked SMTP transport only. Automated idempotency tests are sequential; production concurrency remains unverified. This is a development release, not a production acceptance certificate.
