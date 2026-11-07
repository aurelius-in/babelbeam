import type { ContextLine } from "./phraseContext";

/** Wait after the latest sent or heard line before asking the model again. */
export const SAY_NEXT_DEBOUNCE_MS = 500;

export type SayNextResponse = {
  suggestions?: string[];
  phase?: string;
  simulated?: boolean;
  source?: string;
};

export function contextFingerprint(lines: readonly ContextLine[]): string {
  return lines
    .map((line) => `${line.english}\u0001${line.spanish}`)
    .join("\u0002");
}

export function normalizeSuggestions(body: SayNextResponse | null | undefined): string[] {
  const raw = body?.suggestions;
  if (!Array.isArray(raw)) {
    return [];
  }
  const kept: string[] = [];
  const seen = new Set<string>();
  for (const item of raw) {
    if (typeof item !== "string") {
      continue;
    }
    const text = item.replace(/\s+/g, " ").trim();
    if (!text) {
      continue;
    }
    const key = text.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    kept.push(text.slice(0, 220));
    if (kept.length === 3) {
      break;
    }
  }
  return kept;
}
