# Google Backend Compliance and Reliability Design

## Intent

Harden the existing Somo LeadFinder Flask application using the current official Places API documentation, preserve authentication, Google OAuth, plans, Freemius checkout, and the general search/dashboard experience, and make unsafe or unverified Places-data handling explicit. The strict policy-first data rules remain: only Place IDs may be persisted as Google Places data, and Places-derived fields must not be saved in My Leads or exports. On 2026-11-02, the owner confirmed that scraping business websites returned by Google Places for publicly available contact/social links was reviewed and approved under applicable terms.

This is a code-level design, not a claim of legal or live-production approval. Google Cloud's actual quota, account billing region, current SKU prices, deployed schema, published Terms/Privacy text, and worker-host availability remain external verification items.

## Goals

- Make supported Places API requests with minimal, documented field masks, a hard maximum of 60 results, and clear handling of 400/401/403/429/temporary 5xx responses.
- Enforce a project-wide request rate in Neon PostgreSQL, with the configured ceiling supplied from the actual Google Cloud quota. Fail closed in production if the ceiling is absent or invalid.
- Retry only documented transient cases with bounded exponential backoff and `Retry-After` handling; avoid logging API keys or full Google response bodies.
- Reserve one user search credit atomically before the first billable search request. Release it when that search fails; commit it once a valid first page succeeds.
- Keep durable search ownership and pagination metadata in Neon. Persist Place IDs only from Google data. Never put Google response objects, names, addresses, phone numbers, URLs, ratings, reviews, types, or page content into durable tables or job payloads.
- Keep ownership checks on all search, status, pagination, and export paths. Generate exports from server-owned records and include only Place IDs and user-entered search metadata.
- Prevent duplicate initial-search or pagination submissions from triggering duplicate Text Search requests by using distinct idempotency keys for the initial search and each logical page request.
- Add attribution near displayed Places content, make the Google content visually distinct, and provide ranking-factor disclosure. Do not fabricate legal Terms or Privacy text; report their required public publication as a manual release prerequisite.
- Harden URL-fetching code against SSRF for the approved, request-scoped website enrichment.
- Keep migrations manual and reviewable. Do not apply migrations or connect to production.

## Non-goals and constraints

- No production DB, Vercel, Neon, Google Cloud, or Freemius changes; no paid requests or payments.
- No new database provider, Redis, external queue, or paid service.
- No claim of 1,000-user capacity without representative load testing.
- Do not persist full Places responses for a cache, export, or background job.
- Website enrichment may use Google Places `websiteUri` values following owner-confirmed policy review. Enrichment remains best-effort, request-scoped, bounded, and excluded from durable storage and exports.
- Do not make a legal determination that exports or any particular use of `websiteUri` is permitted. Only Place IDs are included in generated exports under this design.
- Existing production records may already contain Places data in `exported_leads`. Code will stop reading/writing those fields. A separately documented, manually applied cleanup is needed to remove legacy values; this implementation will not execute it.

## Approaches considered

1. **Strict policy-first (selected):** durable Place IDs and app-owned query/status metadata only; on-demand Places data is transient; no Places fields in My Leads/exports; allow website enrichment after owner-confirmed policy review.
2. **Preserve detailed lead exports:** keep saved phone/address/rating/website fields and exports, add attribution and a map. This preserves the existing product better but conflicts with the requested storage restriction and cannot be called compliant without written Google approval.
3. **Rehydrate every display/export from Place IDs:** store IDs, then make Place Details calls to rebuild page fields. This avoids storing those fields but adds many billable API calls, complicates rate limiting, and still does not resolve whether exporting the rehydrated fields is allowed. Not selected.

## Proposed design

### Places client and billing

