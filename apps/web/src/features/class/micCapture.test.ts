import { describe, expect, it } from "vitest";
import { MAX_UTTERANCE_MS, SILENCE_MS, nextCaptureAction } from "./micCapture";

describe("microphone utterance capture", () => {
  it("keeps recording when the phone stays under the loudness line", () => {
    expect(
      nextCaptureAction({
        recording: true,
        heardSpeech: false,
        rms: 0,
        elapsedMs: 5_000,
        silenceMs: 5_000,
      }),
    ).toBe("keep");
  });

  it("finishes at the time limit so a quiet take is still uploaded", () => {
    expect(
      nextCaptureAction({
        recording: true,
        heardSpeech: false,
        rms: 0,
        elapsedMs: MAX_UTTERANCE_MS,
        silenceMs: MAX_UTTERANCE_MS,
      }),
    ).toBe("finish");
  });

  it("finishes after detected speech goes quiet", () => {
    expect(
      nextCaptureAction({
        recording: true,
        heardSpeech: true,
        rms: 0,
        elapsedMs: 3_000,
        silenceMs: SILENCE_MS,
      }),
    ).toBe("finish");
  });

  it("starts another take when speech returns after the microphone is already open", () => {
    expect(
      nextCaptureAction({
        recording: false,
        heardSpeech: false,
        rms: 20,
        elapsedMs: 0,
        silenceMs: 0,
      }),
    ).toBe("start");
  });
});
