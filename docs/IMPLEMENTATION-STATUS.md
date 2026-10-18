# Implementation status — backend foundation release

This release begins the requested phased implementation and includes functioning client/admin business workflows. It does not claim the entire specification is complete or production-ready.

## Implemented and locally tested

- Flask factory, SQLAlchemy models, initial Alembic migration, development SQLite; PostgreSQL driver/configuration supplied.
- Shared login, registration, generic login/reset-request responses, password policy, Argon2id, CSRF, rate limits, server-side session lookup/expiry/revocation and rotation at login, suspended-account rejection, POST logout.
- Client/admin redirects, admin/support/billing/client permissions, customer ownership enforcement, current-password confirmation for sensitive financial/user actions, last-active-admin protection.
- Explicit two-user development seeding, randomly generated credentials, reset/remove commands, production configuration checks and demo-account startup rejection.
- Live database dashboard counts; redesigned client/admin workspace using the archived homepage logo and local Inter/Aldrich fonts, refined navy/yellow styling, animated transitions, reduced-motion support, collapsible permission-aware sidebar and accessible mobile drawer.
- `/admin/users`: real paginated/searchable/filterable/sortable directory, registration/last-login/session counts, active services and orders, bulk session revocation and guarded suspension. `/admin/users/<id>` includes profile, services, orders, invoices/payments, wallet, tickets, sessions, activity/security tabs, restricted internal notes, secure password-reset queue, Super Admin role controls, last-Super-Admin protection and soft-delete/redaction preserving financial history. `/admin/users/new` creates accounts and issues expiring password-setup links through the email outbox. Profile/email/preferences/verification and role changes are audited.
- Guided four-step hosting plan editor with category/location/processor selection, database-backed plan tabs, prices, verified availability and revision history. SEO, add-ons and multi-location allocation remain unavailable and are labeled.
- Category/location/processor records; create/edit/review/publish/hide/archive plans; reusable optional location/processor association; JSON category-specific resources; multiple billing cycle price rows, stock, revision history.
- Review-only import of visible archived cards with evidence and unverified prices; 102 visible plans imported locally. Hidden variants are not covered.
- Filterable maintained catalog and API, single-plan checkout, server-calculated totals and percentage coupons with expiry/global-use/category limits.
- Idempotent order submission, stock reservation/restoration, immutable purchase snapshots through application routes, unpaid cancellation, invoice records/details/PDF downloads.
- Independently verified manual payment recording, unique payment references, paid-only manual fulfillment, duplicate fulfillment prevention, service detail and renewal/change/cancellation request records.
- INR wallet adjustment ledger, reason/reference/audit requirements, duplicate prevention and insufficient-balance rejection. No customer credits or wallet spending endpoint.
- Ticket creation, departments, replies, close/reopen, staff queue and internal notes hidden from clients. Plain-text rendering is escaped.
- Scheduled/pinned announcements, editable/publishable knowledgebase articles and search.
- Responsive navy/yellow Jinja panels, password visibility, accessible form labels/focus, confirmation prompts and reduced-motion support.
- Health/readiness endpoints, source tests, migration files, development setup and deployment examples.

## Implemented code, requires infrastructure or further validation

- SMTP outbox, RQ dispatch/worker and retries: requires SMTP/Redis. Local tests do not send real email. Configure credentials and validate actual delivery before enabling password reset in production. SMTP delivery is at-least-once; crashes after acceptance can duplicate a message.
- PostgreSQL constraints/row locks and multi-worker Redis limits: configured but not integration-tested against running PostgreSQL/Redis here. Concurrency/load testing is required before real billing.
- Gunicorn/Nginx/systemd/TLS/Cloudflare deployment examples: provided, not deployed or tested on your server.
- PDF invoices are simple operational documents, not jurisdiction-validated tax invoices. No tax calculation is implemented.

## Not implemented — explicit remaining work

- Full migration of original public product sections to database-driven rendering. Their archived cards still show static estimates. Only `/catalog` is synchronized now.
- TOTP enrollment/challenge/recovery codes, customer email verification/change workflows, security alert emails and per-session revoke UI (all-session revoke exists).
- Multi-item persistent cart, configurable add-ons, pricing promotions/taxes, separate immutable invoice item entities, auto-renewal invoicing, wallet payments, refunds/credit notes/receipt documents, per-user coupon limits and plan-specific coupon restrictions.
- Real Stripe, Razorpay or PayPal adapters, credential vault/encryption, checkout sessions and signed/idempotent webhooks; mock gateway. Interfaces only; no endpoints claim payment success.
- Real Pterodactyl/Proxmox/LXD/Docker/cloud provisioning, health monitoring, credentials vault, server console/actions/backups; automatic service suspension/expiry jobs.
- Ticket attachments (no uploads accepted), staff assignment/priority/canned replies, service-request resolution workflow and internal customer notes/history detail UI.
- Detailed revenue/registration charts and analytics, bulk account deletion, granular configurable permission editor (fixed role permission matrix exists).
- Product duplication, configurable ordering/featured state, structured hardware technical fields, many-to-many plan/location/processor variants, stock reservation expiry and a complete hidden-variant import.
- Website hero/About/team/careers/footer CMS and media library; existing v4 pages remain preserved. Article helpfulness voting and rich markup are not enabled.
- Notifications/preferences, referral dashboard, download center, general settings/payment/email settings UI.
- Independent penetration test, production integration test, live gateway/SMTP tests and load/concurrency tests.

## Next work

1. Migrate public product sections and verify every price/variant with the owner.
2. Finish account 2FA, structured CMS, uploads and advanced billing models with migrations.
3. Implement one real payment and one provisioning adapter with sandbox contract tests.
4. Validate PostgreSQL/Redis concurrency, SMTP, backups/restore and deployment before accepting customers.