- Keep Places API (New) Text Search `POST https://places.googleapis.com/v1/places:searchText`.
- Retain the required `X-Goog-FieldMask`; verify every requested field against the current Text Search field/SKU table before deciding the final mask. Keep fields only when needed for display or approved website enrichment.
- Set `pageSize` to no more than 20 and make at most three Text Search page calls (60 results total). Follow `nextPageToken` sequentially and stop on missing/repeated tokens.
- Keep Places payloads in request/response memory only as needed to render the current response. Do not cache them on the server, store them in Neon, local storage, or durable jobs. The client receives only the current page's data for immediate display; pagination state is held only in volatile client memory and signed POST cursor state.
- Add `GOOGLE_PLACES_QPM_LIMIT` as an explicit runtime setting that must equal a manually verified Google Cloud per-project Places method quota. No default or fallback number is assumed. A Neon-backed atomic minute-window counter coordinates all Flask instances. If the setting is missing or invalid in any environment, the app does not send Google requests and returns service unavailable.
- Call the Neon-backed limiter immediately before every outbound Google HTTP attempt, including each pagination request and every retry attempt. Each attempt consumes its own QPM slot; if the limiter denies the attempt, do not call Google. The limiter must never reserve once per logical page and then allow uncounted retries.
- Add bounded retries for 429 and temporary 5xx, honor numeric or HTTP-date `Retry-After`, and use capped exponential backoff with jitter and a finite attempt/deadline limit. Each retry reacquires a QPM slot. Do not retry validation/authentication/permission errors (400/401/403). Map upstream failures to safe client messages and log status/category only.
- Add mocked tests for URL/method/headers/body/field mask, page limit, parsing, status mapping, retry timing/Retry-After, and rate-limit concurrency. Verify every retry reacquires a QPM slot. Test that same-key and different-key cursor replays, as well as concurrent claims, are rejected without a second Google request, while the next page sequence remains independently claimable. Verify field SKUs against official docs; actual price depends on region and billing account and remains manual.

### Quota, idempotency, and search records

- Add a SQLAlchemy request ledger for initial searches and pagination. Store only a hash of each client idempotency key, unique per user and operation. Pagination additionally has a database-enforced unique constraint on `(user_id, search_id, page_sequence)`, independent of that key. Each page stores app-owned operation status/timestamps and, where needed, keyed fingerprints of its input and next cursor; it never stores Google's token. Initial-search keys and each logical page's keys are separate. Retrying the same page reuses its key; moving to a new page uses a new key and a new page sequence. The initial-success record is page sequence 1 and holds only the fingerprint for its returned next cursor; page sequence 2 validates against that predecessor, and so on.
- Reserve quota using one atomic PostgreSQL conditional update before the initial Google API request; release it after a definitive initial-search failure; finalize the one search charge and create `SearchHistory` on first-page success. Pagination uses its own request-ledger entry and never reserves another user search credit.
- Before a pagination request can call Google, verify the signed cursor and its user/search/page binding, then atomically claim `(user_id, search_id, page_sequence)` in Neon. Store an HMAC fingerprint of the received signed cursor and compare it with the preceding page's recorded next-cursor fingerprint. The unique constraint is the concurrency arbiter: only the transaction that creates the claim may proceed to Google. A conflict, including a replay using a different idempotency key or a simultaneous request, returns the recorded status (or an in-progress response) and never triggers another Google request. The winner holds the claim across bounded HTTP retries; each retry still reacquires the QPM slot. Unknown outcomes remain claimed and are not automatically replayed.
- Distinguish client-level replay from bounded transport retries: another browser submission, with the same or a different idempotency key, cannot make an upstream call after the page identity is claimed. The single request that owns the claim may perform only the explicitly bounded 429/temporary-5xx retry attempts; each attempt is separately QPM-limited. Do not automatically retry ambiguous connection timeouts, because Google may already have processed that request.
- For a repeated completed key/page, return only the recorded operation status and page/search identifiers, not cached Places data. Do not make another Google call. The UI keeps the already received page in volatile JavaScript memory. If a response was lost and the client has no page data, show a recoverable message and require a new search; it must not bypass the completed page claim with a new key. This trades transparent response replay for the no-cache policy.
- Keep query text and status metadata as app-owned data. Do not store Places response objects or field values in the reservation.
- Do not persist Google `result_count` as a copied response field; derive counts from Place-ID rows when needed. Do not persist `nextPageToken` in Neon.
- Preserve `SearchHistory` ownership. Associate every durable search-result row with `user_id`/`search_id`; result rows contain only `place_id` and position. Pagination looks up records by owner. Page tokens are request flow state and are not saved durably.
- Next-page token flow: Google returns `nextPageToken` over HTTPS; Flask returns it only inside a short-lived, signed cursor bound to the authenticated `user_id`, `search_id`, and expected next-page sequence. The signature makes the cursor tamper-evident, not confidential; the authenticated browser necessarily holds the cursor in volatile JavaScript memory. The browser POSTs it in the JSON body for the next page. It is never placed in a URL, cookie, local/session storage, Neon row, job, analytics event, or log. Flask verifies signature, expiry, ownership, and page sequence, unwraps the token only in request memory, then forwards it to Google. Before forwarding, Flask checks the cursor fingerprint against the prior page's stored `next_cursor_fingerprint`; the page-identity unique constraint prevents replay even if the client substitutes a fresh idempotency key. Store only the keyed fingerprint, page sequence, and operation state. Do not log request bodies, cursor contents, fingerprints, or upstream URLs containing the token. Drop the cursor from process memory after use/expiry. A browser reload loses it and requires a new search.
- Change dashboard/profile totals that currently sum `SearchHistory.result_count` to count the owned Place-ID rows instead; do not copy a Google result count into persistent history.
- Replace process-local result cache with shared Neon metadata and Place-ID rows. Do not introduce a shared cache of Places content. Expiration cleanup deletes app metadata and Place IDs only after the configured retention period; Place ID retention is allowed indefinitely, but short retention is preferred for product minimization.
- A failed request after a network timeout is ambiguous: Google may have billed it even if the app did not receive a response. Do not retry beyond the configured bound; surface a safe retryable failure and retain/reconcile the idempotency state without claiming the vendor did not bill.
- If Google returns success but the following Neon commit fails, leave the reservation in a recoverable/unknown state instead of freeing quota automatically; otherwise a client could repeatedly trigger paid API requests during a DB outage without consuming quota. Provide an explicit expiry/reconciliation policy and tests for this state.

