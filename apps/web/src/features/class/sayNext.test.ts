import { describe, expect, it } from "vitest";
import { contextFingerprint, normalizeSuggestions } from "./sayNext";

describe("sayNext helpers", () => {
  it("fingerprints context in order", () => {
    expect(
      contextFingerprint([
        { english: "A.", spanish: "A." },
        { english: "B.", spanish: "B." },
      ]),
    ).not.toBe(contextFingerprint([{ english: "B.", spanish: "B." }, { english: "A.", spanish: "A." }]));
  });

  it("keeps three unique trimmed suggestions", () => {
    expect(
      normalizeSuggestions({
        suggestions: [" Welcome. ", "Welcome.", "Next.", "Also.", "Extra."],
      }),
    ).toEqual(["Welcome.", "Next.", "Also."]);
  });

  it("returns an empty list for bad payloads", () => {
    expect(normalizeSuggestions(null)).toEqual([]);
    expect(normalizeSuggestions({ suggestions: [1, "", "  "] as unknown as string[] })).toEqual([]);
  });
});
