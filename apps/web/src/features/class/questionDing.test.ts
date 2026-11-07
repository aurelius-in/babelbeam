import { afterEach, describe, expect, it } from "vitest";
import {
  playQuestionDing,
  readQuestionSoundPref,
  storeQuestionSoundPref,
} from "./questionDing";

afterEach(() => {
  storeQuestionSoundPref(true);
});

describe("question ding", () => {
  it("does not throw when AudioContext is missing", () => {
    expect(() => playQuestionDing()).not.toThrow();
  });

  it("respects the mute preference and muted option", () => {
    expect(readQuestionSoundPref()).toBe(true);
    storeQuestionSoundPref(false);
    expect(readQuestionSoundPref()).toBe(false);
    expect(() => playQuestionDing()).not.toThrow();
    expect(() => playQuestionDing({ muted: true })).not.toThrow();
  });
});
