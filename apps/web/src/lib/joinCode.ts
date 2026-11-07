export function codeFromQuery(value: string | null): string {
  return (value ?? "").replace(/\D/g, "").slice(0, 6);
}

export function formatJoinCode(code: string): string {
  const digits = codeFromQuery(code);
  if (digits.length <= 3) {
    return digits;
  }
  return `${digits.slice(0, 3)} ${digits.slice(3)}`;
}

export function joinUrl(origin: string, code: string): string {
  return `${origin.replace(/\/$/, "")}/join?code=${codeFromQuery(code)}`;
}

export function listenerLabel(count: number, none: string, one: string, many: string): string {
  if (count <= 0) {
    return none;
  }
  if (count === 1) {
    return one;
  }
  return many.replaceAll("{count}", String(count));
}
