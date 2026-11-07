import type { CapacitorConfig } from "@capacitor/cli";

/**
 * Class App loads the live BabelBeam site inside a native shell so Keep Awake
 * can prevent screen dimming during class more reliably than a browser tab.
 */
const config: CapacitorConfig = {
  appId: "com.babelbeam.classapp",
  appName: "BabelBeam Class",
  webDir: "www",
  server: {
    url: "https://babelbeam.com",
    cleartext: false,
    allowNavigation: ["babelbeam.com", "www.babelbeam.com", "*.babelbeam.com"],
  },
  android: {
    allowMixedContent: false,
  },
  plugins: {
    KeepAwake: {},
  },
};

export default config;
