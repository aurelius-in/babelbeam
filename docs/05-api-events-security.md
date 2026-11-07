# 05 - API contracts, authentication, security, and privacy

## 1. Authentication
Use Supabase Auth email OTP as the default managed identity provider [S18]. The backend requests/verifies codes through a vetted SDK or documented API. Configure short expiry, attempt limits, throttling, and a verified production sender. Prefer entered codes over magic links alone because installed apps and the system browser may have separate storage contexts.

After successful provider verification, the backend maps the verified subject to a local user and issues its own cryptographically random opaque session cookie. Store only a hash of that app-session token. Do not accept a client-supplied email/subject as proof of verification. Avoid a global mutable Supabase client whose authenticated session could leak between concurrent users; use request-scoped auth clients or explicit stateless HTTP calls. Do not persist provider refresh tokens unnecessarily when the application uses its own server session.

Cookie: `__Host-babelbeam_session`, Secure, HttpOnly, SameSite=Lax, Path=/, no Domain attribute. Use a distinct, explicitly insecure localhost development cookie only in development. Default idle expiry 12 hours, absolute expiry 30 days, rotation on authentication/privilege changes, and user-visible logout/revoke sessions. Privileged billing/admin changes require recent verification (for example 15 minutes). Verify local account status and organization membership on every request. Follow session security guidance [S19].

SameSite is defense in depth, not complete CSRF protection. Use a session-bound CSRF token plus Origin checks for state-changing cookie-authenticated requests. Rate-limit OTP sends/verification per challenge/account/IP without letting one hostile IP globally lock out a parish. Return neutral responses to avoid email enumeration. Never log OTPs, auth tokens, or full email bodies. Use Mailpit or test-only adapters for development, not a public bypass login route.

Guests get a separate opaque session cookie bound to one admitted classroom, plus short-lived room tokens. Guests have no memberships, billing access, teacher role, or durable profile. Guest sessions expire after class end plus a brief cleanup period. A random neutral alias is sufficient. Teacher accounts can join a class as guests without converting the guest role into teacher privileges.

## 2. HTTP API
Prefix business endpoints `/api/v1`. Generate OpenAPI/Pydantic contracts and TypeScript client types. Authenticate every endpoint except truly public configuration/help and a rate-limited join/OTP entry point. Return stable machine-readable error codes and request IDs, with no secret/internal stack details.

| Method/path | Authorization and effect |
| --- | --- |
| `GET /public/config` | Price, trial days, approved public limits, languages, status; no secrets or tenant data. |
| `POST /auth/request-code` | Rate-limited; sends verification code, creates challenge. |
| `POST /auth/verify-code` | Challenge-bound provider verification; rotates app session. |
| `GET /auth/me` | Safe user/membership summary and CSRF bootstrap. |
| `POST /auth/logout` | Revoke session; clear cookies. |
| `POST /organizations` | Verified adult; ownership and trial eligibility remain server controlled. |
| `GET /organizations/:orgId` | Member only, scoped response. |
| `PATCH /organizations/:orgId` | Owner; permitted settings only, never billing privileges through generic patch. |
| `GET /entitlements?organization_id=...` | Authorized member; exact access state, dates, limits, usage, reasons. |
| `POST /billing/checkout` | Owner + recent auth + consent + CSRF; server product/customer. |
| `GET /billing/checkout-status/:attemptId` | Owner of that attempt only; canonical reconciliation. |
| `POST /billing/portal` | Owner; generates short-lived portal URL from server customer mapping. |
| `POST /billing/cancel` | Owner + recent auth; one confirmation, audited and idempotent. |
| `POST /webhooks/stripe` | Raw-body signature verified, environment matched; no browser trust. |
| `POST /classes` | Teacher membership; create draft under its org. |
| `POST /classes/:id/start` | Teacher, entitlement/capacity/limit checks; idempotency key. |
| `POST /classes/:id/pause` | Authorized teacher; expected epoch; stops processing/meter. |
| `POST /classes/:id/resume` | Revalidate access/capacity; increment epoch appropriately. |
| `POST /classes/:id/end` | Teacher; idempotent; invalidate room/worker access. |
| `POST /classes/:id/lock` | Teacher; lock new joins without ejecting current attendees. |
| `POST /classes/:id/rotate-invite` | Teacher; invalidates old join credentials. |
| `POST /join/resolve` | Rate-limited, opaque invite/code; minimal metadata only. |
| `POST /join/admit` | Admission/notice/consent checks; guest cookie issued before media access. |
| `GET /classes/:id/snapshot` | Bound participant/teacher; role-filtered bounded recent state. |
| `POST /classes/:id/media-token` | Bound role, active access/session/epoch, server-resolved room only. |
| `POST /classes/:id/hands` | Admitted student, one request at a time. |
| `DELETE /classes/:id/hands/:requestId` | Request owner or teacher; cannot manipulate others. |
| `POST /classes/:id/floor/grant` | Teacher, revision check and transaction; exactly one student. |
| `POST /classes/:id/floor/revoke` | Teacher; hard cancel. |
| `POST /classes/:id/floor/start` | Current selected student; explicit speaking action. |
| `POST /classes/:id/floor/finish` | Selected student/teacher; normal drain then revoke. |
| `POST /classes/:id/questions/text` | Current approved turn; bounded text; ephemeral only. |
| `POST /classes/:id/participants/:pid/remove` | Teacher; revoke guest/media access and floor if needed. |
| `GET/POST /glossaries` | Tenant member/teacher; never global data by default. |
| `POST /glossaries/:id/versions` | Create draft, validate import and size. |
| `POST /glossaries/:id/versions/:v/approve` | Authorized teacher; immutable approval snapshot. |
| `POST /glossaries/:id/preview` | Teacher, quota-limited pronunciation test; explicit synthetic sample. |
| `POST /account/delete-request` | Recent auth; separate billing cancellation and reviewed retention flow. |
| `GET /health/live` | Minimal liveness only. |
| `GET /health/ready` | Internal/restricted readiness, dependencies and migrations. |

