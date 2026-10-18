# Noryx Hosting — repaired website export, v4

## Preview

From this directory, run:

```bash
python3 preview.py
```

Open http://127.0.0.1:8081/ . Press Ctrl+C to stop. To use another port, run `python3 preview.py --port 8082`.

Extract this release into a fresh directory rather than mixing it with earlier releases. The preview server sends no-cache headers and the repaired scripts have a new cache version. This prevents earlier broken bundles from being reused.

## Repairs

The existing layout, sections, typography and components are retained. Branding is Noryx Hosting with the supplied logo, and purple theme colors are replaced with yellow/gold. Product artwork is retained.

- Restored the correctly decoded `[gameName]` script directory. Its encoded filename caused all nine game detail pages to fail.
- Restored background image and Minecraft plan-icon locations expected by the original JavaScript.
- Corrected serialized React text-record lengths after branding edits.
- Changed the export bootstrap to mount the original components directly, avoiding reconciliation against the modified archived HTML. This addresses the repeated hydration errors and incomplete rendering without rewriting the frontend components.
- Disabled automatic Next.js route prefetching and retained normal page navigation for this static export.
- Removed inherited chat/tracking loaders and disconnected Google sign-in markup that depended on the original owner's backend configuration.
- Fixed dark-button text contrast and added cache-safe local previewing.

## Backend limitation

The uploaded archive was a downloaded website mirror. Its `.php` paths are folders of saved HTML, not executable PHP. It contains no backend application source, database schema, authentication service, billing engine, payment gateway integration or provisioning code.

This release repairs the available frontend/export. Login, registration, checkout, tickets, reseller OTP/application and other server operations remain unavailable. Saved client pages are previews only. Requests requiring the missing backend are blocked with an unavailable message; no fake successes are generated.

To repair those features, provide the actual application repository or source ZIP, dependency manifests, migrations/schema and sanitized example configuration. Do not include live passwords, tokens or private keys. If the original client system is WHMCS, its licensed installation and relevant custom templates/modules are required.

Some public Minecraft tools use external APIs. Their network-dependent operations require separate testing with those services available. Currency conversion uses the archive's estimates, not a live exchange-rate feed.

## Before deployment

The real Noryx domain, email addresses and social links were not provided. `noryx.example` is a reserved placeholder, not a live destination. Old-brand contact destinations are disconnected. Configure verified contact details before launch.

Review inherited prices, staff names/photos, testimonials, founding dates, legal policies and infrastructure claims. They remain content from the supplied archive, not verified facts about Noryx Hosting. The original commitment page, administrative source and billing services are absent. Some archived client decorations/country flags were not included.

Serve `site/` at the domain root, not a subdirectory. Example Nginx directives for a static preview:

```nginx
root /var/www/noryx-hosting;
index index.html;
location / {
    try_files $uri $uri/ =404;
}
```

Use your own domain and TLS configuration. Do not send these saved `.php` directories to PHP-FPM. `preview.py` is for local preview only and is not an application backend.

## Reconnecting actual source

The original editable frontend source/build configuration is also absent. These are repaired compiled bundles. When the actual source is available, apply the branding there and rebuild normally. The static navigation/backend guards in `assets/js/noryx-runtime.js` should be removed only when the corresponding real services have been restored and tested.

## Verification of v3

All 72 saved page routes were loaded and scrolled in Chromium at desktop width; eight representative routes were also checked at 390px mobile width. These 80 checks recorded no uncaught JavaScript exceptions, HTTP error responses, broken loaded images or horizontal document overflow. External network requests were blocked during the audit, so live external API operations were not validated. All 232 JavaScript files passed syntax checks. These checks do not validate absent backend services or every possible interaction.

## v4 content update

About timeline: QuickHost, HyperCloud and Noryx Hosting dated November 5, 2026. Team: one Console card, @console.gg, Founder, supplied portrait and unchanged founder bio. Careers: We're Hiring!, with the contradictory closed-hiring paragraph updated. Both pages verified in Chromium at 1440px and 390px widths with no page exceptions.
