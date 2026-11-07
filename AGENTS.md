# BabelBeam - permanent project instructions

Build a real, installable classroom interpretation product for parishes. The catechist teaches in English; students receive Spanish audio and captions and can ask teacher-approved questions in Spanish. The teacher hears those questions in English. This is an interpreter, not a chatbot or doctrinal authority.

## Source of truth
Read `docs/01-product-and-design.md` through `docs/07-tests-operations-launch.md`. Read the relevant spec before modifying its subsystem. Update `docs/BUILD_STATUS.md` after every milestone. Resolve conflicts in this order: latest explicit owner decision, these specifications, approved branding, older brochure examples. The brochures are visual/product references, not evidence of deployed features.

## Commercial invariants
- Plan price is 1499 US cents ($14.99), recurring monthly. The initial trial is 14 elapsed days, not a calendar month and not 14 days after every installation. Owner decision on October 15, 2026 replaced the earlier 30-day, $19.99 figures.
- Download/install is free. Trial activation occurs after verified account creation, clear renewal consent, and successful Stripe Checkout completion.
- Students never need billing accounts, credit cards, or individual subscriptions.
- No automatic renewal without a saved payment method and affirmative consent. Stripe executes billing; application cron jobs must not charge cards.
- Keep Tom's organization complimentary using a protected grant; never infer his account from a guessed email address or organization display name.
- Limits in the example config are proposed launch assumptions; do not advertise unlimited use. Do not activate live sales until approved.
- Never trust localStorage, a redirect, or a browser timestamp as proof of access.

## Engineering invariants
- React/TypeScript/Vite PWA; FastAPI; PostgreSQL; ephemeral Redis; LiveKit Cloud; asynchronous Python translation worker. Use vetted Auth integration with Supabase email OTP.
- Preserve tenant boundaries on every HTTP route, WebSocket, database operation, and media token.
- Use separate media rooms for public Spanish output, private teacher audio, and a temporary private question turn. No raw student or private English audio in the broadcast room.
- Translate and synthesize once per class/output language, not once per listener.
- All floor grants and usage entitlement checks are server-authoritative and race-tested.
- Translation input is untrusted data. No tools, browsing, instruction following, answering, or unapproved summaries inside the translation pipeline.
- Validate protected terminology before emitting captions or synthesized speech. Do not claim perfect spoken-term recognition.
- No recordings or durable classroom transcripts by default. Do not log source speech, captions, question text, names, join codes, tokens, or API keys.
- Never ship demos as live integration. Fake providers only in explicit development/test mode; production startup fails if they are enabled.

## Execution style
Inspect first; implement small vertical slices; add tests with each slice; run migrations and checks; repair failures; report evidence. Do not merely describe code that should exist. Do not rewrite unrelated files. Never delete a database, reset a repo, change DNS, purchase resources, enable real billing, or deploy without approval.

Use strict TypeScript and Python type hints, structured errors, bounded retries, timeouts, cancellation, explicit state machines, and tested idempotency. Lock dependency versions. Read current official provider documentation and record the tested versions. Do not invent SDK fields or use deprecated models merely because an older example used them.

## Design
Approved concept: two legible integrated Bs plus a projected cyan beam. Navy/cyan, restrained premium parish styling, spacious mobile-first screens. Dark backgrounds require a light/cyan logo variant with real transparency. No visible logo background box. Accessibility beats decorative luxury.

## Done means
Working workflows, passing automated checks, honest real-integration evidence, usable installation, functioning 14-day-to-$14.99 billing tests, documented deployment and rollback, and clearly listed remaining operator approvals. Browser automation does not replace physical phone/headset testing.

---
