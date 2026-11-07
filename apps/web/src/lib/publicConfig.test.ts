import { describe, expect, it } from "vitest";
import { bannerState, formatMinutes, formatUsd, type PublicConfig } from "./publicConfig";

const liveConfig: PublicConfig = {
  app_name: "BabelBeam",
  provider_mode: "live",
  simulated: false,
  price_cents: 1499,
  trial_days: 14,
  currency: "usd",
  student_price_cents: 0,
  max_student_listeners: 10,
  included_class_seconds: 18000,
  plan_limits_approved: false,
  limits_are_proposed: true,
  minors_enabled: false,
  production_billing_enabled: false,
  billing_implemented: false,
};

describe("public config display", () => {
  it("formats the confirmed monthly price", () => {
    expect(formatUsd(1499)).toBe("$14.99");
  });

  it("shows proposed classroom minutes without calling them approved", () => {
    expect(formatMinutes(18000)).toBe(300);
  });

  it("keeps simulated mode visible", () => {
    expect(bannerState({ ...liveConfig, simulated: true, provider_mode: "mock" }, false)).toBe(
      "simulated",
    );
  });

  it("does not claim a live provider when the API cannot be reached", () => {
    expect(bannerState(null, true)).toBe("unknown");
    expect(bannerState(liveConfig, false)).toBe("live");
  });
});
