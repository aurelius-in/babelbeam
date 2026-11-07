# 06 - Cursor implementation sequence

## Working agreement
Implement a tested vertical slice in each phase. Do not spend the first several phases only on marketing pages. Do not report a phase passed because a mock implementation returns canned text. Separate unit, contract, live-provider, and real-device evidence.

Before each phase read its relevant spec and current `docs/BUILD_STATUS.md`. After each phase record changed files, commands actually run, test results, screenshots where appropriate, known limitations, missing operator prerequisites, and the next step. Preserve uncommitted owner work. Never run destructive resets to simplify the task.

## Phase 0 - Repository and runnable foundation
Inspect repo; create an architecture summary and task checklist. Resolve supported versions; create frontend/backend/worker structure, strict types, linting, lockfiles, `.gitignore`, example config, and health endpoints. Establish one-origin dev proxy and local services (PostgreSQL, ephemeral Redis, email test inbox). Add explicit test provider interfaces and an unmissable simulated-mode banner.

Create root commands, implemented and tested rather than merely documented:
```text
make setup              install pinned dependencies and verify tooling
make dev                start local services and apps in explicit development mode
make migrate            apply application schema migrations
make seed               add synthetic fixtures, not production users or grants
make lint               frontend and Python checks
make typecheck          both language type checks
make test               offline deterministic unit/integration suite
make test-e2e           browser workflow tests against local stack
make provider-check     verify configuration/model/API capabilities, with opt-in cost notice
make billing-test       run documented Stripe sandbox simulations
make build              build deployable artifacts
```
Supply PowerShell/Windows or WSL instructions in README; do not assume every user has GNU make installed. Missing dependencies must produce specific instructions. Production startup refuses fake providers and missing secrets. Local fake mode must not contact external billing services.

Deliverable: a new developer can open the repo, configure the example environment, start it, and understand which parts are simulated. A clean CI runner can execute its deterministic tests.

## Phase 1 - Verified auth, tenants, and access skeleton
Implement provider-backed email OTP, secure app sessions, tenant creation/membership, basic role-aware dashboard, guest admission foundation, and schema migrations. Build EntitlementService with test fixtures for trial, paid, expired, and complimentary states, but no production bypass endpoints. Add protected operator CLI to grant complimentary access to a specified organization ID.

Pass: cross-tenant tests, OTP throttling, logout/session revocation, forged identity rejection, CSRF, no student billing access, and production fake-mode refusal. Establish Tom's production grant only after Oliver identifies the correct account and approves the write.

## Phase 2 - Real one-way streaming vertical slice
Implement private teacher and public broadcast rooms, worker assignment/lease, real microphone capture, live STT, text translation, streaming TTS, and Spanish caption events. Start/pause/end controls must affect the actual worker/media. Show real readiness and error states.

Prove on two phones: English microphone -> readable Spanish -> audible Spanish, plus clean stop. Then repeat with two student devices to verify one shared TTS output rather than one request per listener. Implement no content logging now, not as a cleanup task later.

Pass: real provider smoke test, synthetic deterministic audio contract tests, source filtering, no worker feedback loop, pause/end cleanup, and measured latency logs without utterance text. Missing real credentials block only the live-provider evidence, not the adapter implementation or other tests.

## Phase 3 - Glossary and quality
Implement glossary editor/import/approval/versioning, term matching/placeholders/validation, bounded retries, selected voice preview, corrections, and the supplied terminology fixtures. No unapproved glossary edits in live segments. Add source/translation mismatch handling and captions-only degradation.

Pass: protected-token multiset tests, unknown term behavior, injection tests, long speech/backlog bounds, and the original three-term example through real audio. Bilingual/teacher pronunciation review remains a human release gate and must be recorded honestly.

## Phase 4 - Moderated two-way questions
Implement guest hand queue, single floor transaction, temporary private question room, explicit Tap to Speak, Spanish -> English private teacher output, typed fallback, drain-versus-hard-cancel semantics, timeouts, teacher response routing, and reconnect revocation.

Pass: two simultaneous approval attempts yield one floor; unapproved student cannot publish; ordinary listener cannot subscribe to private media; the final question sentence is not lost; stale tokens/late output cannot reclaim a turn. Demonstrate on teacher + two student devices.

## Phase 5 - Stripe trial, billing, and metering
Create the one 1499-cent monthly Price and hosted Checkout in sandbox. Implement consent, trial eligibility, server-verified activation, raw-body webhooks, reconciliation, access states, portal/cancellation, reminder jobs, live usage ledger, allowance warnings, and no-card complimentary flow. Use the approved plan config everywhere.

Pass the billing scenario matrix with real Stripe sandbox/test-clock evidence where supported. Document sandbox email limitations and test app-owned reminders separately. Do not wait 30 actual days to test conversion. No test ever charges a real card. Show day-14 expiry, first 1499-cent invoice, renewal, cancellation, failed initial payment, out-of-order webhook recovery, and no second trial on reinstall.

## Phase 6 - Premium UI, help, and installation
Finish the approved visual system, genuine transparent logo variants, responsive teacher/student screens, pricing/onboarding/billing states, English/Spanish locale files, accessible controls, manifest/icons, install help, service worker, safe offline page, and update deferral. Marketing should reflect only implemented/verified capabilities.

Pass: no logo background boxes, legible header on dark/light, no white-on-white phone panels, no clipped footers, keyboard/focus/contrast checks, 200% text zoom, 360px-wide phone layouts, and actual installation/opening on target iPhone/Android devices. Generated icons must remain recognizable at small sizes.

## Phase 7 - Production operations and rehearsals
Write container/proxy deployment, environment separation, HTTPS/DNS steps, migrations/backups/restore, workers/capacity, alerting, provider quotas, secrets rotation, cleanup, privacy retention and billing runbooks. Add continuous test/lint/build checks; scans must not upload classroom data.

Run a representative 60-90 minute adult lesson and a full proposed-listener-count test, including questions and a network interruption. Confirm no increasing audio backlog and no accumulating orphan rooms/workers. Produce a cost report from actual provider/worker measurements.

Pass: restore test, webhook retry/reconciliation drill, worker-crash fencing test, usage boundary test, budget alarm test, and a completed operator checklist. This is the first point at which Oliver can separately authorize deployment and live billing.

## Phase 8 - Supervised parish pilot and commercial launch
Obtain parish approval and any necessary safeguarding/legal reviews. Confirm supported devices, actual Wi-Fi/headsets, terminology/voice review, customer support contact, public policy wording, and final plan allowances. Keep Tom complimentary.

Run the classroom rehearsal with human bilingual review. Record issues without storing unapproved recordings. Fix critical meaning inversions/term errors or label unsupported scenarios before admitting paying customers. Do not start real trials before the product can provide the promised service. Enable live billing only after explicit owner approval and sandbox acceptance evidence.

## Resume prompt
```text
Read AGENTS.md and docs/BUILD_STATUS.md. Inspect the current implementation and
rerun the last phase's checks. Continue the first incomplete phase from
06-implementation-plan.md. Do not rewrite working modules or repeat a plan
instead of implementing. Keep simulations clearly marked, list any missing real
credentials, and provide test evidence and an updated build status.
```

## Final implementation handoff required from Agent
A usable application repo, actual startup/test commands, migrations and seeds, `.env.example`, generated contracts, clean brand assets, screen/install screenshots, test reports, provider version/cost record, Stripe sandbox results, deployment/rollback/support guides, and a list of genuine remaining real-world approvals. Never fabricate a public deployment URL, customer testimonial, test result, or completed purchase.

---
