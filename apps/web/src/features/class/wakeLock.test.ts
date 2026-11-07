import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@capacitor/core", () => ({
  Capacitor: {
    isNativePlatform: () => false,
  },
}));

vi.mock("@capacitor-community/keep-awake", () => ({
  KeepAwake: {
    isSupported: vi.fn(async () => ({ isSupported: false })),
    keepAwake: vi.fn(async () => undefined),
    allowSleep: vi.fn(async () => undefined),
  },
}));

import {
  createWakeLockController,
  readKeepAwakePref,
  storeKeepAwakePref,
  wakeLockSupported,
} from "./wakeLock";

afterEach(() => {
  vi.unstubAllGlobals();
  storeKeepAwakePref(true);
});

describe("wake lock preference", () => {
  it("defaults to enabled and stores the teacher choice", () => {
    expect(readKeepAwakePref()).toBe(true);
    storeKeepAwakePref(false);
    expect(readKeepAwakePref()).toBe(false);
    storeKeepAwakePref(true);
    expect(readKeepAwakePref()).toBe(true);
  });
});

describe("wake lock controller", () => {
  it("reports unsupported when the API is missing", async () => {
    vi.stubGlobal("navigator", {});
    expect(wakeLockSupported()).toBe(false);
    const controller = createWakeLockController();
    expect(controller.state()).toBe("unsupported");
    await expect(controller.setEnabled(true)).resolves.toBe("unsupported");
    controller.dispose();
  });

  it("acquires and releases a screen wake lock when supported", async () => {
    const release = vi.fn(async () => undefined);
    const listeners = new Map<string, () => void>();
    const sentinel = {
      released: false,
      release: async () => {
        sentinel.released = true;
        await release();
        listeners.get("release")?.();
      },
      addEventListener: (type: "release", listener: () => void) => {
        listeners.set(type, listener);
      },
    };
    const request = vi.fn(async () => sentinel);
    vi.stubGlobal("navigator", { wakeLock: { request } });
    vi.stubGlobal("document", {
      visibilityState: "visible",
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    });

    const controller = createWakeLockController();
    expect(controller.state()).toBe("inactive");
    await expect(controller.setEnabled(true)).resolves.toBe("active");
    expect(request).toHaveBeenCalledWith("screen");
    await expect(controller.setEnabled(false)).resolves.toBe("inactive");
    expect(release).toHaveBeenCalled();
    controller.dispose();
  });
});
