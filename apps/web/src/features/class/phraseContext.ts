export type ContextLine = {
  english: string;
  spanish: string;
};

export type CleanupMode = "clean" | "verbatim";

export const MAX_CONTEXT_LINES = 3;
export const MAX_CONTEXT_CHARS = 600;
export const MAX_CONTEXT_FIELD_CHARS = 400;

function tidy(text: string): string {
  return text.replace(/\s+/g, " ").trim().slice(-MAX_CONTEXT_FIELD_CHARS);
}

function size(line: ContextLine): number {
  return line.english.length + line.spanish.length;
}

/**
 * Remember one delivered class line for the next request. The lines stay in this
 * browser's memory only: never storage, never the shared class board.
 */
export function rememberLine(lines: readonly ContextLine[], english: string, spanish: string): ContextLine[] {
  const next: ContextLine = { english: tidy(english), spanish: tidy(spanish) };
  if (!next.english && !next.spanish) {
    return [...lines];
  }
  const kept = [...lines, next].slice(-MAX_CONTEXT_LINES);
  while (kept.length > 1 && kept.reduce((total, line) => total + size(line), 0) > MAX_CONTEXT_CHARS) {
    kept.shift();
  }
  if (kept.length === 1 && size(kept[0]) > MAX_CONTEXT_CHARS) {
    const half = MAX_CONTEXT_CHARS / 2;
    kept[0] = { english: kept[0].english.slice(-half), spanish: kept[0].spanish.slice(-half) };
  }
  return kept;
}

export function cleanupMode(enabled: boolean): CleanupMode {
  return enabled ? "clean" : "verbatim";
}