### My Leads, pagination, exports, and attribution

- Remove all new persistence and server reads of Google-sourced name/address/phone/website/rating/review-count/map-URL/type values. My Leads stores/returns Place IDs plus app-owned search metadata only. Do not reuse client-supplied result data as authoritative export data.
- CSV/Excel endpoints query the authenticated user's owned search/Place-ID rows; output Place IDs and user-entered query metadata only. Preserve authorization and download formats where possible. Remove or neutralize formula-leading values in exported user metadata.
- Keep Places fields in the immediate search response only for display, with explicit Google Maps logo attribution inside the results container, proper visual separation, and an accessible label. Display Google's documented ranking factors disclosure with a link. Use the official attribution asset/style; do not approximate or alter the logo.
- Remove or hide legacy Places fields from new app presentation. Add an optional manual SQL cleanup script for historical `exported_leads` Google columns only if a backup/review is completed; never run it from app startup or deployment. Until historical values are purged, production policy compliance remains unverified.
- Add tests proving no Google Places field is written to DB, returned from My Leads, or included in CSV/XLSX, and that another user's search ID cannot be paginated/exported.

### Website scraping and background jobs

- On 2026-11-02, the owner confirmed that use of Google Places website URLs to extract publicly linked business contact and social-profile information has been reviewed and approved under the applicable Google Maps Platform terms.
- Website enrichment runs synchronously for returned results and is best-effort. The immediate search response may include email/social links found in the linked public website; scraping failures leave those fields empty and are logged without failing the Places search.
- The scraper allows only HTTP/HTTPS on standard ports, rejects non-public DNS/IP results, pins the connection to the validated IP while preserving the original Host/TLS hostname, revalidates each redirect, disables environment proxies and automatic redirects, and caps redirects, response bytes, and elapsed request time.
- Website-derived fields are returned only in the immediate search response. Search history continues to persist Place IDs and application-owned query metadata only. No durable scraping job or worker is added.

### Web security and production safety

- Add CSRF protection to cookie-authenticated state-changing routes, including search/export/payment mutations, preserving OAuth's existing state validation. Change logout to POST and update its UI.
- Validate Google OAuth `email_verified` before account creation/session establishment. Keep session clearing/rotation behavior and enforce secure production cookie flags.
- Apply per-user abuse limits to search submission and export/download paths using shared Neon counters (no unconfigured in-memory global limit). Also rate-limit the OAuth login-start endpoint by a short-window hash of client IP; do not retain raw IPs for this limiter. Keep the Places QPM limiter as the separate project-wide vendor limit.
- Review SQLAlchemy pool settings against Vercel function concurrency and Neon pooled-connection guidance; do not advertise a capacity number without load testing. Batch export queries rather than issuing one lookup per lead.
- Add response security headers that are compatible with the current inline-script/style templates; use a staged CSP compatible with existing UI rather than breaking it.
- Preserve Freemius checkout/webhooks and current payment code; run the existing payment safety tests throughout.
- Use safe error responses; no secrets, authorization headers, full provider bodies, or raw website content in logs.

### Database and migrations