Backend derives actor/role and checks tenant membership even when the URL has an org/session ID. Query filters and foreign keys must agree with tenant scope. An unauthenticated UUID is not an authorization mechanism.

No generic endpoint that accepts arbitrary LiveKit room names, Stripe customer IDs, role strings, SQL patches, or model IDs from the browser. Critical configuration and complementary grants use protected explicit actions or an operator CLI.

Error envelope example:
```json
{
  "error": {
    "code": "TRIAL_EXPIRED",
    "message_key": "billing.trialExpired",
    "retryable": false,
    "request_id": "req_opaque"
  }
}
```
Other codes: `PAYMENT_REQUIRED`, `CLASS_LIMIT_REACHED`, `USAGE_LIMIT_REACHED`, `ROOM_FULL`, `JOIN_INVALID`, `SESSION_ENDED`, `FLOOR_BUSY`, `FLOOR_REVOKED`, `MEDIA_UNAVAILABLE`, `TRANSLATION_UNAVAILABLE`, `SAFEGUARDING_REQUIRED`. Do not reveal an organizer's billing details in guest errors.

## 3. App WebSocket contract
Use `/ws/v1/classes/:id` on the same origin. Authenticate with the bound cookie, validate Origin, require a short-lived single-use connection ticket sent in the first frame, and timeout unauthenticated sockets. Do not put a long-lived token or join credential in a logged query string. Guest tickets are bound to class, role and expiry.

The app WebSocket carries state/captions, not raw audio. Commands can use authenticated HTTP for simpler idempotency and auditing. The worker's internal endpoint uses a separate service identity and session/lease authorization, not a public browser token.

Every event envelope:
```json
{
  "schema_version": 1,
  "event_id": "opaque-uuid",
  "session_id": "opaque-uuid",
  "epoch": 3,
  "sequence": 42,
  "emitted_at": "2026-10-15T12:00:00Z",
  "type": "caption.final",
  "payload": {
    "segment_id": "opaque-uuid",
    "language": "es",
    "text": "Texto de ejemplo.",
    "glossary_version": 2
  }
}
```
Define typed schemas for `session.ready`, `session.state`, `caption.draft`, `caption.final`, `caption.correction`, `audio.status`, `hand.queued`, `floor.granted`, `floor.speaking`, `floor.revoked`, `usage.warning`, `participant.count`, `service.degraded`, and `session.ended`.

