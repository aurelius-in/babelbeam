export const UPLOAD_SAMPLE_RATE = 16000;

/** Box-filter resampler. Each output sample averages the input window it covers. */
export function resample(samples: Float32Array, inputRate: number, outputRate: number): Float32Array {
  if (inputRate === outputRate || samples.length === 0) {
    return samples.slice();
  }
  const ratio = inputRate / outputRate;
  const length = Math.max(1, Math.floor(samples.length / ratio));
  const output = new Float32Array(length);
  for (let index = 0; index < length; index += 1) {
    const start = Math.floor(index * ratio);
    const end = Math.min(samples.length, Math.max(start + 1, Math.floor((index + 1) * ratio)));
    let sum = 0;
    for (let cursor = start; cursor < end; cursor += 1) {
      sum += samples[cursor];
    }
    output[index] = sum / (end - start);
  }
  return output;
}

/** Mono 16-bit PCM WAV. Samples outside -1..1 are clipped. */
export function encodeWav16(samples: Float32Array, sampleRate: number): Uint8Array<ArrayBuffer> {
  const dataBytes = samples.length * 2;
  const bytes = new Uint8Array(new ArrayBuffer(44 + dataBytes));
  const view = new DataView(bytes.buffer);
  writeAscii(bytes, 0, "RIFF");
  view.setUint32(4, 36 + dataBytes, true);
  writeAscii(bytes, 8, "WAVE");
  writeAscii(bytes, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(bytes, 36, "data");
  view.setUint32(40, dataBytes, true);
  for (let index = 0; index < samples.length; index += 1) {
    const clipped = Math.max(-1, Math.min(1, samples[index]));
    view.setInt16(44 + index * 2, clipped < 0 ? clipped * 0x8000 : clipped * 0x7fff, true);
  }
  return bytes;
}

/** A short silent clip used to unlock audio playback inside a tap on iPhone Safari. */
export function silentWavDataUrl(durationMs = 120, sampleRate = 8000): string {
  const wav = encodeWav16(new Float32Array(Math.round((sampleRate * durationMs) / 1000)), sampleRate);
  let binary = "";
  for (const byte of wav) {
    binary += String.fromCharCode(byte);
  }
  return `data:audio/wav;base64,${btoa(binary)}`;
}

function writeAscii(bytes: Uint8Array, offset: number, text: string) {
  for (let index = 0; index < text.length; index += 1) {
    bytes[offset + index] = text.charCodeAt(index);
  }
}
