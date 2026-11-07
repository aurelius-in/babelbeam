import { describe, expect, it } from "vitest";
import { MAX_CONTEXT_CHARS, cleanupMode, rememberLine, type ContextLine } from "./phraseContext";

describe("teacher phrase context", () => {
  it("keeps only the newest three lines", () => {
    let lines: ContextLine[] = [];
    for (let index = 0; index < 5; index += 1) {
      lines = rememberLine(lines, `Line ${index}.`, `Línea ${index}.`);
    }
    expect(lines.map((line) => line.english)).toEqual(["Line 2.", "Line 3.", "Line 4."]);
  });

  it("stays within 600 characters, dropping the oldest lines first", () => {
    const long = "word ".repeat(70);
    let lines: ContextLine[] = [];
    lines = rememberLine(lines, long, long);
    lines = rememberLine(lines, "Newest English.", "Español más reciente.");
    const total = lines.reduce((sum, line) => sum + line.english.length + line.spanish.length, 0);
    expect(total).toBeLessThanOrEqual(MAX_CONTEXT_CHARS);
    expect(lines[lines.length - 1].english).toBe("Newest English.");
  });

  it("trims one oversized line to the budget and keeps its end", () => {
    const lines = rememberLine([], `${"a".repeat(500)} END`, `${"b".repeat(500)} FIN`);
    expect(lines).toHaveLength(1);
    expect(lines[0].english.length + lines[0].spanish.length).toBeLessThanOrEqual(MAX_CONTEXT_CHARS);
    expect(lines[0].english.endsWith("END")).toBe(true);
    expect(lines[0].spanish.endsWith("FIN")).toBe(true);
  });

  it("ignores empty lines and does not change the previous list", () => {
    const before: ContextLine[] = [{ english: "Peace be with you.", spanish: "La paz sea con ustedes." }];
    const after = rememberLine(before, "  ", "\n");
    expect(after).toEqual(before);
    expect(after).not.toBe(before);
  });

  it("maps the teacher toggle to the request mode", () => {
    expect(cleanupMode(true)).toBe("clean");
    expect(cleanupMode(false)).toBe("verbatim");
  });
});