Role-filter events on the server: English source/draft captions, student aliases, complete hand queue, and English question interpretation go only to the teacher. Spanish class captions reach admitted listeners. The selected student sees their own turn status; no student receives another student's private control/token. Do not broadcast everything and hide fields in CSS.

Clients deduplicate event IDs, enforce monotonically valid epochs, and request a snapshot after gaps. Snapshot contains current state and bounded recent finalized captions only. On end, clear visible transient state after a helpful end message; no replay of old media. All consumers validate schema versions and handle unknown event types safely.

## 4. Threat model and controls
Required abuse tests include cross-tenant ID guessing, invite-code brute force, reuse of expired room credentials, student role escalation, private-track subscription attempts, fake Stripe webhooks, duplicate Checkout creation, trial resets, prompt injection in speech, XSS in captions/aliases, malicious glossary CSV, concurrent floor approvals, and runaway worker billing.

Enforce:
- TLS, secure cookies, explicit CORS/Origin allowlists, CSRF, a restrictive tested CSP, secure headers, least-privilege DB/service credentials.
- Render all text as text, not `dangerouslySetInnerHTML`. Glossary import accepts bounded CSV/JSON, not macros or arbitrary URLs. Validate encoding, length, duplicates, formula-like content, and schema. No fetching arbitrary lesson URLs in v1.
- Rate limits on auth, joins, hand raises, media-token minting, glossary previews, billing attempts, and backend message sizes.
- Random high-entropy QR invites, limited-lifetime numeric entry codes with strong rate limiting, optional teacher approval/room lock, revoke/rotate controls. Never rely only on a six-digit code without abuse controls.
- No PII in provider identities/room names. Logging filters are tested, not merely configured optimistically.
- Worker network timeouts, finite retry budgets, bounded queues, fencing tokens, capacity admission, maximum session length, orphan-room cleanup, and spending alarms.
- No blanket remote-unmute setting. Student permission and local recording activation remain distinct.
- Admin is deny-by-default and never bootstrapped to the first public signup. Owner provisioning is explicit and audited; MFA/reauthentication is required for high-impact administration.

## 5. Privacy and safeguarding
By default the application does not persist raw classroom audio, classroom transcripts, or question text. It keeps minimal account/billing records, glossary content, session times/counts, and non-content quality/usage metrics. This is not a blanket claim of provider zero retention: verify provider data controls, regions, logging, and optional observability/recording settings. Use `store: false` where supported, and disable audio/transcript recording in media/agent tools. [S8]

Classroom snapshots live in explicitly ephemeral storage. No service worker cache, session replay SDK, analytics payload, exception message, or debug audio should secretly become a transcript archive. Diagnostic content capture, if ever added, must be a separate opt-in reviewed feature with retention and access controls, not a developer toggle in production.

Children's privacy: do not collect birthdays simply to avoid making a policy decision. Do not assume a free account, no email field, teacher checkbox, or captions-only mode removes obligations. Voice and persistent identifiers can be covered children's personal information; the relevant FTC guidance requires an applicability/consent review. [S20]

Default rollout is adult participants only. `MINORS_ENABLED=false` blocks minor-class admission and disables associated media/guest processing. When the owner enables a reviewed minor workflow, require verified parish authorization and the approved parental/guardian consent/admission mechanism before third-party media connections. Do not invent a token field and call it legally sufficient consent. Revocation removes admission and deletes eligible data. Testing for known child sessions must fail closed.

Explicitly prohibit use for confession, private pastoral counseling, or other highly sensitive interpretation until a separate product/privacy/security review. Do not market as a certified interpreter or a source of authoritative doctrine.

## 6. PWA storage and update behavior
Service worker precaches only static shell/assets and a safe offline help screen. Network-only/no-store for auth, billing, class state, guest admission, captions, API/WebSocket traffic, and signed media credentials. No audio or classroom text in IndexedDB/localStorage by default. Static demo content is separately labeled and nonpersonal.

Update assets predictably and notify the user when an update is ready. Defer activation/reload until a class ends or the user explicitly chooses a safe time. Preserve role/route context after installation but never persist an entitlement grant in the manifest/cache.

Offline message: "Internet is required for live translation. Reconnect to rejoin the class." Do not show a cached LIVE badge or pretend offline translation is working.

---
