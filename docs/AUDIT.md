# Existing website audit and architecture

## Source preserved

The recovered v4 contains 1,505 website files, including compiled Next.js/React bundles, 72 index routes and a search page. It is an export, not an original Next.js project. The archived `.php` paths contain HTML snapshots, not PHP code. There was no original authentication, billing, database or server provisioning source to repair.

The v4 logo, yellow public theme, About timeline (QuickHost, HyperCloud, Noryx Hosting — November 5, 2026), Console / @console.gg / Founder card and portrait, and Careers hiring copy remain intact. No compiled bundles were modified for this backend release.

## Architecture

Flask application factory + SQLAlchemy relational models + Alembic migrations + Jinja templates. New application CSS and JavaScript live in `noryx/static`, independently of the archived export. Money uses integer minor units. Historical orders contain a purchased-plan snapshot; invoices do not look up live catalog prices.

- `noryx/__init__.py`: configuration, extensions, response headers, production checks.
- `noryx/models.py`: persistent users, sessions, catalog, orders, invoices, payments, services, wallet ledger, tickets, articles, announcements, audits, email outbox.
- `noryx/security.py`: Argon2id, server-side session records, RBAC, ownership checks, reauthentication.
- `noryx/business.py`: stock reservation, coupons, checkout idempotency, payment and fulfillment state transitions.
- `noryx/routes.py`: public/account/admin controllers and legacy route bridge.
- `noryx/cli.py`: explicit seed/admin/import/email-dispatch commands.
- `noryx/jobs.py`: SMTP delivery worker.
- `noryx/integrations.py`: provider protocols, unavailable by default. These are boundaries, not working gateway integrations.

## Route mapping

| Existing destination | Application destination |
| --- | --- |
| `/`, `/about/`, `/careers/`, public content/tools pages | Preserved export served by Flask |
| `/client/`, archived client index/login routes | Shared `/login`, or appropriate dashboard when signed in |
| Archived client registration routes | `/register` |
| Archived store/cart/order routes | `/catalog` |
| Archived client ticket/contact routes | `/client/tickets` |
| Archived invoice routes | `/client/invoices` |
| Unconfigured contact placeholders / reseller form submission | Support entry point |

Archived client pages are no longer served as functioning account screens. Old saved client files remain in the archive for reference, but Flask routes take precedence.

## Catalog audit

`flask import-catalog` imports 102 visible plan cards across the available product pages into review. Repeating the import does not duplicate matching category/plan names. A source text snapshot records the visible name, price and resources. Explicit monthly INR display amounts are retained as unverified draft prices; quarterly/yearly prices, missing prices, processor associations and stock are not invented. Specifications must be verified and entered into structured fields before publishing.

The source has configuration-dependent products (notably VPS and Minecraft variants), client-side currency conversion estimates and marketing starting prices. The importer does not execute compiled JavaScript or infer every hidden combination. Some source headings/cards may repeat across products; an administrator must review drafts. Hardware records are created explicitly by administrators; optional location/processor levels are supported.

## Public catalog migration still required

`/catalog`, `/api/catalog`, checkout and admin edits use the same database. However, the original marketing pages still render their archived product cards and estimated prices from compiled bundles. Those cards do **not** synchronize with admin edits. Their legacy purchase links route to the maintained catalog for actual selection and checkout.

Full synchronization of every original product section is NOT complete. The next frontend phase should reconstruct each product section as a maintainable template/component using the existing design, replace its compiled component at the original source level where available, and use database records exclusively. Do not launch the archived prices as verified offers. The current backend is a development foundation, not the completed production platform requested in the specification.

The original export also retains inherited testimonials, legal text, infrastructure claims and placeholder domains. Review those before public launch. External Minecraft tools and currency rates are outside the backend acceptance tests.
