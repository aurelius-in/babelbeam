/** Keep the class screen awake. Uses native keep-awake inside the Class App, else Wake Lock API. */

import { Capacitor } from "@capacitor/core";
import { KeepAwake } from "@capacitor-community/keep-awake";

export type WakeLockState = "unsupported" | "inactive" | "active" | "blocked";

type WakeLockSentinelLike = {
  released: boolean;
  release: () => Promise<void>;
  addEventListener: (type: "release", listener: () => void) => void;
};

type WakeLockNavigator = Navigator & {
  wakeLock?: {
    request: (type: "screen") => Promise<WakeLockSentinelLike>;
  };
};

const PREF_KEY = "bb-keep-awake";
const memoryPrefs = new Map<string, string>();

function readPref(key: string): string | null {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      return window.localStorage.getItem(key);
    }
  } catch {
    // Fall through to memory.
  }
  return memoryPrefs.get(key) ?? null;
}

function writePref(key: string, value: string): void {
  memoryPrefs.set(key, value);
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.setItem(key, value);
    }
  } catch {
    // Memory map still holds the value for this session.
  }
}

export function readKeepAwakePref(): boolean {
  return readPref(PREF_KEY) !== "0";
}

export function storeKeepAwakePref(enabled: boolean): void {
  writePref(PREF_KEY, enabled ? "1" : "0");
}

export function isClassAppRuntime(): boolean {
  try {
    return Capacitor.isNativePlatform();
  } catch {
    return false;
  }
}

export function wakeLockSupported(): boolean {
  if (isClassAppRuntime()) {
    return true;
  }
  return typeof navigator !== "undefined" && Boolean((navigator as WakeLockNavigator).wakeLock);
}

export type WakeLockController = {
  state: () => WakeLockState;
  setEnabled: (enabled: boolean) => Promise<WakeLockState>;
  dispose: () => void;
};

/**
 * Keeps the screen on while class is live.
 * Class App (Capacitor): native keep-awake, more reliable than browser alone.
 * Browser/PWA: Screen Wake Lock API while the tab is visible.
 * Neither path promises microphone capture after the OS fully locks the device.
 */
export function createWakeLockController(
  onChange?: (state: WakeLockState) => void,
): WakeLockController {
  let enabled = false;
  let sentinel: WakeLockSentinelLike | null = null;
  let disposed = false;
  let usingNative = false;
  let current: WakeLockState = wakeLockSupported() ? "inactive" : "unsupported";

  function publish(next: WakeLockState) {
    current = next;
    onChange?.(next);
  }

  async function releaseNative() {
    if (!usingNative) {
      return;
    }
    usingNative = false;
    try {
      await KeepAwake.allowSleep();
    } catch {
      // Ignore.
    }
  }

  async function releaseSentinel() {
    await releaseNative();
    const held = sentinel;
    sentinel = null;
    if (!held || held.released) {
      return;
    }
    try {
      await held.release();
    } catch {
      // Release failures must not break the class console.
    }
  }

  async function acquireNative(): Promise<WakeLockState> {
    try {
      const support = await KeepAwake.isSupported();
      if (!support.isSupported) {
        publish("unsupported");
        return current;
      }
      await KeepAwake.keepAwake();
      usingNative = true;
      publish("active");
      return current;
    } catch {
      publish("blocked");
      return current;
    }
  }

  async function acquireBrowser(): Promise<WakeLockState> {
    if (!wakeLockSupported()) {
      publish("unsupported");
      return current;
    }
    if (typeof document !== "undefined" && document.visibilityState !== "visible") {
      publish("inactive");
      return current;
    }
    if (sentinel && !sentinel.released) {
      publish("active");
      return current;
    }
    try {
      const api = (navigator as WakeLockNavigator).wakeLock;
      if (!api) {
        publish("unsupported");
        return current;
      }
      const next = await api.request("screen");
      if (disposed || !enabled) {
        try {
          await next.release();
        } catch {
          // Ignore.
        }
        return current;
      }
      sentinel = next;
      next.addEventListener("release", () => {
        if (sentinel === next) {
          sentinel = null;
          if (!disposed && enabled) {
            publish("inactive");
          }
        }
      });
      publish("active");
      return current;
    } catch {
      publish("blocked");
      return current;
    }
  }

  async function acquire(): Promise<WakeLockState> {
    if (disposed || !enabled) {
      return current;
    }
    if (isClassAppRuntime()) {
      return acquireNative();
    }
    // Prefer the Capacitor web implementation when present, then fall back.
    try {
      const support = await KeepAwake.isSupported();
      if (support.isSupported) {
        await KeepAwake.keepAwake();
        usingNative = true;
        publish("active");
        return current;
      }
    } catch {
      // Fall through to the browser Wake Lock API.
    }
    return acquireBrowser();
  }

  function onVisibility() {
    if (disposed || !enabled || isClassAppRuntime()) {
      return;
    }
    if (document.visibilityState === "visible") {
      void acquire();
    } else {
      void releaseSentinel().then(() => {
        if (!disposed && enabled) {
          publish("inactive");
        }
      });
    }
  }

  if (typeof document !== "undefined") {
    document.addEventListener("visibilitychange", onVisibility);
  }

  return {
    state: () => current,
    setEnabled: async (nextEnabled: boolean) => {
      enabled = nextEnabled;
      storeKeepAwakePref(nextEnabled);
      if (!nextEnabled) {
        await releaseSentinel();
        publish(wakeLockSupported() ? "inactive" : "unsupported");
        return current;
      }
      return acquire();
    },
    dispose: () => {
      disposed = true;
      enabled = false;
      if (typeof document !== "undefined") {
        document.removeEventListener("visibilitychange", onVisibility);
      }
      void releaseSentinel();
    },
  };
}
