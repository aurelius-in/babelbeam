import { describe, expect, it } from "vitest";
import { lessonSmsMessage, normalizeSmsPhone, smsComposeUrl } from "./smsShare";

describe("sms share helpers", () => {
  it("normalizes phone numbers for sms URLs", () => {
    expect(normalizeSmsPhone("(555) 123-4567")).toBe("5551234567");
    expect(normalizeSmsPhone("+1 (555) 123-4567")).toBe("+15551234567");
    expect(normalizeSmsPhone("  ")).toBe("");
  });

  it("builds apple and android compose URLs", () => {
    const message = "BabelBeam lesson: https://babelbeam.com/share/x";
    expect(smsComposeUrl(message, "5551234567", "iPhone")).toBe(
      `sms:5551234567&body=${encodeURIComponent(message)}`,
    );
    expect(smsComposeUrl(message, "5551234567", "Android")).toBe(
      `sms:5551234567?body=${encodeURIComponent(message)}`,
    );
    expect(smsComposeUrl(message, "", "iPhone")).toBe(`sms:&body=${encodeURIComponent(message)}`);
  });

  it("includes an optional course title in the message", () => {
    expect(lessonSmsMessage("https://example.com/share/a", "Baptism")).toBe(
      "BabelBeam lesson (Baptism): https://example.com/share/a",
    );
  });
});
