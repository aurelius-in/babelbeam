# BabelBeam - Complete Cursor Implementation Instructions

14-day free trial | $14.99 USD/month | Free students | Complimentary Tom pilot

This is the human-readable master specification. The ZIP additionally supplies individual Cursor rules, configuration, test fixtures and approved brand art. It is not an implemented app.


---

# BabelBeam - Cursor build kit
## Your words. Their language.
Prepared October 15, 2026 for Oliver Ellison / Reliable AI Network, Inc.

This package is a build specification, persistent Cursor rules, configuration examples, and acceptance fixtures. It is **not the implemented application**, a deployed service, or evidence that the live integrations have passed testing.

## Use this package
1. Extract the contents into a new `babelbeam` project folder, or merge them into the root of your existing repository without overwriting unrelated work.
2. Open that folder in Cursor. The root `AGENTS.md` and `.cursor/rules/*.mdc` hold persistent instructions. The longer specifications are in `docs/`.
3. Open Agent mode. Paste the starter prompt below. Let it implement one tested milestone at a time.
4. Supply provider credentials only through your local `.env` or your deployment's secret store, never in chat, screenshots, or committed files. `.env.example` contains no working credentials.
5. Use `docs/BUILD_STATUS.md` to resume work across Agent sessions. Do not equate mock tests with real-device or production approval.

## Paste into Cursor Agent
```text
Build BabelBeam in this repository. Read AGENTS.md, docs/01-product-and-design.md,
docs/02-architecture-and-data.md, docs/03-realtime-and-terminology.md,
docs/04-trial-billing-entitlements.md, docs/05-api-events-security.md,
docs/06-implementation-plan.md, and docs/07-tests-operations-launch.md.

Implement the working application, not just a landing page, mockup, plan, or scaffold.
The non-negotiable commercial requirements are an installable app, a real 14-day
free trial, and automatic renewal at $14.99 USD per calendar month after explicit
consent. The instructor/organization subscribes; students join free. Keep Tom's
pilot organization complimentary through a protected server-side grant.

Start by inspecting the repository and recording a concise implementation plan.
Then complete Phase 0 and proceed to Phase 1. Write code, migrations, tests,
configuration, and operator documentation. Resolve and lock supported dependency
versions. Check current official API documentation before integrating providers.
Do not discard existing work or choose unrelated frameworks without explaining why.

Use the supplied approved BB-and-beam branding as the reference. Produce accessible
dark and light assets; never put the dark wordmark on a dark rectangle or rely on
CSS inversion to fix the logo. Keep the live classroom UI legible and simple.

Prove teacher English -> student Spanish captions and audio on a real streaming
path before polishing secondary pages. Then implement glossary preservation,
private moderated Spanish -> English questions, billing, and installation.

Never expose provider keys, trust client billing state, charge students, invent
provider responses, or call a mock test a successful live integration. Missing
credentials may block a live test, but they must not block all unrelated work.
Record the exact setup needed and continue with safe, explicit test adapters.

After each phase run its checks, update docs/BUILD_STATUS.md, and report what
passed, what remains unverified, and the next step. Do not deploy, enable live
billing, buy services, modify DNS, or send real marketing messages without my
separate approval. Do not stop at a plan: begin the implementation now.
```

## Decisions embodied in this specification
- Confirmed on October 15, 2026: 14-day trial; $14.99 USD recurring monthly price; BabelBeam branding; English/Spanish audio and captions; protected religious terminology; moderated questions. This replaces the earlier 30-day, $19.99 figures.
- Recommended distribution: installable progressive web app (PWA) from BabelBeam.com. This is a website-installed application, not an IPA/APK, executable download, or App Store listing. Native store distribution is a later, separately approved milestone.
- Recommended buyer: one organization subscription, one instructor seat, one concurrent class; students do not pay.
- Recommended commercial guardrails: 300 active classroom minutes per trial and per paid billing period, up to 10 simultaneous student listeners. These are editable assumptions, **not limits Oliver originally specified**. Show them before signup. Obtain owner approval before enabling live sales.
- Recommended rollout: adult technical rehearsal first; children only after the required safeguarding and consent workflow is approved. No false claim that captions-only use eliminates children's privacy requirements.
- Honor the original free arrangement for Tom. No card collection or trial countdown for his complimentary organization. Owner-funded usage safeguards still apply.

## What you will need to configure
OpenAI API access (or an approved replacement speech provider), LiveKit Cloud, Stripe Billing, Supabase Auth, PostgreSQL, Redis, a verified transactional email sender, and a host that supports long-running containers and WebSockets. Supabase may host both Auth and PostgreSQL; it is not necessary to purchase two database services. Use sandbox environments first. Subscription prices, tax settings, launch limits, model lifecycle, privacy terms, and supported devices require an explicit prelaunch check.

## Reading order
`01` defines the experience and visual system. `02` defines services and data. `03` defines live media and terminology. `04` defines billing. `05` defines contracts and security. `06` tells Agent what to implement next. `07` defines tests, deployment, and launch gates. `08` explains what changes for native distribution. `SOURCES.md` records primary documentation and known documentation conflicts.

---
