# 07 - Acceptance tests, operations, and launch checklist

## 1. Definition of acceptance
Automated tests prove local invariants. Contract tests verify provider API shapes. Real-device tests verify microphones, audio output, permissions, installation, and network recovery. A bilingual reviewer evaluates meaning/pronunciation. None is a substitute for the others.

Performance goals are initial engineering targets, not customer guarantees: median final-caption delay <=3 seconds and median translated-audio onset <=5 seconds after a phrase ends; investigate p95 above 8 seconds. Also report phrase-start -> output latency so long segmentation is not hidden. Record queued audio growth during a full lesson, not just a 10-second demo. Accuracy reports distinguish typed-text preservation from actual spoken recognition.

## 2. Automated acceptance matrix
| ID | Scenario | Required assertion |
| --- | --- | --- |
| A01 | Wrong tenant org/session ID | No access to data, media, billing, glossary, or events. |
| A02 | Guest modifies role/localStorage | Teacher/billing actions remain denied. |
| A03 | Fake login claim / stale OTP | Rejected; no app session or role created. |
| A04 | Logout/session revoke | HTTP and WebSocket authorization expire; no token refresh. |
| A05 | Cross-origin state-changing request | CSRF/Origin checks reject it. |
| R01 | Teacher speaks; 1, 2, then 10 listeners | Same Spanish stream, one translation/TTS per source segment. |
| R02 | Ordinary student publishes in broadcast room | Server rejects publication. |
| R03 | Ordinary student requests private teacher room | No token/no private audio or English-question events. |
| R04 | Worker TTS loops into input | Source identity filtering prevents retranslation. |
| R05 | Start retry / double click | One class, one worker, correct reservation. |
| R06 | Pause/end | No new STT/TTS work or stale audio beyond defined drain/cancel. |
| R07 | Out-of-order translation completions | Public delivery remains ordered; duplicates not spoken. |
| R08 | Worker restart and lost lease | Old worker fenced off, old room output stopped, new epoch only. |
| R09 | Audio backlog / TTS timeout | Visible degradation, bounded memory/cost, captions continue if valid. |
| R10 | No listeners / teacher disconnect | Defined idle cleanup, no indefinitely billed session. |
| G01 | Tom's three-term example | Canonical spellings/counts survive validated text. |
| G02 | Token missing/duplicated/forged | Bounded retry then unavailable; no unsafe TTS. |
| G03 | Prompt-injection utterance | Translated as content; not executed or answered. |
| G04 | Negation, dates, numbers, named terms | No critical meaning inversion in reviewed test set. |
| G05 | Unknown term / overlapping glossary matches | Conservative, deterministic behavior; no fabricated certainty. |
| G06 | Unapproved edit mid-class | Cannot alter pinned glossary without approved version boundary. |
| Q01 | Two teachers/tabs approve simultaneously | Exactly one selected floor holder. |
| Q02 | Teacher grants a turn | Student mic stays off until student's explicit tap. |
| Q03 | Selected student ends normally | Final utterance drains, then permissions/room revoked. |
| Q04 | Teacher revokes / student disconnects | Hard cancel; stale grants and late English audio rejected. |
| Q05 | Typed question | Same floor/validation/ephemeral policy, no unrestricted chat. |
| Q06 | Student asks; teacher answers | Teacher privately hears English; class hears Spanish answer. |
| B01 | New eligible trial activation | 14 days from Stripe trial start, no charge today, one subscription. |
| B02 | First renewal | Base amount 1499 USD cents, correct calendar-month recurring price. |
| B03 | Cancel before trial end | Access until trial expiry; no first paid invoice/charge. |
| B04 | Trial expires / no payment / authentication needed | No permanent free hosting; recovery UI works. |
| B05 | Reinstall, new browser, same buyer/new org | No renewed trial eligibility. |
| B06 | Duplicate/concurrent checkout | One legitimate active subscription; safe reconciliation. |
| B07 | Forged redirect / session from another buyer | No access activation. |
| B08 | Fake/duplicate/out-of-order webhook | Rejected or idempotently reconciled. |
| B09 | Zero-dollar trial invoice | Does not extend a paid entitlement incorrectly. |
| B10 | Cancel paid subscription | Current paid access retained; no next renewal. |
| B11 | Tom complimentary | No Stripe checkout, card, charge, or countdown; budget controls intact. |
| B12 | Allowance/period boundary | Meter idempotent, correct period, no unconsented overage. |
| B13 | Access expires during live class | One persisted wind-down; rejoin cannot reset it. |
| B14 | Payment recovers | Canonical status/period restore correct access without second trial. |
| P01 | Install on actual supported devices | Recognizable icon, standalone opening, correct role/login behavior. |
| P02 | Offline / stale service worker | No cached LIVE state, credentials, captions, or paid access. |
| P03 | Update available mid-class | No forced reload or microphone interruption. |
| P04 | Text zoom and screen reader | Controls usable, no clipping or incessant announcements. |
| S01 | Known minor session without approved consent path | No admission or third-party media connection. |
| S02 | Inspect logs/storage after synthetic lesson | No raw audio, text, names, codes, tokens, or private billing data leaked. |

