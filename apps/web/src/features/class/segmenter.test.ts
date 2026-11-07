import { describe, expect, it } from "vitest";
import {
  createSegmenter,
  frameRms,
  silenceLimitMs,
  TEACHER_SEGMENTER,
  type Segmenter,
  type Utterance,
} from "./segmenter";

const RATE = 48000;
const FRAME = 960;
const OPTIONS = { ...TEACHER_SEGMENTER, sampleRate: RATE };

let seed = 7;
function random(): number {
  seed = (seed * 1103515245 + 12345) % 2147483648;
  return seed / 2147483648;
}

function noise(level: number, count: number): Float32Array[] {
  const amplitude = level * Math.sqrt(3);
  return Array.from({ length: count }, () => {
    const frame = new Float32Array(FRAME);
    for (let index = 0; index < FRAME; index += 1) {
      frame[index] = (random() * 2 - 1) * amplitude;
    }
    return frame;
  });
}

/** A tone with a short dip every 200 ms, like the gap between syllables. */
function speech(level: number, count: number): Float32Array[] {
  return Array.from({ length: count }, (_unused, frameIndex) => {
    const frame = new Float32Array(FRAME);
    const scale = frameIndex % 10 >= 8 ? 0.1 : 1;
    for (let index = 0; index < FRAME; index += 1) {
      const time = (frameIndex * FRAME + index) / RATE;
      frame[index] = Math.sin(2 * Math.PI * 220 * time) * level * Math.SQRT2 * scale;
    }
    return frame;
  });
}

function run(frames: Float32Array[], during?: (segmenter: Segmenter, index: number) => void): Utterance[] {
  const found: Utterance[] = [];
  const segmenter = createSegmenter(OPTIONS, (utterance) => found.push(utterance));
  frames.forEach((frame, index) => {
    during?.(segmenter, index);
    segmenter.push(frame);
  });
  segmenter.flush();
  return found;
}

describe("teacher phrase segmenter", () => {
  it("keeps about 300 ms before the first loud frame so soft onsets survive", () => {
    const onset = noise(0.004, 4);
    const found = run([...noise(0.0005, 100), ...onset, ...speech(0.05, 75), ...noise(0.0005, 60)]);
    expect(found).toHaveLength(1);
    const spokenMs = (onset.length + 75) * 20;
    expect(found[0].durationMs).toBeGreaterThanOrEqual(spokenMs + 200);
    expect(found[0].durationMs).toBeLessThanOrEqual(spokenMs + 400 + 300 + 20);
    const first = found[0].samples.indexOf(onset[0][0]);
    expect(first).toBeGreaterThanOrEqual(10 * FRAME);
  });

  it("does not clip a teacher who starts talking right after the tap", () => {
    const words = speech(0.06, 50);
    const found = run([...words, ...noise(0.0005, 70)]);
    expect(found).toHaveLength(1);
    expect(found[0].samples.slice(0, FRAME)).toEqual(words[0]);
    expect(found[0].durationMs).toBeGreaterThanOrEqual(1000);
  });

  it("cuts long continuous speech at a quiet frame with no gap and no repeat", () => {
    const talk = speech(0.05, 1500);
    const found = run([...noise(0.0005, 100), ...talk, ...noise(0.0005, 60)]);
    expect(found.length).toBeGreaterThanOrEqual(3);
    for (const utterance of found.filter((item) => item.forced)) {
      expect(utterance.durationMs).toBeLessThanOrEqual(OPTIONS.maxUtteranceMs);
    }
    const total = found.reduce((sum, item) => sum + item.samples.length, 0);
    expect(total).toBeGreaterThanOrEqual(talk.length * FRAME);
    expect(total).toBeLessThanOrEqual((talk.length + 20 + 16) * FRAME);
    const joined = new Float32Array(total);
    let offset = 0;
    for (const utterance of found) {
      joined.set(utterance.samples, offset);
      offset += utterance.samples.length;
    }
    const start = joined.indexOf(talk[0][1]) - 1;
    expect(start).toBeGreaterThanOrEqual(0);
    const span = joined.slice(start, start + talk.length * FRAME);
    const intact = span.every((value, index) => value === talk[Math.floor(index / FRAME)][index % FRAME]);
    expect(intact).toBe(true);
  });

  it("hears soft speech in a quiet room that the old fixed loudness line missed", () => {
    const soft = 0.01;
    expect(soft * 128).toBeLessThan(6);
    const found = run([...noise(0.0003, 100), ...speech(soft, 100), ...noise(0.0003, 75)]);
    expect(found).toHaveLength(1);
    expect(found[0].voicedMs).toBeGreaterThanOrEqual(1500);
  });

  it("does not open a phrase for steady room noise", () => {
    expect(run(noise(0.02, 500))).toHaveLength(0);
  });

  it("does not upload a click or cough shorter than the minimum", () => {
    expect(run([...noise(0.0005, 100), ...speech(0.05, 6), ...noise(0.0005, 100)])).toHaveLength(0);
  });

  it("sends the open phrase and ignores the speaker while this device plays audio", () => {
    const found = run(
      [...noise(0.0005, 100), ...speech(0.05, 50), ...speech(0.2, 50), ...noise(0.0005, 50)],
      (segmenter, index) => {
        if (index === 150) {
          segmenter.setHold(true);
        }
        if (index === 200) {
          segmenter.setHold(false);
        }
      },
    );
    expect(found).toHaveLength(1);
    expect(found[0].durationMs).toBeLessThan(1500);
  });

  it("waits longer after a short phrase and less after a long one", () => {
    expect(silenceLimitMs(OPTIONS, 800)).toBe(800);
    expect(silenceLimitMs(OPTIONS, 3000)).toBe(600);
    expect(silenceLimitMs(OPTIONS, 7000)).toBe(350);
    expect(frameRms(new Float32Array([0.5, -0.5]))).toBeCloseTo(0.5);
  });
});
