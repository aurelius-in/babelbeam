# BabelBeam Class App

Native shell for teachers and students who need the screen to stay awake during class.

- Loads https://babelbeam.com inside Capacitor
- Uses `@capacitor-community/keep-awake` so dimming/lock is blocked while class keep-awake is on
- Android APK is built by GitHub Actions and published on the Install page

## Local Android build

1. Install Android Studio and accept SDK licenses.
2. From this folder:

```powershell
npm install
npx cap add android
npx cap sync android
cd android
.\gradlew.bat assembleRelease
```

The APK is written under `android/app/build/outputs/apk/`.

## Honest limits

Keep-awake prevents the screen from sleeping while the Class App is open and the preference is on. It does not claim microphone capture after the user force-locks the phone or after the OS kills background audio. See `docs/10-wake-lock-and-background.md`.
