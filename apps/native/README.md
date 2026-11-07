# BabelBeam Class App

Native shell for teachers and students who need the screen to stay awake during class.

- Loads https://babelbeam.com inside Capacitor
- Uses `@capacitor-community/keep-awake` so dimming/lock is blocked while class keep-awake is on
- Android APK is built by GitHub Actions and published on the Install page
- iOS project is in `ios/`; compile CI runs on macOS; TestFlight upload runs when Apple signing secrets are configured

## Local Android build

1. Install Android Studio and accept SDK licenses.
2. From this folder:

```powershell
npm install
npx cap sync android
cd android
.\gradlew.bat assembleRelease
```

The APK is written under `android/app/build/outputs/apk/`.

## Local iOS build (macOS + Xcode)

1. Apple Developer Program membership (paid) for device installs and TestFlight.
2. From this folder on a Mac:

```bash
npm install
npx cap sync ios
npx cap open ios
```

3. In Xcode: select the App target, set your Team, then Run on a physical iPhone or Archive for TestFlight.

Bundle id: `com.babelbeam.classapp`.

## TestFlight CI secrets

Set repository variable `IOS_TESTFLIGHT_ENABLED=true` only after these secrets exist:

| Secret | Purpose |
| --- | --- |
| `APPLE_TEAM_ID` | 10-character Apple Team ID |
| `IOS_DIST_CERT_P12` | Base64-encoded Apple Distribution `.p12` |
| `IOS_DIST_CERT_PASSWORD` | Password for that `.p12` |
| `IOS_PROVISIONING_PROFILE` | Base64-encoded App Store provisioning profile for `com.babelbeam.classapp` |
| `IOS_KEYCHAIN_PASSWORD` | Temporary CI keychain password |
| `ASC_KEY_ID` | App Store Connect API key id |
| `ASC_ISSUER_ID` | App Store Connect issuer id |
| `ASC_KEY_CONTENT` | Contents of the `.p8` API key |

Create the App Store Connect app for BabelBeam Class before the first upload. After a build is approved for external/internal testing, put the public `https://testflight.apple.com/join/...` URL into `IOS_TESTFLIGHT_URL` in `apps/web/src/features/pages/InstallPage.tsx` and redeploy the site.

## Honest limits

Keep-awake prevents the screen from sleeping while the Class App is open and the preference is on. It does not claim microphone capture after the user force-locks the phone or after the OS kills background audio. See `docs/10-wake-lock-and-background.md`.
