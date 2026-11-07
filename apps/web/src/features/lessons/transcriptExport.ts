/** Build downloadable transcript files from a durable lesson payload. */

export type TranscriptSegment = {
  id?: string;
  t?: number;
  recognized_english?: string;
  delivered_spanish?: string;
  status?: string;
};

export type TranscriptLesson = {
  id?: string;
  course_title?: string;
  created_at?: number;
  ended_at?: number | null;
  segments?: TranscriptSegment[];
  gaps?: { reason?: string }[];
};

function stamp(seconds?: number | null): string {
  if (!seconds || !Number.isFinite(seconds)) {
    return "";
  }
  try {
    return new Date(seconds * 1000).toISOString();
  } catch {
    return "";
  }
}

export function transcriptPlainText(lesson: TranscriptLesson): string {
  const title = (lesson.course_title || "BabelBeam lesson").trim() || "BabelBeam lesson";
  const lines: string[] = [
    title,
    `Lesson id: ${lesson.id || ""}`,
    `Started: ${stamp(lesson.created_at)}`,
    `Ended: ${stamp(lesson.ended_at ?? null)}`,
    "",
    "Recognized English and delivered Spanish are listed separately.",
    "Audio is not included.",
    "",
  ];
  const segments = lesson.segments || [];
  if (segments.length === 0) {
    lines.push("(No transcript segments.)");
  }
  segments.forEach((item, index) => {
    lines.push(`--- ${index + 1} (${stamp(item.t) || item.id || "segment"}) ---`);
    lines.push(`EN: ${(item.recognized_english || "").trim()}`);
    lines.push(`ES: ${(item.delivered_spanish || "").trim()}`);
    if (item.status) {
      lines.push(`Status: ${item.status}`);
    }
    lines.push("");
  });
  const gaps = lesson.gaps || [];
  if (gaps.length > 0) {
    lines.push(`Flagged gaps: ${gaps.length}`);
    gaps.forEach((gap, index) => {
      lines.push(`  ${index + 1}. ${gap.reason || "gap"}`);
    });
  }
  return `${lines.join("\n").trim()}\n`;
}

export function transcriptJson(lesson: TranscriptLesson): string {
  return `${JSON.stringify(
    {
      id: lesson.id || "",
      course_title: lesson.course_title || "",
      created_at: lesson.created_at ?? null,
      ended_at: lesson.ended_at ?? null,
      segments: (lesson.segments || []).map((item) => ({
        id: item.id || "",
        t: item.t ?? null,
        recognized_english: item.recognized_english || "",
        delivered_spanish: item.delivered_spanish || "",
        status: item.status || "",
      })),
      gaps: lesson.gaps || [],
    },
    null,
    2,
  )}\n`;
}

export function downloadTextFile(filename: string, contents: string, mime = "text/plain"): void {
  const blob = new Blob([contents], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function transcriptFilename(lesson: TranscriptLesson, ext: "txt" | "json"): string {
  const raw = (lesson.course_title || lesson.id || "lesson").toLowerCase();
  const slug = raw
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
  return `babelbeam-${slug || "lesson"}.${ext}`;
}
