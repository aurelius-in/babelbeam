# 04 - 14-day trial, $14.99/month, and entitlements

## 1. Commercial contract
Confirmed owner requirements as of October 15, 2026: installable website, 14 days free, then $14.99/month. This replaces the earlier 30-day, $19.99 figures. Implement one product, one monthly recurring USD price of **1499 cents**, quantity **1**, and one trial entitlement per eligible verified buyer. Students join free. Checkout is not connected in the current build. No annual plan, setup fee, automatic overage, per-student charge, or second subscription added silently.

Recommended buyer/limits: one organization, one teacher seat, one concurrent class, 300 active classroom minutes per trial and per paid billing period, up to 10 concurrent student listeners. Limits are proposed business assumptions, not requirements already specified by Oliver. Keep them centralized/configurable, show them before Checkout, and require approval before live sales. Do not describe a metered trial as unlimited.

Student traffic consumes the organizer's classroom allowance; students never see a paywall. A sponsor/complimentary grant can override limits within an approved operating budget. Demo access does not establish a paid trial.

## 2. Install is not billable activation
The PWA can be installed free. Trial activation requires verified adult login, a billing-owner organization, explicit renewal consent, and a completed Stripe Checkout subscription session. Store the actual Stripe trial dates. Use server UTC for enforcement and the chosen account timezone for human-readable dates.

Do not use the device clock, browser localStorage, first-page-visit cookie, or a cron-generated PaymentIntent for subscription access. Reinstallation and new devices do not restart a trial. A paid returner may resubscribe without another free trial.

Checkout configured with `mode: subscription`, a server-controlled Price, `subscription_data.trial_period_days: 30`, and payment-method collection for renewal supports this flow [S12-S13]. A card-free trial cannot auto-charge unless a valid payment method and consent are obtained later. This specification chooses card-required activation to meet the requested automatic conversion.

## 3. Pricing and consent copy
Use current server configuration for the price/allowance everywhere. Suggested short copy:

> Start your 14-day free trial. $0 today. Then $14.99 USD/month, plus applicable tax. A card will be required when checkout is connected. Your subscription renews automatically unless you cancel. Cancel in Billing before your trial ends to avoid the first charge. Students join free. Card and checkout are not connected yet.

Before activation display the included allowance and listener limit beside the price. Present an unchecked affirmative renewal-consent control and a Terms/Privacy acknowledgment, with links. Do not pre-check consent, hide the next price behind a tooltip, or use an ambiguous "Continue" button. Suggested CTA: **Start 14-day free trial**.

Once the subscription exists, confirmation, dashboard, and welcome email show the actual first billing date and easy cancellation link. Before creation say "30 days after activation" rather than fabricating an exact pre-Checkout timestamp. Keep marketing consent separate and optional.

Record the user, organization, consent/disclosure version, trial_days, amount, currency, interval, acceptance time, and associated checkout attempt. Do not store card numbers/CVC. Enabling Stripe Tax or changing tax-inclusive/exclusive behavior requires the owner's tax setup review; do not claim a Stripe integration itself settles tax registration obligations.

## 4. Stripe objects and checkout algorithm
Create the product/price once with an idempotent setup script. Verify at startup or billing preflight that the selected price is active, USD, 1499 cents, recurring monthly, and belongs to the expected product. The client may submit a fixed plan slug, never an arbitrary amount, Price ID, quantity, trial days, customer ID, or organization billing owner.

`POST /api/v1/billing/checkout`:
1. Authenticate user, require organization owner and recent authentication, validate CSRF and consent version.
2. Lock the organization's billing state. Reject complimentary/suspended accounts or an existing active/trialing subscription. Return the existing valid pending checkout when appropriate.
3. Resolve eligibility from durable verified identity/organization records; trial eligibility is not `has no subscription row`.
4. Create/reuse the Stripe Customer mapped to this organization. Stripe metadata contains opaque internal IDs only.
5. Persist a checkout attempt with a stable idempotency key. Do not hold a DB lock over an unbounded provider network request; use attempt state and a short transaction, then reconcile the result.
6. Create hosted Checkout. Fixed server return URLs; never accept an arbitrary redirect from the client. Include the trial only when eligible. Returning users get an explicitly disclosed paid checkout without trial.
7. Save the Stripe Checkout ID and URL against the attempt. If the network times out, retry with the same key and recover, rather than making a second subscription.
8. Expire competing abandoned sessions when possible. A browser cannot bypass one-trial rules by opening two checkouts concurrently. Reconcile any orphan/duplicate subscription and flag it for safe operator handling.

