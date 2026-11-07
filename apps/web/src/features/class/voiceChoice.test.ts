import { describe, expect, it } from "vitest";
import { DEFAULT_VOICE, STUDENT_VOICES, parseVoice, previewUrl, voiceLabelKey } from "./voiceChoice";

describe("student voice choice", () => {
  it("accepts only the four persona ids", () => {
    expect(STUDENT_VOICES).toEqual(["felipe", "roberta", "mateo", "valeria"]);
    expect(parseVoice("felipe")).toBe("felipe");
    expect(parseVoice("VALERIA")).toBe("valeria");
    expect(parseVoice("marin")).toBe(DEFAULT_VOICE);
    expect(parseVoice("")).toBe("valeria");
  });

  it("serves a static preview path so a tap costs nothing", () => {
    expect(previewUrl("mateo")).toBe("/voices/mateo.mp3");
    expect(voiceLabelKey("roberta")).toBe("voiceRoberta");
  });
});
