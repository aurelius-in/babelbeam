# Primary sources and evidence boundaries

Reviewed October 15, 2026. These sources support provider/platform facts, not a claim that this application is built or validated. Architecture, usage caps, timeouts, UI copy, and build order are design recommendations. Re-check official docs, lifecycle, account access, and rates when implementing.

## Product source
Oliver supplied Tom Louie's requirements and the free-build/referral arrangement in this conversation. The October 14 project blueprint established English/Spanish interpretation, original-language terminology, moderated questions, and server-side permissions. The latest owner decision, October 15, 2026, is an installable website, a 14-day free trial, and $14.99 monthly billing. That replaces the earlier 30-day, $19.99 figures. Earlier "defer payments" exclusions are superseded by this request. Brand concept: approved paired Bs and projected beam.

## Important documentation conflict
At review, the TTS guide still demonstrated gpt-4o-mini-tts while the model page displayed a Deprecated label. Do not choose a production TTS model solely from a tutorial or silently treat an alias as supported forever. Resolve the lifecycle/account-access question through the current provider documentation/dashboard and a real smoke test; log the outcome. The old gpt-4.1-mini model page also showed a deprecated label, so this kit does not base new translation code on it.

Stripe's broader trial documentation includes newer paid/item-level offers. The required simple 30-day subscription-level free trial is described by the Checkout free-trial guide; do not inadvertently implement a different offer type.

## [S1] Cursor project rules and AGENTS.md
`https://cursor.com/help/customization/rules`

Rules placement and persistent instructions.

## [S2] MDN: Making PWAs installable
`https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable`

Manifest, installation behavior, and platform differences.

## [S3] OpenAI: Realtime transcription
`https://developers.openai.com/api/docs/guides/realtime-transcription`

Live transcription session, explicit commits, hints, and model-specific VAD constraints.

## [S4] OpenAI: GPT-Live-Transcribe model
`https://developers.openai.com/api/docs/models/gpt-live-transcribe`

Current documented live transcription candidate and $0.017/minute rate.

## [S5] OpenAI: GPT-5.4 Mini model
`https://developers.openai.com/api/docs/models/gpt-5.4-mini`

Candidate text model, supported reasoning configuration and snapshots.

## [S6] OpenAI: Text to speech guide
`https://developers.openai.com/api/docs/guides/text-to-speech`

Streaming speech, formats, language/voice considerations, artificial-voice disclosure.

## [S7] OpenAI: GPT-4o Mini TTS model
`https://developers.openai.com/api/docs/models/gpt-4o-mini-tts`

Lifecycle label must be checked alongside the speech guide before selecting a production model.

## [S8] OpenAI: Data controls
`https://developers.openai.com/api/docs/guides/your-data`

Provider retention controls and limits of store=false/zero-retention claims.

## [S9] LiveKit pricing
`https://livekit.com/pricing`

Distinguishes participant minutes, self-hosted workers, hosted agent sessions, data transfer and plan allowances.

## [S10] LiveKit: Access tokens and grants
`https://docs.livekit.io/frontends/reference/tokens-grants/`

Role/source grants, opaque identities, and Cloud-specific token revocation.

## [S11] LiveKit: Room service API
`https://docs.livekit.io/reference/other/roomservice-api/`

Backend room and participant control.

## [S12] Stripe: Configure free trials for Checkout
`https://docs.stripe.com/payments/checkout/free-trials`

Subscription-level free trial duration and payment-method collection.

## [S13] Stripe: Create a Checkout Session
`https://docs.stripe.com/api/checkout/sessions/create`

Current Checkout field contract. Pin the selected API version.

## [S14] Stripe: Trial/promotion compliance requirements
`https://docs.stripe.com/billing/subscriptions/trials/manage-trial-compliance`

Reminder/cancellation disclosures and documented 7-day reminder behavior.

## [S15] Stripe: Manage webhook endpoints
`https://docs.stripe.com/events/manage-webhook-endpoints`

Signed webhooks, duplicate/retry handling and recovery.

## [S16] Stripe: Using webhooks with subscriptions
`https://docs.stripe.com/billing/subscriptions/webhooks`

Subscription status and paid access lifecycle.

## [S17] Stripe: Test Billing integration
`https://docs.stripe.com/billing/testing`

Sandbox/test clocks, payment failures, approximately 3-day trial_will_end event.

## [S18] Supabase: Passwordless email sign-in
`https://supabase.com/docs/guides/auth/auth-email-passwordless`

Managed email OTP request/verification flow.

## [S19] OWASP: Session Management Cheat Sheet
`https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html`

Session cookies, expiry, rotation and CSRF defense-in-depth.

## [S20] FTC: COPPA six-step compliance plan
`https://www.ftc.gov/business-guidance/resources/childrens-online-privacy-protection-rule-six-step-compliance-plan-your-business`

Child voice/persistent identifiers, consent and privacy review.

## [S21] Apple: App Review Guidelines
`https://developer.apple.com/app-store/review/guidelines/`

Future native distribution/payment requirements vary with storefront and mechanism.

---
