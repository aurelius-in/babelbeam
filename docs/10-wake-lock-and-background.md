# Wake lock and background capture (Milestone E)

## Class App (recommended for teachers)
Download from https://babelbeam.com/install (Android APK pilot). The Class App loads BabelBeam in a native shell and uses Capacitor Keep Awake so the screen is less likely to dim or lock while **Keep screen awake during class** is on.

## Supported browser/PWA behavior
Without the Class App, BabelBeam uses the Screen Wake Lock API when the teacher enables **Keep screen awake during class**.

Supported behavior (foreground browser/PWA tab visible):
- Request a screen wake lock while class is live and the preference is on.
- Re-acquire after the tab becomes visible again.
- Show active, inactive, unsupported, or blocked status in the teacher UI.

## Documented OS limits
Neither the Class App keep-awake path nor the PWA path guarantees:
- Teacher microphone capture after a forced screen lock
- Continuous capture after the OS kills the app or stops background audio
- Student translated-audio playback under every lock-screen media policy

Do not claim those behaviors until device tests pass and, if needed, a deeper native audio-session build is approved.

## Required physical device matrix (operator)
Test separately for teacher capture and student playback:

| Device | OS | Browser/PWA | Screen off | Lock | App switch | Incoming call | Network loss/reconnect |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Tom phone | | | | | | | |
| Student phones | | | | | | | |

Pass criteria for web: uninterrupted supported foreground behavior, or clear recovery UX when the OS interrupts capture.

## Native decision gate
Only start native iOS/Android work after the matrix above shows the required teaching experience is unacceptable on web/PWA. See `docs/08-native-distribution.md`.

## Quality-review workflow (software)
Teachers can rate aligned English/Spanish transcript segments on the lesson review page and leave correction notes. Original recognized text remains immutable. Use these samples with volunteer bilingual reviewers only with permission.
