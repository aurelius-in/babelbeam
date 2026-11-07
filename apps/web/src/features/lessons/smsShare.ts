/** Build a native SMS compose URL. The OS Messages app still requires the teacher to tap Send. */

export function normalizeSmsPhone(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) {
    return "";
  }
  const hasPlus = trimmed.startsWith("+");
  const digits = trimmed.replace(/\D/g, "");
  if (!digits) {
    return "";
  }
  return hasPlus ? `+${digits}` : digits;
}

export function smsComposeUrl(message: string, phone = "", userAgent = ""): string {
  const body = encodeURIComponent(message);
  const number = normalizeSmsPhone(phone);
  const ua = userAgent || (typeof navigator !== "undefined" ? navigator.userAgent : "");
  const apple = /iPad|iPhone|iPod|Macintosh/.test(ua);
  if (number) {
    return apple ? `sms:${number}&body=${body}` : `sms:${number}?body=${body}`;
  }
  return apple ? `sms:&body=${body}` : `sms:?body=${body}`;
}

export function lessonSmsMessage(url: string, courseTitle = ""): string {
  const title = courseTitle.trim();
  if (title) {
    return `BabelBeam lesson (${title}): ${url}`;
  }
  return `BabelBeam lesson: ${url}`;
}
