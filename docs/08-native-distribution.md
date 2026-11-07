# 08 - Native distribution

Owner request (2026-11-07): provide a downloadable Class App so screen dimming/lock is less likely to interrupt class.

## Current Class App (pilot)
- Location: `apps/native` (Capacitor shell)
- Loads https://babelbeam.com inside a native WebView
- Uses `@capacitor-community/keep-awake` while **Keep screen awake during class** is on
- Android APK is built by `.github/workflows/class-app-android.yml` and offered on `/install`
- iOS Xcode project is under `apps/native/ios` (bundle id `com.babelbeam.classapp`)
- iOS compile CI: `.github/workflows/class-app-ios.yml` (unsigned build on every native push)
- iOS TestFlight job: same workflow, enabled only when repo variable `IOS_TESTFLIGHT_ENABLED=true` and Apple signing secrets are present (see `apps/native/README.md`)
- Until a TestFlight invite URL is published on `/install`, iPhone teachers use Home Screen install plus keep-awake

## Operator gate for Tom's iPhone
1. Enroll (or reuse) an Apple Developer Program team.
2. Create App Store Connect app **BabelBeam Class**, bundle id `com.babelbeam.classapp`.
3. Create Distribution certificate + App Store provisioning profile; encode as base64 secrets listed in `apps/native/README.md`.
4. Create an App Store Connect API key; store id, issuer, and `.p8` contents as secrets.
5. Set `IOS_TESTFLIGHT_ENABLED=true`, run **Class App iOS** workflow (or push a native change).
6. Add Tom (and other pilot phones) as TestFlight testers; paste the public join URL into `InstallPage.tsx` `IOS_TESTFLIGHT_URL`; redeploy web.

## Honest claims
The Class App is meant to keep the screen on during class. It is not a Play Store / App Store listing yet, not an offline translator, and not a guarantee of microphone capture after a forced lock or OS background kill. See `docs/10-wake-lock-and-background.md`.

## Later store / LiveKit-native path
A fuller React Native/Expo client using the official LiveKit SDK may replace the Capacitor shell later. Native UI/audio/session routing and microphone permissions require device-specific tests. Confirm current SDK/build support, background-audio behavior, provisioning, deep links, account deletion, accessibility, app signing, and distribution requirements.

Store subscriptions/payment links must be reviewed against current Apple and Google policies for the storefront and app category. Do not assume every app may embed Stripe Checkout globally or that a web wrapper automatically avoids store billing rules. Current Apple guidance explicitly distinguishes storefronts and purchasing mechanisms; verify at submission time. [S21]

Keep billing-provider identity separate from effective entitlement, so StoreKit/Google Play entitlements can later map to the same organization subscription without double billing. Support purchase restoration and server verification/notifications when added. Do not offer a second free trial merely because the buyer switches from web to native.

A native store may represent a trial as a calendar month rather than exactly 14 elapsed days. Confirm the permitted durations and obtain approval before changing the customer promise. Do not rename a one-month offer "14 days" without checking.

Native publication requires separate operator approval, accounts/signing assets and testing. No store asset or approval is included in this instruction kit.

---
