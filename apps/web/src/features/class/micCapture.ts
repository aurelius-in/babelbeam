export type MicCapture = {
  stop: () => void;
};

export const SPEECH_RMS = 6;
export const SILENCE_MS = 900;
export const MAX_UTTERANCE_MS = 12000;

export type CaptureAction = "start" | "keep" | "finish";

export function nextCaptureAction(input: {
  recording: boolean;
  heardSpeech: boolean;
  rms: number;
  elapsedMs: number;
  silenceMs: number;
}): CaptureAction {
  if (!input.recording) {
    return input.rms >= SPEECH_RMS ? "start" : "keep";
  }
  if (input.elapsedMs >= MAX_UTTERANCE_MS) {
    return "finish";
  }
  if (input.rms >= SPEECH_RMS) {
    return "keep";
  }
  if (input.heardSpeech && input.silenceMs >= SILENCE_MS) {
    return "finish";
  }
  return "keep";
}

export async function startMicCapture(onUtterance: (blob: Blob, contentType: string) => void): Promise<MicCapture> {
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
    throw new Error("unsupported");
  }
  const contentType = recorderType();
  if (!contentType) {
    throw new Error("unsupported");
  }
  const context = new AudioContext();
  const resumed = context.resume();
  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
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
  const source = context.createMediaStreamSource(stream);
  const analyser = context.createAnalyser();
  analyser.fftSize = 2048;
  source.connect(analyser);
  // Chrome does not pull analyser samples unless the graph reaches the destination.
  const sink = context.createGain();
  sink.gain.value = 0;
  analyser.connect(sink);
  sink.connect(context.destination);
  const samples = new Uint8Array(analyser.fftSize);
  let recorder: MediaRecorder | null = null;
  let chunks: Blob[] = [];
  let heardSpeech = false;
  let silenceAt = 0;
  let startedAt = 0;
  let running = true;

  function release() {
    stream.getTracks().forEach((track) => track.stop());
    void context.close();
  }

  function begin(fromSpeech: boolean) {
    if (recorder && recorder.state === "recording") {
      return;
    }
    chunks = [];
    heardSpeech = fromSpeech;
    try {
      recorder = new MediaRecorder(stream, { mimeType: contentType });
    } catch {
      throw new Error("unsupported");
    }
    const active = recorder;
    active.ondataavailable = (event) => {
      if (event.data.size > 0) {
        chunks.push(event.data);
      }
    };
    active.onstop = () => {
      const blob = new Blob(chunks, { type: contentType });
      chunks = [];
      if (recorder === active) {
        recorder = null;
      }
      if (blob.size > 800) {
        onUtterance(blob, contentType);
      }
    };
    active.start();
    startedAt = performance.now();
    silenceAt = startedAt;
  }

  function finish() {
    if (recorder && recorder.state === "recording") {
      recorder.stop();
    }
  }

  try {
    // The tap is the decision to speak. Do not wait for a loud sample before recording.
    begin(false);
  } catch (error) {
    release();
    throw error;
  }

  const timer = window.setInterval(() => {
    if (!running) {
      return;
    }
    analyser.getByteTimeDomainData(samples);
    let sum = 0;
    for (const value of samples) {
      const centered = value - 128;
      sum += centered * centered;
    }
    const rms = Math.sqrt(sum / samples.length);
    const now = performance.now();
    if (rms >= SPEECH_RMS) {
      heardSpeech = true;
      silenceAt = now;
    }
    const recording = Boolean(recorder && recorder.state === "recording");
    const action = nextCaptureAction({
      recording,
      heardSpeech,
      rms,
      elapsedMs: recording ? now - startedAt : 0,
      silenceMs: recording ? now - silenceAt : 0,
    });
    if (action === "start") {
      try {
        begin(true);
      } catch {
        // Keep the microphone open. The recording already in progress still uploads on stop.
      }
    } else if (action === "finish") {
      finish();
    }
  }, 100);

  return {
    stop() {
      running = false;
      window.clearInterval(timer);
      const active = recorder;
      if (active && active.state === "recording") {
        active.addEventListener("stop", () => release(), { once: true });
        finish();
        return;
      }
      release();
    },
  };
}

function recorderType(): string {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  return candidates.find((item) => MediaRecorder.isTypeSupported(item)) ?? "";
}