- Add a new manual PostgreSQL migration for the global QPM counter, quota reservations, per-operation idempotency ledger, and Place-ID-only search results, with owner/expiry indexes and constraints. Preserve all existing migration files and records.
- Do not run `db.create_all()` in production or auto-apply migrations. Keep startup schema validation and update it to require the new tables/columns.
- Do not drop existing `exported_leads` columns in the application migration. Stop using them in application code. If historical cleanup is later desired, provide it as a separate optional SQL file, never referenced by startup or deployment; require a verified backup and the user's manual review/application. Do not execute it as part of this work.
- Verify SQL against PostgreSQL in tests or a disposable local test database only; actual production migration history/schema remains NOT VERIFIED until manually compared.

## Exact initial files expected to change

- `services/google_places.py` — request, field mask, pagination, parsing, retry/status behavior.
- New `services/google_places_rate_limiter.py` — Neon-backed global QPM reservation.
- `config.py` — QPM configuration and production validation.
- `routes/search.py`, `routes/search_cache.py`, `routes/pagination.py`, `routes/usage.py` — quota reservation, durable ID-only search state, ownership, and removal of scraping/cache behavior.
- `models/search_history.py`, `models/exported_lead.py`, and new quota reservation/search-result model modules — durable metadata and Place IDs only.
- `routes/export.py`, `routes/profile.py` — owned Place-ID-only exports and My Leads; stop exposing legacy Places values.
- `services/website_scraper.py` — SSRF and bounded-fetch hardening for approved, request-scoped enrichment.
- `templates/index.html`, `templates/profile.html`, `templates/account.html`, `templates/home.html`, `static/app.js`, `static/pagination.js`, `static/profile.js`, `static/profile.css`, and possibly `app.py` — attribution, status, removal of enrichment display, CSRF, and logout UI.
- `routes/auth.py`, `routes/payment.py`, `app.py` — verified OAuth email, CSRF/security headers and session-safe routes; Freemius webhooks remain CSRF-exempt only because provider signature validation is their authentication.
- `migrations/20261031_google_backend_compliance.sql` — manual schema additions only. Any historical-data cleanup must be a separate optional SQL file with explicit backup/review instructions, never part of deployment/startup.
- `tests/test_google_places.py`, `tests/test_google_places_rate_limiter.py`, `tests/test_search_quota_reservation.py`, `tests/test_search_ownership.py`, `tests/test_export_policy.py`, `tests/test_website_scraper_security.py`, `tests/test_auth_security.py` — mocked/offline regression coverage.
- `README.md` (new) and `.env.example` (new, no secrets) — local setup, manual migration, QPM source, worker deferral, privacy/terms/attribution and release checklist. No production values.

Files already changed by the user, including `app.py`, `config.py`, Freemius routes, tests, docs, and the deletion of `migrations/20261030_subscription_quota.sql`, will be preserved and merged carefully. No `.env` file is to be read or written.

## Risks and compatibility

- My Leads and CSV/XLSX will no longer contain contact details or other Places fields; they will contain Place IDs and user-entered query metadata. Website email/social enrichment stops. This is the deliberate cost of the selected policy-first approach pending Google confirmation.
- Additional on-demand page calls can increase billing; actual quota and regional SKU cost must be manually checked. The design does not silently fetch Place Details for every ID.
- A global PostgreSQL limiter adds a DB operation per upstream call and depends on Neon availability/latency. On DB failure, Google requests fail closed.
- Database reservation and rate-limiter migrations must be applied manually before enabling the new code. Startup validation will fail clearly if they are absent.
- Historical `exported_leads` rows may contain restricted values until separately cleaned; not production-ready for compliance until that is resolved.
- Idempotent retries intentionally do not replay Places response bodies. If the original HTTP response is lost, the client may need a new logical attempt and a new API call; the old key still prevents an automatic duplicate call.
- A separate worker host is deferred; email/social extraction remains unavailable until policy review and worker hosting are approved.
- Legal Terms/Privacy policy text and Google's applicable EEA/non-EEA service terms require owner review. No legal text is invented in this change.

## Verification and release gates

- Run new mocked tests and the full existing test suite; no paid Google or Freemius calls.
- Run Python compile/import checks and inspect the final diff for accidental secrets, migration conflicts, or changes to the user's prior work.
- Manually compare field mask, QPM, billing region/SKUs, Google Cloud quotas, attribution asset, published Terms/Privacy, actual database schema/migration history, and Vercel runtime settings before production deployment.
- Do not claim full Google policy compliance, actual production readiness, or load capacity until those manual/external checks and the historical-data cleanup are complete.
