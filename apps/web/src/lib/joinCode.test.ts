import { describe, expect, it } from "vitest";
import { codeFromQuery, formatJoinCode, joinUrl, listenerLabel } from "./joinCode";

describe("join code display", () => {
  it("groups a six-digit code for the front of the room", () => {
    expect(formatJoinCode("482913")).toBe("482 913");
  });

  it("keeps only digits from a scanned or pasted code", () => {
    expect(codeFromQuery(" 482-913 ")).toBe("482913");
    expect(codeFromQuery(null)).toBe("");
  });

  it("builds a student link on the current site", () => {
    expect(joinUrl("https://babelbeam.com/", "482913")).toBe(
      "https://babelbeam.com/join?code=482913",
    );
  });

  it("names the listener count without a zero looking like a class", () => {
    expect(listenerLabel(0, "none", "one", "{count} many")).toBe("none");
    expect(listenerLabel(1, "none", "one", "{count} many")).toBe("one");
    expect(listenerLabel(2, "none", "one", "{count} many")).toBe("2 many");
  });
});