Payload shape (adapt to the pinned Stripe SDK; this is a contract example, not an untested full endpoint):
```json
{
  "mode": "subscription",
  "customer": "SERVER_RESOLVED_CUSTOMER_ID",
  "line_items": [{"price": "SERVER_CONFIGURED_MONTHLY_PRICE_ID", "quantity": 1}],
  "payment_method_collection": "always",
  "payment_method_types": ["card"],
  "subscription_data": {
    "trial_period_days": 30,
    "trial_settings": {"end_behavior": {"missing_payment_method": "cancel"}},
    "metadata": {"organization_id": "SERVER_RESOLVED_ORG_ID"}
  },
  "client_reference_id": "SERVER_RESOLVED_ORG_ID",
  "consent_collection": {"terms_of_service": "required"},
  "success_url": "https://babelbeam.com/app/billing/return?session_id={CHECKOUT_SESSION_ID}",
  "cancel_url": "https://babelbeam.com/app/billing"
}
```
Use the current hosted Checkout fields and account Terms URL configuration. Confirm a 30-day **subscription-level free trial**, not a new paid/item-level trial-offer feature merely because its documentation is newer. Stripe field shapes/API versions can change; pin and test rather than copy obsolete subscription period fields. [S12-S13]

Do not activate access from `success_url`. The return page polls the backend for confirmed status. A server-side lookup of the authenticated user's completed Checkout may reconcile status when a webhook is delayed; it must verify customer, org, product, subscription, and completion. Replaying a session ID from another account must fail.

## 5. Webhooks, reconciliation, and payment reality
Verify Stripe signatures against the **raw request body** before parsing/acting. Enforce environment separation and HTTPS. Persist a minimal event record and durable job before returning success. Duplicate delivery is normal; use a UNIQUE provider event ID and idempotent business updates. Payment webhooks are CSRF-exempt but signature-authenticated. [S15]

Handle at least:
- `checkout.session.completed` and checkout expiry/failure as relevant.
- `customer.subscription.created`, `.updated`, `.deleted`, `.trial_will_end`.
- `invoice.paid`, `invoice.payment_failed`, `invoice.payment_action_required`, `invoice.finalization_failed`.
- The selected provider's supported dispute/refund event mapping for an operator alert and documented handling.

Events can arrive out of order. Fetch canonical current objects where needed; serialize reconciliation per organization and match the subscription/customer/product. Do not let a stale update overwrite a later cancellation or create a new paid period. Maintain processing retries and a dead-letter/operator alert path.

A zero-dollar trial invoice is not proof that a paid month was purchased. Extend paid access using the actual settled qualifying subscription period and current status, not by adding 30 days to every `invoice.paid`. An invoice paid through an authorized account credit can be valid; do not hard-code "amount_paid must be positive" as the only evidence. Match the correct recurring line/period and reconcile the live subscription. [S16]

Stripe attempts the first payment at the trial boundary according to its invoice/payment lifecycle. Do not promise that a successful card charge occurs at the exact millisecond of expiry. Handle required authentication, declined cards, missing payment methods, delayed webhooks, and invoice failures explicitly. Run a scheduled canonical reconciliation for active/trialing/past-due accounts so missed events cannot leave permanent free access.

## 6. Application entitlement state
Never scatter billing checks across React components. Implement one backend `EntitlementService` used for room creation, join admission, media tokens, worker admission, renewals, and periodic active-class checks.

| Effective state | Access |
| --- | --- |
| `complimentary` | Approved sponsor access, no card/trial/renewal; configured budget/limits apply. |
| `trialing` | Full core product within disclosed allowance until server trial_end. |
| `active_paid` | Product through the confirmed paid-through boundary, within allowance. |
| `canceling_trial` | Trial continues until confirmed expiry; no first charge. |
| `canceling_paid` | Paid period continues through paid-through; no next renewal. |
| `payment_pending` | Return/recovery UI; no fabricated paid entitlement while verification is unresolved. |
| `past_due_grace` | Optional 72-hour recovery for previously paying accounts; clearly bounded. |
| `expired`, `unpaid`, `canceled`, `incomplete`, `paused` | No new hosting/media grants; billing/help remains accessible. |
| `suspended` | Owner-controlled security block overrides ordinary access. |

Initial payment failure at the end of a free trial does not get a second undisclosed multi-day trial. Allow only the defined active-class wind-down, then require payment recovery. For previously paying customers, the suggested 72-hour grace is a business assumption configurable by the owner.