Use fixtures in this kit as test seeds. Do not weaken assertions simply to mark a phase complete. Do not equate exact Spanish wording to semantic correctness; a valid translation may differ from the fixture's reference.

## 3. Physical-device rehearsal
Minimum matrix: an iPhone using Safari/browser and installed PWA; Android Chrome/browser and installed PWA; desktop Chromium as instructor fallback; Bluetooth and wired headsets. Record OS/browser/headset versions and dates. A Playwright WebKit run is not an iPhone microphone test.

Scenarios: join by camera QR; enter code manually; start playback after gesture; microphone permission denied then granted; output route changes; headset disconnect; incoming call; lock/unlock; rotate screen; large text; leave/rejoin; teacher Wi-Fi loss; student cellular switch; multiple raised hands; a 60-90 minute lecture with natural pauses and questions.

The baseline customer instruction is to keep the session screen open and unlocked. Record actual background/lock behavior before advertising more. Do not issue a blanket guarantee across untested devices.

## 4. Stripe sandbox test procedure
Use a dedicated development sandbox with sandbox price/customer/webhook secrets and no live cards. Configure fixed 1499-cent monthly price and a 14-day trial. Use Stripe's documented testing/test-clock workflow [S17]; confirm current restrictions for Checkout and test-clock customer creation. If a Checkout-specific clock scenario is unsupported, test real Checkout separately and use equivalent sandbox subscription objects for accelerated lifecycle verification. Document that distinction.

Advance a simulation through trial activation, pre-end reminders, trial end, first invoice/payment, next monthly invoice, cancellation, declined initial payment, and authentication-required recovery. Wait for asynchronous event processing to finish before assertions. Verify backend entitlement state, not only the Stripe dashboard badge.

Test webhook signatures with raw bytes. Replay duplicates/out-of-order events and temporarily fail the handler to prove retry/outbox recovery. Simulate database commit failure around checkout/event processing. Test reminders in the app's email harness; Stripe's sandbox does not send its trial reminder emails. Never change live subscriptions to speed up testing.

## 5. Deployable topology
Use one HTTPS origin for static PWA + API/WebSocket reverse proxy. Run API and translation worker as long-running containers; PostgreSQL and Redis are private. LiveKit Cloud handles public media networking. Serve static assets with correct cache headers; API/auth/content endpoints are no-store. Use a process host that permits persistent connections, idle worker leases, and graceful shutdown.

Create separate development/staging/production databases, auth projects, media rooms/projects as appropriate, Stripe environments, API keys and domain configuration. Secrets from a local `.env` are never baked into frontend bundles or container layers. Define health/readiness endpoints and explicit CPU/memory/concurrency ceilings.

Start with a small maximum active-class capacity and admission queue/message; do not start more workers than quotas allow. Prefer external worker hosting with LiveKit RTC rather than automatically turning on a hosted conversational-agent stack with recording. Account for the chosen hosting/billing arrangement explicitly.

