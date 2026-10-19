# Noryx workspace update

The authenticated workspace now uses a consistent navy and Noryx yellow theme, compact navigation, responsive tables and forms, and a scenic sign-in page. The existing public homepage and its Console founder profile are preserved.

## Screens and behavior

- Shared shell: grouped role-aware navigation, mobile drawer, workspace page search, account menu and accessible confirmation dialogs.
- Admin overview and analytics: actual account/service/order totals, seven-month payment chart with separate reporting currencies, service category chart and recent audit events. No exchange-rate conversion or invented revenue.
- Catalog: category/location/processor tabs, searchable tables, five-step plan editor, resource fields backed by the existing JSON specification, saved billing-cycle selection, stock, featured status, display order and revision editor attribution.
- Orders: server-side customer/plan/order search, status filters, sorting, 25-record pagination and a detail drawer. Manual payments and fulfillment retain password reauthentication. Unpaid rejection releases reserved stock through the existing cancellation transaction.
- Support: searchable ticket table, saved priority, staff assignment and status controls. Internal replies retain staff-only visibility.
- Content: announcement/article tabs, table summaries, modal editing, scheduled publication and announcement archiving.
- Settings: Super Admin-only saved workspace name, public URL, timezone, reporting currency, registration availability and approved logo selection. Password-reset links use the saved public URL.
- Additional pages: locations, processors, stock, invoices, transactions, staff, approved media, provisioning queue, email queue and readiness links.
- Remaining account, user profile, checkout, service, invoice, wallet and help pages inherit the shared theme and retain their existing backend operations.

Anime.js 3.2.2 is bundled locally with its MIT license. Motion covers page/card entrances and revenue chart drawing; existing counters and wizard transitions remain. Reduced-motion preferences are respected. Critical content is visible without entrance observers.

## Database and safety

Migration `c83a41d9a120` adds workspace settings, add-on definitions, plan presentation fields, ticket priority/assignment and announcement archiving. Existing money records and historical order snapshots are preserved. SQLite uses native additive schema operations so populated foreign keys and unnamed plan CHECK constraints survive.

The existing `68a02e0f29f2` migration fixes the stale user-role CHECK constraint that previously blocked `create-admin` with `super_admin`.

Self-suspension/demotion and removal of the last active Super Admin are refused. Ticket assignees must be active support-capable staff. Settings and billing mutations remain CSRF-protected and permission-checked.

## Verification

- 44 pytest checks passed, covering existing authentication/billing/catalog behavior plus new settings authorization, registration controls, ticket assignment, announcement visibility, currency isolation, order rejection, search/pagination and Super Admin protection.
- Populated SQLite upgrade, downgrade and re-upgrade preserved table counts, foreign-key validity and plan stock/status CHECK constraints.
- Browser coverage at 1440, 768 and 390 pixels included admin/client routes, image loading, document overflow and JavaScript errors. Workflow checks exercised wizard saving, published catalog updates, content saving, ticket assignment, workspace search, order drawers, cancellation confirmation, mobile navigation and reduced motion.
- Browser fixtures use disposable synthetic accounts and payment records; none are shipped or inserted into the production database.

## Deliberately unavailable integrations

Automatic gateways, provider refunds, node management, automated provisioning, external monitoring and media uploads are not connected. Their pages explain the limitation and disable unavailable controls. Add-ons can be defined but are not purchasable or allocated. Email delivery still requires server SMTP configuration and the existing worker. Local validation used SQLite and Chromium; PostgreSQL and the remote VPS were not exercised in this session.

## Deploy

Back up the actual configured database first. Then, from the existing checkout:

```bash
cd ~/yitikjhgj
source .venv/bin/activate
git pull --ff-only origin main
flask --app wsgi db upgrade
```

Restart the process serving Flask/Gunicorn. If the repository's supplied systemd service is installed, use `sudo systemctl restart noryx`. Confirm `/health/ready` and sign in. The migration must run before serving the updated workspace.

For the previous administrator-creation failure, run `flask --app wsgi create-admin` after upgrading. Choose a unique password of 12–128 characters including letters and a number; enter the exact same value twice.
