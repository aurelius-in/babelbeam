/**
 * Ordered listener playback for class lines. Pure state, no browser APIs.
 *
 * Every caption is kept. Audio plays one clip at a time in the teacher's order and never
 * interrupts a clip that is playing. When queued audio would exceed the backlog limit,
 * new clips are shown as captions only and the listener is told audio fell behind.
 */
export type FeedSegment = {
  id: string;
  seq?: number | null;
  wait_for?: number[];
  spanish_text: string;
  audio_state?: string;
  audio_base64?: string;
  audio_content_type?: string;
};

export type LineAudio = "pending" | "ready" | "playing" | "played" | "none" | "skipped" | "history";

export type QueueLine = {
  id: string;
  order: number;
  seq: number | null;
  waitFor: number[];
  text: string;
  arrivedAt: number;
  readyAt: number | null;
  audio: LineAudio;
  clip: { base64: string; contentType: string; estimatedMs: number } | null;
};

export type PlaybackQueue = {
  lines: QueueLine[];
  nextOrder: number;
  behind: boolean;
  skipped: number;
};

export const QUEUE_LIMITS = {
  holdMs: 3000,
  pendingAudioMs: 20000,
  warnBacklogMs: 8000,
  maxBacklogMs: 20000,
  maxLines: 80,
  mp3BytesPerSecond: 16000,
};

export function emptyQueue(): PlaybackQueue {
  return { lines: [], nextOrder: 1, behind: false, skipped: 0 };
}

export function estimateClipMs(base64Length: number, bytesPerSecond = QUEUE_LIMITS.mp3BytesPerSecond): number {
  return Math.round(((base64Length * 3) / 4 / bytesPerSecond) * 1000);
}

/** Merge one feed response. History lines (first poll after joining) never play audio. */
export function ingest(
  queue: PlaybackQueue,
  segments: FeedSegment[],
  now: number,
  history = false,
): PlaybackQueue {
  if (segments.length === 0) {
    return queue;
  }
  let lines = queue.lines.slice();
  let nextOrder = queue.nextOrder;
  let behind = queue.behind;
  let skipped = queue.skipped;
  for (const segment of segments) {
    const index = lines.findIndex((line) => line.id === segment.id);
    const seq = typeof segment.seq === "number" && segment.seq > 0 ? segment.seq : null;
    const existing = index >= 0 ? lines[index] : null;
    let line: QueueLine = existing ?? {
      id: segment.id,
      order: seq ?? nextOrder,
      seq,
      waitFor: Array.isArray(segment.wait_for) ? segment.wait_for.filter((value) => value > 0) : [],
      text: segment.spanish_text,
      arrivedAt: now,
      readyAt: null,
      audio: history ? "history" : "pending",
      clip: null,
    };
    if (!existing) {
      nextOrder = Math.max(nextOrder, line.order) + 1;
    }
    line = { ...line, text: segment.spanish_text || line.text };
    if (line.audio === "pending") {
      const state = segment.audio_state ?? (segment.audio_base64 ? "ready" : "none");
      if (state === "ready" && segment.audio_base64 && segment.audio_content_type) {
        const clip = {
          base64: segment.audio_base64,
          contentType: segment.audio_content_type,
          estimatedMs: estimateClipMs(segment.audio_base64.length),
        };
        const queued = backlogMs({ lines, nextOrder, behind, skipped });
        if (queued === 0) {
          behind = false;
        }
        if (behind || queued + clip.estimatedMs > QUEUE_LIMITS.maxBacklogMs) {
          behind = true;
          skipped += 1;
          line = { ...line, audio: "skipped", readyAt: now };
        } else {
          line = { ...line, audio: "ready", readyAt: now, clip };
        }
      } else if (state === "ready" && !segment.audio_base64) {
        // Keep polling. The chosen voice may still be missing while another clip exists
        // on a later feed response after a join race.
      } else if (state !== "pending") {
        line = { ...line, audio: "none", readyAt: now };
      }
    }
    if (existing) {
      lines[index] = line;
    } else {
      lines.push(line);
    }
  }
  lines.sort((left, right) => left.order - right.order);
  if (lines.length > QUEUE_LIMITS.maxLines) {
    lines = lines.slice(-QUEUE_LIMITS.maxLines);
  }
  return { lines, nextOrder, behind, skipped };
}

