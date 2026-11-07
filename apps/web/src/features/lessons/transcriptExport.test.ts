import { describe, expect, it } from "vitest";
import { transcriptFilename, transcriptJson, transcriptPlainText } from "./transcriptExport";

const sample = {
  id: "abc",
  course_title: "Baptism Week 1",
  created_at: 1_700_000_000,
  ended_at: 1_700_003_600,
  segments: [
    {
      id: "s1",
      t: 1_700_000_100,
      recognized_english: "Today we talk about baptism.",
      delivered_spanish: "Hoy hablamos del bautismo.",
      status: "delivered",
    },
  ],
  gaps: [{ reason: "network" }],
};

describe("transcriptExport", () => {
  it("builds a plain-text transcript with EN and ES lines", () => {
    const text = transcriptPlainText(sample);
    expect(text).toContain("Baptism Week 1");
    expect(text).toContain("EN: Today we talk about baptism.");
    expect(text).toContain("ES: Hoy hablamos del bautismo.");
    expect(text).toContain("Flagged gaps: 1");
  });

  it("builds JSON with separate english and spanish fields", () => {
    const parsed = JSON.parse(transcriptJson(sample)) as {
      segments: { recognized_english: string; delivered_spanish: string }[];
    };
    expect(parsed.segments[0].recognized_english).toBe("Today we talk about baptism.");
    expect(parsed.segments[0].delivered_spanish).toBe("Hoy hablamos del bautismo.");
  });

  it("makes a safe download filename", () => {
    expect(transcriptFilename(sample, "txt")).toBe("babelbeam-baptism-week-1.txt");
  });
});
