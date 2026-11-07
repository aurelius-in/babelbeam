/**
 * Splits continuous microphone frames into utterances. Pure logic, no browser APIs.
 *
 * Audio is never dropped between utterances: a forced cut at the length limit carries
 * the remaining frames into the next utterance, and a short pre-roll before the first
 * loud frame keeps soft word onsets.
 */
export type SegmenterOptions = {
  sampleRate: number;
  frameMs: number;
  preRollMs: number;
  startFrames: number;
  startWindowFrames: number;
  minVoicedMs: number;
  shortUtteranceMs: number;
  shortSilenceMs: number;
  endSilenceMs: number;
  longUtteranceMs: number;
  longSilenceMs: number;
  maxUtteranceMs: number;
  cutSearchMs: number;
  keepTailMs: number;
  startupMs: number;
  floorWindowMs: number;
  initialFloor: number;
  minThreshold: number;
  maxThreshold: number;
  thresholdRatio: number;
};

export const TEACHER_SEGMENTER: Omit<SegmenterOptions, "sampleRate"> = {
  frameMs: 20,
  preRollMs: 300,
  startFrames: 3,
  startWindowFrames: 5,
  minVoicedMs: 240,
  shortUtteranceMs: 1500,
  shortSilenceMs: 800,
  endSilenceMs: 600,
  longUtteranceMs: 6000,
  longSilenceMs: 350,
  maxUtteranceMs: 12000,
  cutSearchMs: 1500,
  keepTailMs: 300,
  startupMs: 1500,
  floorWindowMs: 5000,
  initialFloor: 0.0015,
  minThreshold: 0.006,
  maxThreshold: 0.05,
  thresholdRatio: 4,
};

export type Utterance = {
  samples: Float32Array;
  sampleRate: number;
  durationMs: number;
  voicedMs: number;
  forced: boolean;
};

export type Segmenter = {
  push: (frame: Float32Array) => void;
  setHold: (held: boolean) => void;
  flush: () => void;
  threshold: () => number;
  speaking: () => boolean;
};

export function frameRms(frame: Float32Array): number {
  if (frame.length === 0) {
    return 0;
  }
  let sum = 0;
  for (const value of frame) {
    sum += value * value;
  }
  return Math.sqrt(sum / frame.length);
}

export function silenceLimitMs(options: SegmenterOptions, spokenMs: number): number {
  if (spokenMs < options.shortUtteranceMs) {
    return options.shortSilenceMs;
  }
  if (spokenMs >= options.longUtteranceMs) {
    return options.longSilenceMs;
  }
  return options.endSilenceMs;
}

export function createSegmenter(
  options: SegmenterOptions,
  emit: (utterance: Utterance) => void,
): Segmenter {
  const frames = (ms: number) => Math.max(1, Math.round(ms / options.frameMs));
  const preRollFrames = frames(options.preRollMs);
  const startupFrames = frames(options.startupMs);
  const floorFrames = frames(options.floorWindowMs);
  const keepTailFrames = frames(options.keepTailMs);
  const cutSearchFrames = frames(options.cutSearchMs);
  const maxFrames = frames(options.maxUtteranceMs);
  let floorLevels: number[] = [];
  let pre: Float32Array[] = [];
  let preLevels: number[] = [];
  let observed = 0;
  let open = false;
  let current: Float32Array[] = [];
  let levels: number[] = [];
  let voiced: boolean[] = [];
  let silenceRun = 0;
  let held = false;

  function floor(): number {
    if (floorLevels.length < options.startWindowFrames) {
      return options.initialFloor;
    }
    let lowest = Number.POSITIVE_INFINITY;
    for (const level of floorLevels) {
      lowest = Math.min(lowest, level);
    }
    return Math.max(lowest, 0.0002);
  }

  function threshold(): number {
    return Math.min(options.maxThreshold, Math.max(options.minThreshold, floor() * options.thresholdRatio));
  }

  function emitFrames(chunk: Float32Array[], chunkVoiced: boolean[], forced: boolean) {
    const voicedMs = chunkVoiced.filter(Boolean).length * options.frameMs;
    if (chunk.length === 0 || voicedMs < options.minVoicedMs) {
      return;
    }
    const total = chunk.reduce((sum, frame) => sum + frame.length, 0);
    const samples = new Float32Array(total);
    let offset = 0;
    for (const frame of chunk) {
      samples.set(frame, offset);
      offset += frame.length;
    }
    emit({
      samples,
      sampleRate: options.sampleRate,
      durationMs: chunk.length * options.frameMs,
      voicedMs,
      forced,
    });
  }

  function close(keepAllTail: boolean) {
    const tail = keepAllTail ? 0 : Math.max(0, silenceRun - keepTailFrames);
    const end = current.length - tail;
    emitFrames(current.slice(0, end), voiced.slice(0, end), false);
    pre = current.slice(end).slice(-preRollFrames);
    preLevels = levels.slice(end).slice(-preRollFrames);
    open = false;
    current = [];
    levels = [];
    voiced = [];
    silenceRun = 0;
  }

  function cutAtQuietestFrame() {
    const from = Math.max(1, current.length - cutSearchFrames);
    let cut = current.length - 1;
    for (let index = from; index < current.length; index += 1) {
      if (levels[index] < levels[cut]) {
        cut = index;
      }
    }
    emitFrames(current.slice(0, cut + 1), voiced.slice(0, cut + 1), true);
    current = current.slice(cut + 1);
    levels = levels.slice(cut + 1);
    voiced = voiced.slice(cut + 1);
    silenceRun = 0;
    for (let index = voiced.length - 1; index >= 0 && !voiced[index]; index -= 1) {
      silenceRun += 1;
    }
  }

  return {
    push(frame) {
      if (held) {
        return;
      }
      const level = frameRms(frame);
      floorLevels.push(level);
      if (floorLevels.length > floorFrames) {
        floorLevels = floorLevels.slice(-floorFrames);
      }
      observed += 1;
      const limit = threshold();
      const loud = level >= limit;
      if (!open) {
        pre.push(frame);
        preLevels.push(level);
        // Right after the tap, keep everything so a teacher who speaks at once is not clipped.
        const keep = observed <= startupFrames ? startupFrames : preRollFrames + options.startWindowFrames;
        if (pre.length > keep) {
          pre = pre.slice(-keep);
          preLevels = preLevels.slice(-keep);
        }
        if (observed < options.startWindowFrames) {
          return;
        }
        const window = preLevels.slice(-options.startWindowFrames);
        if (window.filter((value) => value >= limit).length >= options.startFrames) {
          open = true;
          current = pre;
          levels = preLevels;
          voiced = preLevels.map((value) => value >= limit);
          pre = [];
          preLevels = [];
          silenceRun = 0;
          for (let index = voiced.length - 1; index >= 0 && !voiced[index]; index -= 1) {
            silenceRun += 1;
          }
        }
        return;
      }
      current.push(frame);
      levels.push(level);
      voiced.push(loud);
      silenceRun = loud ? 0 : silenceRun + 1;
      const spokenMs = (current.length - silenceRun) * options.frameMs;
      if (silenceRun * options.frameMs >= silenceLimitMs(options, spokenMs)) {
        close(false);
      } else if (current.length >= maxFrames) {
        cutAtQuietestFrame();
      }
    },
    setHold(next) {
      if (next === held) {
        return;
      }
      if (next && open) {
        close(true);
      }
      held = next;
      pre = [];
      preLevels = [];
      observed = 0;
    },
    flush() {
      if (open) {
        close(false);
      }
    },
    threshold,
    speaking: () => open,
  };
}