/** Queued audio not yet played, including the clip that is playing now. */
export function backlogMs(queue: PlaybackQueue): number {
  return queue.lines.reduce(
    (sum, line) => sum + (line.clip && (line.audio === "ready" || line.audio === "playing") ? line.clip.estimatedMs : 0),
    0,
  );
}

export type NextStep =
  | { kind: "play"; line: QueueLine }
  | { kind: "busy" }
  | { kind: "wait"; untilMs: number }
  | { kind: "idle" };

/** Decide what the single audio player should do now. Pure apart from the clock value. */
export function nextStep(queue: PlaybackQueue, now: number): NextStep {
  if (queue.lines.some((line) => line.audio === "playing")) {
    return { kind: "busy" };
  }
  for (const line of queue.lines) {
    if (line.audio === "pending") {
      const giveUpAt = line.arrivedAt + QUEUE_LIMITS.pendingAudioMs;
      if (now < giveUpAt) {
        return { kind: "wait", untilMs: giveUpAt };
      }
      continue;
    }
    if (line.audio !== "ready") {
      continue;
    }
    const missing = line.waitFor.some((seq) => !queue.lines.some((other) => other.seq === seq));
    const holdUntil = (line.readyAt ?? line.arrivedAt) + QUEUE_LIMITS.holdMs;
    if (missing && now < holdUntil) {
      return { kind: "wait", untilMs: holdUntil };
    }
    return { kind: "play", line };
  }
  return { kind: "idle" };
}

/** Lines still waiting for audio past the limit are shown as captions only. */
export function expirePending(queue: PlaybackQueue, now: number): PlaybackQueue {
  const stale = queue.lines.some(
    (line) => line.audio === "pending" && now >= line.arrivedAt + QUEUE_LIMITS.pendingAudioMs,
  );
  if (!stale) {
    return queue;
  }
  return {
    ...queue,
    lines: queue.lines.map((line) =>
      line.audio === "pending" && now >= line.arrivedAt + QUEUE_LIMITS.pendingAudioMs
        ? { ...line, audio: "none" }
        : line,
    ),
  };
}

export function markPlaying(queue: PlaybackQueue, id: string): PlaybackQueue {
  return setAudio(queue, id, "playing");
}

/** The clip ended or failed. Leaving the backlog clears the fell-behind notice. */
export function markPlayed(queue: PlaybackQueue, id: string): PlaybackQueue {
  const next = setAudio(queue, id, "played");
  const drained = !next.lines.some((line) => line.audio === "ready" || line.audio === "playing");
  return drained && next.behind ? { ...next, behind: false } : next;
}

/** Drop queued older clips and keep only the newest ready one. Captions stay. */
export function skipToLatest(queue: PlaybackQueue): PlaybackQueue {
  const ready = queue.lines.filter((line) => line.audio === "ready");
  const keep = ready.length > 0 ? ready[ready.length - 1].id : "";
  let skipped = queue.skipped;
  const lines = queue.lines.map((line) => {
    if (line.audio === "ready" && line.id !== keep) {
      skipped += 1;
      return { ...line, audio: "skipped" as const, clip: null };
    }
    return line;
  });
  return { ...queue, lines, skipped, behind: false };
}

/** Lines this listener needs nothing more for, newest last. The server window is 30 lines. */
export function knownIds(queue: PlaybackQueue, limit = 40): string[] {
  return queue.lines
    .filter((line) => line.audio !== "pending")
    .map((line) => line.id)
    .slice(-limit);
}

function setAudio(queue: PlaybackQueue, id: string, audio: LineAudio): PlaybackQueue {
  return {
    ...queue,
    lines: queue.lines.map((line) =>
      line.id === id ? { ...line, audio, clip: audio === "played" ? null : line.clip } : line,
    ),
  };
}
