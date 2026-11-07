import { createSegmenter, TEACHER_SEGMENTER, type SegmenterOptions } from "./segmenter";
import { encodeWav16, resample, UPLOAD_SAMPLE_RATE } from "./wav";

export type CapturedUtterance = {
  blob: Blob;
  contentType: string;
  durationMs: number;
  voicedMs: number;
  forced: boolean;
  bytes: number;
};

export type TeacherCapture = {
  stop: () => void;
  setHold: (held: boolean) => void;
  /** False when the OS ended tracks or suspended audio after lock/background. */
  isAlive: () => boolean;
};

const WORKLET_URL = "/worklets/pcm-tap.js";

/**
 * Continuous teacher capture. The microphone stays open between phrases, so no audio is
 * lost while a recorder restarts, and each phrase keeps a short pre-roll before its first
 * loud frame. Each phrase uploads as 16 kHz mono WAV.
 */
export async function startTeacherCapture(
  onUtterance: (utterance: CapturedUtterance) => void,
  tuning: Partial<Omit<SegmenterOptions, "sampleRate">> = {},
): Promise<TeacherCapture> {
  const AudioContextClass =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!navigator.mediaDevices?.getUserMedia || !AudioContextClass) {
    throw new Error("unsupported");
  }
  // Created inside the tap so iPhone Safari lets the context run.
  const context = new AudioContextClass();
  const resumed = context.resume();
  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,
      },
    });
    await resumed;
    if (context.state === "suspended") {
      await context.resume();
    }
  } catch (error) {
    void context.close();
    throw error;
  }
  const sampleRate = context.sampleRate;
  const frameLength = Math.round((sampleRate * TEACHER_SEGMENTER.frameMs) / 1000);
  const segmenter = createSegmenter({ ...TEACHER_SEGMENTER, ...tuning, sampleRate }, (utterance) => {
    const wav = encodeWav16(
      resample(utterance.samples, utterance.sampleRate, UPLOAD_SAMPLE_RATE),
      UPLOAD_SAMPLE_RATE,
    );
    onUtterance({
      blob: new Blob([wav], { type: "audio/wav" }),
      contentType: "audio/wav",
      durationMs: utterance.durationMs,
      voicedMs: utterance.voicedMs,
      forced: utterance.forced,
      bytes: wav.length,
    });
  });
  let frame = new Float32Array(frameLength);
  let filled = 0;
  function accept(samples: Float32Array) {
    let offset = 0;
    while (offset < samples.length) {
      const take = Math.min(samples.length - offset, frameLength - filled);
      frame.set(samples.subarray(offset, offset + take), filled);
      filled += take;
      offset += take;
      if (filled === frameLength) {
        segmenter.push(frame);
        frame = new Float32Array(frameLength);
        filled = 0;
      }
    }
  }
  const source = context.createMediaStreamSource(stream);
  // Browsers only pull a processing node whose output reaches the destination.
  const sink = context.createGain();
  sink.gain.value = 0;
  sink.connect(context.destination);
  let tap: AudioNode;
  try {
    tap = await workletTap(context, accept);
  } catch {
    tap = scriptTap(context, accept);
  }
  source.connect(tap);
  tap.connect(sink);
  let stopped = false;
  return {
    stop() {
      if (stopped) {
        return;
      }
      stopped = true;
      segmenter.flush();
      source.disconnect();
      tap.disconnect();
      sink.disconnect();
      stream.getTracks().forEach((track) => track.stop());
      void context.close();
    },
    setHold(held) {
      segmenter.setHold(held);
    },
    isAlive() {
      if (stopped) {
        return false;
      }
      if (context.state === "closed") {
        return false;
      }
      const tracks = stream.getAudioTracks();
      if (tracks.length === 0) {
        return false;
      }
      return tracks.every((track) => track.readyState === "live");
    },
  };
}

async function workletTap(
  context: AudioContext,
  accept: (samples: Float32Array) => void,
): Promise<AudioNode> {
  if (!context.audioWorklet || typeof AudioWorkletNode === "undefined") {
    throw new Error("no worklet");
  }
  await context.audioWorklet.addModule(WORKLET_URL);
  const node = new AudioWorkletNode(context, "pcm-tap", {
    numberOfInputs: 1,
    numberOfOutputs: 1,
    outputChannelCount: [1],
  });
  node.port.onmessage = (event: MessageEvent<Float32Array>) => accept(event.data);
  return node;
}

function scriptTap(context: AudioContext, accept: (samples: Float32Array) => void): AudioNode {
  const node = context.createScriptProcessor(2048, 1, 1);
  node.onaudioprocess = (event) => accept(new Float32Array(event.inputBuffer.getChannelData(0)));
  return node;
}
