import { describe, expect, it } from "vitest";
import {
  QUEUE_LIMITS,
  backlogMs,
  emptyQueue,
  estimateClipMs,
  expirePending,
  ingest,
  knownIds,
  markPlayed,
  markPlaying,
  nextStep,
  skipToLatest,
  type FeedSegment,
  type PlaybackQueue,
} from "./playbackQueue";

function clip(seconds: number): string {
  return "A".repeat(Math.round((seconds * QUEUE_LIMITS.mp3BytesPerSecond * 4) / 3));
}

function line(id: string, seq: number, seconds = 2, extra: Partial<FeedSegment> = {}): FeedSegment {
  return {
    id,
    seq,
    wait_for: [],
    spanish_text: `frase ${id}`,
    audio_state: "ready",
    audio_base64: clip(seconds),
    audio_content_type: "audio/mpeg",
    ...extra,
  };
}

function playAll(queue: PlaybackQueue, now: number): string[] {
  const played: string[] = [];
  let state = queue;
  for (let guard = 0; guard < 50; guard += 1) {
    const step = nextStep(state, now);
    if (step.kind !== "play") {
      break;
    }
    played.push(step.line.id);
    state = markPlayed(markPlaying(state, step.line.id), step.line.id);
  }
  return played;
}

describe("listener playback queue", () => {
  it("plays both clips when two lines arrive in one poll", () => {
    const queue = ingest(emptyQueue(), [line("a", 1), line("b", 2)], 0);
    expect(playAll(queue, 0)).toEqual(["a", "b"]);
  });

  it("never interrupts a clip that is playing", () => {
    let queue = ingest(emptyQueue(), [line("a", 1)], 0);
    queue = markPlaying(queue, "a");
    queue = ingest(queue, [line("b", 2)], 500);
    expect(nextStep(queue, 500).kind).toBe("busy");
    queue = markPlayed(queue, "a");
    const step = nextStep(queue, 2500);
    expect(step.kind === "play" && step.line.id).toBe("b");
  });

  it("holds a later line briefly for an earlier line still being translated", () => {
    let queue = ingest(emptyQueue(), [line("second", 2, 2, { wait_for: [1] })], 1000);
    expect(nextStep(queue, 1500).kind).toBe("wait");
    queue = ingest(queue, [line("first", 1, 2, { audio_state: "pending", audio_base64: undefined })], 1600);
    expect(queue.lines.map((item) => item.id)).toEqual(["first", "second"]);
    expect(nextStep(queue, 1700).kind).toBe("wait");
    queue = ingest(queue, [line("first", 1)], 2500);
    expect(playAll(queue, 2500)).toEqual(["first", "second"]);
  });

  it("plays the later line when the earlier one never arrives", () => {
    const queue = ingest(emptyQueue(), [line("second", 2, 2, { wait_for: [1] })], 0);
    expect(nextStep(queue, QUEUE_LIMITS.holdMs - 1).kind).toBe("wait");
    const step = nextStep(queue, QUEUE_LIMITS.holdMs);
    expect(step.kind === "play" && step.line.id).toBe("second");
  });

  it("shows the caption before its audio and plays the audio once it arrives", () => {
    let queue = ingest(emptyQueue(), [line("a", 1, 2, { audio_state: "pending", audio_base64: undefined })], 0);
    expect(queue.lines[0].text).toBe("frase a");
    expect(knownIds(queue)).toEqual([]);
    queue = ingest(queue, [line("a", 1)], 1500);
    expect(knownIds(queue)).toEqual(["a"]);
    expect(playAll(queue, 1500)).toEqual(["a"]);
  });

  it("keeps polling when a ready line arrives without audio yet", () => {
    let queue = ingest(
      emptyQueue(),
      [line("a", 1, 2, { audio_state: "ready", audio_base64: undefined, audio_content_type: undefined })],
      0,
    );
    expect(queue.lines[0].audio).toBe("pending");
    expect(knownIds(queue)).toEqual([]);
    queue = ingest(queue, [line("a", 1)], 800);
    expect(queue.lines[0].audio).toBe("ready");
    expect(playAll(queue, 800)).toEqual(["a"]);
  });

  it("keeps every caption but stops queueing audio past the backlog limit", () => {
    const many = Array.from({ length: 12 }, (_unused, index) => line(`l${index}`, index + 1, 4));
    let queue = ingest(emptyQueue(), many, 0);
    expect(queue.lines).toHaveLength(12);
    expect(backlogMs(queue)).toBeLessThanOrEqual(QUEUE_LIMITS.maxBacklogMs);
    expect(queue.behind).toBe(true);
    expect(queue.skipped).toBeGreaterThan(0);
    const played = playAll(queue, 0);
    expect(played.length + queue.skipped).toBe(12);
    for (const id of played) {
      queue = markPlayed(markPlaying(queue, id), id);
    }
    expect(queue.behind).toBe(false);
    queue = ingest(queue, [line("fresh", 13, 3)], 60000);
    expect(playAll(queue, 60000)).toEqual(["fresh"]);
  });

  it("never plays history from before the listener joined", () => {
    const queue = ingest(emptyQueue(), [line("old", 1)], 0, true);
    expect(queue.lines[0].text).toBe("frase old");
    expect(nextStep(queue, 0).kind).toBe("idle");
    expect(knownIds(queue)).toEqual(["old"]);
  });

  it("skips to the newest ready line on request and gives up on audio that never comes", () => {
    let queue = ingest(emptyQueue(), [line("a", 1), line("b", 2), line("c", 3)], 0);
    queue = skipToLatest(queue);
    expect(playAll(queue, 0)).toEqual(["c"]);
    let waiting = ingest(emptyQueue(), [line("x", 1, 2, { audio_state: "pending", audio_base64: undefined })], 0);
    waiting = expirePending(waiting, QUEUE_LIMITS.pendingAudioMs);
    expect(waiting.lines[0].audio).toBe("none");
    expect(estimateClipMs(clip(5).length)).toBeCloseTo(5000, -2);
  });
});
