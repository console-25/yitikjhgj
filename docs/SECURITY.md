# Security notes and local verification

Passwords use Argon2id. The browser stores a signed HttpOnly/SameSite cookie containing an opaque random session identifier; its hash, user and expiry are stored server-side. Login rotates the identifier, logout deletes it, and password resets revoke all user sessions. Production enables Secure cookies. No tokens are placed in localStorage. CSRF covers all mutation routes including login/logout. Reset URLs use the configured PUBLIC_URL, not the request Host header. Reset tokens are hashed, expiring and single-use.

Permissions come from the database, never form role fields. Ownership queries protect customer orders/invoices/services/tickets. Staff access is limited by fixed role permissions. Internal notes are omitted from client responses, not merely hidden in CSS. Jinja escapes user text. New panels use a self-only Content Security Policy; the archived public export needs inline scripts/styles and has no strict CSP yet.

Manual payments and fulfillment require reauthentication and an external reference. No payment/provisioning callback endpoint is enabled. Catalog amounts from forms are ignored at checkout; money uses integer minor units. Orders snapshot purchased resources/prices. Application routes do not mutate payment/ledger history. Database administrators can still alter rows; use restricted database access and independent backups/audit retention.

Local tests cover authentication, CSRF, role restrictions, IDOR, suspended login, logout revocation, checkout price tampering, sequential idempotency, coupon limits, payment/fulfillment state transitions, stock restoration, reset expiry/reuse, last administrator, wallet reference uniqueness and balance checks, staff-note confidentiality, escaped text, PDF generation, route rendering and explicit demo lifecycle. They do not establish production security. SQLite tests do not prove PostgreSQL concurrent transaction behavior. There is no upload implementation; tests verify an upload endpoint is unavailable rather than claiming upload validation exists.

The development in-memory rate limiter is single-process. Production requires Redis. Behind the provided single trusted Nginx proxy, enable TRUST_PROXY=1 and keep Gunicorn bound to loopback; do not expose a ProxyFix-enabled application directly. Never trust arbitrary forwarded headers.

No real credentials, generated passwords, local databases, environments or test browser session files belong in the ZIP. Test fixture passwords are public test-only values used solely in isolated temporary databases; they are not demo/login credentials for the application.

Before production: finish the remaining features listed in IMPLEMENTATION-STATUS.md, use a clean PostgreSQL database, configure secure SMTP and shared Redis, verify gateway contracts, test concurrent changes and stock expiry, enable 2FA, validate email ownership, validate business/legal/tax content, and perform an independent security review.