Check access before creating rooms, issuing tokens, and assigning workers, plus at least once per minute during an active class. Token expiry alone does not terminate an already connected media participant. On revocation/expiry, notify the teacher, apply a one-time bounded active-class wind-down (recommended 10 minutes), then stop the worker and remove/delete media rooms. No new sessions can start in wind-down. Persist the wind-down deadline so reconnect cannot reset it.

Do not display the teacher's payment problem to students; say the class is unavailable/ended and ask them to contact their instructor. Billing settings and cancellation remain reachable even after hosting access ends.

## 7. Cancellation and renewal notices
Provide a visible Manage subscription/Cancel trial action using a server-created Stripe Customer Portal session, plus a direct cancellation path if needed for the exact trial-end behavior. Users cancel through a simple confirmation; no mandatory survey, call, email, or retention obstacle.

During trial, schedule cancellation at the actual trial boundary with no conversion invoice. For a paid subscription, cancel at paid-period end by default. Verify the pinned API's trial/period behavior instead of assuming the same field always applies. Reflect canonical cancellation state and confirmation in the app/email. Uninstalling the PWA does not cancel; explain this in Billing/install help.

Configure trial-end reminder emails, including the documented 7-day pre-expiry reminder. The `trial_will_end` webhook is normally a different, approximately 3-day event and is not a replacement for a 7-day schedule. Avoid duplicate notices when Stripe and the application both send. Persist reminder jobs with unique keys and test them; Stripe-hosted reminder emails are not sent in its sandbox, so sandbox billing tests do not prove delivery. [S14, S17]

Capture the disclosure/consent and obtain a qualified review of renewal, cancellation, tax, privacy, and card-network requirements for launch markets. This implementation specification is not legal advice or a claim of compliance certification.

## 8. Tom's complimentary organization
Implement a protected operator action taking an explicit existing organization UUID, reason, approver, and optional limit overrides. Never auto-grant free access to any account whose name contains Tom or Our Lady of Victory. Verify the real organization/account with Oliver first; do not guess an email from correspondence.

The complimentary grant overrides purchase requirements but not security/safeguarding. Its UI says **Complimentary parish access** with no countdown or card prompt. Do not create a Stripe subscription for it. Revoking a grant must never start charging; any future conversion requires a new explicit Checkout/consent flow. Existing paid subscriptions must be resolved explicitly before applying a free grant so customers do not keep paying by mistake.

## 9. Metering, limits, and unit economics
The example plan has 18,000 active classroom seconds in the trial and each actual paid subscription period. Unused time does not roll over under the proposed policy. Both directions count toward the same classroom time; 10 students listening simultaneously do **not** multiply the customer-facing classroom-minute counter by 10.

Meter LIVE classroom wall-clock time, including natural silence and student questions, not token counts. Pause/failure states stop the customer-facing teaching meter. Separate provider accounting still tracks connected participant time, output speech time, retries, and idle costs. No-show classes should return to READY or end after a short disclosed idle timeout.

Record worker heartbeats/meter sequences idempotently; authoritative DB transactions reserve/consume small bounded time slices so multiple workers cannot double-spend or double-charge. Allocate across period boundaries using the actual subscription period. Record clock monotonicity/fencing; never trust client-submitted usage.

Show remaining time before a session, at 80%/95% use, and when close to exhaustion. At exhaustion, block new starts; one active class receives only its nonrenewable wind-down. No automatic overage charge. Allowance increases require an owner-approved grant or a separately consented future plan, not a hidden invoice.

Cost ledger formula:
`STT duration/tokens + translation tokens + TTS duration/tokens/characters + media participant time + egress + compute + database/email/monitoring + payment fees`.

Live transcription alone is currently listed at $0.017/minute for the chosen candidate, or $5.10 for 300 fully billed minutes, before translation, synthesized speech, transport, and hosting. LiveKit's listed participant charges distinguish user/self-hosted-worker connections from hosted-agent sessions; do not double-count the wrong plan. Included tiers and minimum plan fees also matter. [S4, S9]

The $14.99 price is an owner requirement, **not a proven profitable unlimited tariff**. Measure an actual full-class cost and create a sensitivity report for 1/5/10 listeners, shorter/longer classes, trial conversions, and all customers consuming their allowance. Store provider rates in configuration with verification dates. Capacity/budget limits should stop new free-trial admissions before runaway spending, without silently cutting an existing session.

---