Do not autosuspend the live worker in the middle of a lesson. Deployment drains new admissions, lets existing sessions finish within a bounded window, and rolls old/new API contracts compatibly. A forced maintenance end is announced, not silently disconnected.

## 6. Migrations, reliability, and cleanup
- Version all schema changes; run preflight migrations on staging; use non-destructive expand/contract changes when possible.
- Back up durable metadata with encryption and a tested restore procedure. No classroom content should enter backups because it should not be durable.
- Reconcile Stripe state after webhook outage and after restores before enabling hosting. Restore must not recreate consumed trial eligibility as new.
- Sweep expired guests, unused question rooms, abandoned classrooms, stale worker leases, and overdue reminder jobs.
- Use worker fence + epoch on every pipeline result. On takeover, disconnect the old worker identity/rooms before exposing new output; do not let both publish indefinitely.
- Failed dependency checks fail closed for new sessions. Active sessions get a defined degraded/wind-down state, not an infinite unauthorized loop.
- Global circuit breaker/budget cap blocks new paid processing admissions under an operator incident policy and produces a clear service notice. Do not silently charge beyond disclosed price or hide degraded service from new trial users.

## 7. Observability without classroom surveillance
Metrics: active rooms/participants, worker count, phase latencies, queued audio, dropped/invalid segments (counts only), protected-token validation failures, reconnections, provider errors/rate limits, usage ledger drift, trial conversions, failed renewals, webhook lag, and estimated cost per classroom hour/listener-hour.

No session replay, microphone recordings, caption payloads, real-name room labels, full HTTP bodies, or payment tokens in monitoring. Provider SDK debug logging and automatic agent recording must be reviewed and disabled in production. If an exception embeds text, sanitize before reporting. Use synthetic fixtures for development screenshots and error reports.

Alert on stale LIVE state without output, growing audio backlog, duplicate workers, orphan media rooms, Stripe webhook failures, entitlement reconciliation drift, and spending thresholds. Email/notification tools require configured verified recipients; do not invent a support address or send to Tom without approval.

## 8. Operator setup checklist
- [ ] Domain ownership/DNS/TLS configured by authorized operator; no domain purchase needed.
- [ ] Tested versions and models recorded; selected TTS lifecycle/Spanish voice confirmed.
- [ ] LiveKit Cloud project, grants, limits and worker hosting chosen; recording disabled.
- [ ] Auth sender configured, OTP delivery and per-user isolation tested.
- [ ] Database/Redis credentials private; auth/app schema access verified.
- [ ] Stripe product price verified at 1499 USD cents/month; trial is 14 days.
- [ ] Terms, consent, cancellation, tax settings and reminder messaging reviewed.
- [ ] Price/usage/listener policy approved and identical in app, Checkout and help.
- [ ] Tom's actual organization confirmed; complimentary grant applied only with approval.
- [ ] Safeguarding/privacy review and participant-age scope approved.
- [ ] No live customer trials before operational readiness.
- [ ] Real-device, bilingual, load, billing and restore tests recorded.
- [ ] Provider/cost budget and external-service incident process set.
- [ ] Support/cancellation/deletion contacts actually exist and are monitored.
- [ ] Production rollback and subscription reconciliation rehearsed.
- [ ] Owner explicitly approves production deployment and live billing.

## 9. Launch configuration checks
`ENVIRONMENT=production` must reject mock auth/AI/media/billing adapters, insecure cookies, default/example secrets, wildcard credentialed CORS, public Redis, and missing required config. `PRODUCTION_BILLING_ENABLED` remains false until the launch checklist passes. `PLAN_LIMITS_APPROVED` and `MINORS_ENABLED` are independent: approving sales limits does not approve child-data collection.

Provider contract and price checks do not authorize paid traffic. The owner must configure real secrets and approve external actions; Agent must report missing prerequisites truthfully rather than claim it deployed a working app.

---
