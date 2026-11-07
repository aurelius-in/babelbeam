import { describe, expect, it } from "vitest";
import { createLineOrder, createUploadGate, lineHeaders } from "./lineOrder";
import { encodeWav16, resample } from "./wav";

describe("teacher line order", () => {
  it("numbers lines and lists the earlier lines still in flight", () => {
    const order = createLineOrder();
    const first = order.begin();
    const second = order.begin();
    expect(first).toEqual({ seq: 1, waitFor: [] });
    expect(second).toEqual({ seq: 2, waitFor: [1] });
    order.end(1);
    expect(order.begin()).toEqual({ seq: 3, waitFor: [2] });
    expect(lineHeaders({ seq: 3, waitFor: [2] })).toEqual({ "X-Line-Seq": "3", "X-Line-Wait": "2" });
    expect(lineHeaders({ seq: 1, waitFor: [] })).toEqual({ "X-Line-Seq": "1" });
    order.reset();
    expect(order.begin().seq).toBe(1);
  });

  it("runs at most the limit of uploads at once, first in first out", async () => {
    const gate = createUploadGate(2);
    let active = 0;
    let peak = 0;
    const started: number[] = [];
    const releases: Array<() => void> = [];
    const tasks = [1, 2, 3, 4].map((id) =>
      gate.run(async () => {
        started.push(id);
        active += 1;
        peak = Math.max(peak, active);
        await new Promise<void>((resolve) => releases.push(resolve));
        active -= 1;
        return id;
      }),
    );
    await Promise.resolve();
    expect(started).toEqual([1, 2]);
    releases.shift()?.();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(started).toEqual([1, 2, 3]);
    while (releases.length > 0 || started.length < 4) {
      releases.shift()?.();
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
    expect(await Promise.all(tasks)).toEqual([1, 2, 3, 4]);
    expect(peak).toBe(2);
  });
});

describe("WAV upload encoding", () => {
  it("writes a 16 kHz mono PCM header and clipped samples", () => {
    const wav = encodeWav16(new Float32Array([0, 1, -1, 2]), 16000);
    const view = new DataView(wav.buffer);
    expect(String.fromCharCode(...wav.slice(0, 4))).toBe("RIFF");
    expect(String.fromCharCode(...wav.slice(8, 12))).toBe("WAVE");
    expect(view.getUint16(22, true)).toBe(1);
    expect(view.getUint32(24, true)).toBe(16000);
    expect(view.getUint32(40, true)).toBe(8);
    expect(view.getInt16(46, true)).toBe(32767);
    expect(view.getInt16(48, true)).toBe(-32768);
    expect(view.getInt16(50, true)).toBe(32767);
  });

  it("downsamples 48 kHz to 16 kHz by averaging each window", () => {
    const input = new Float32Array([0.3, 0.3, 0.3, 0.6, 0.6, 0.6]);
    const output = resample(input, 48000, 16000);
    expect(Array.from(output).map((value) => Number(value.toFixed(3)))).toEqual([0.3, 0.6]);
    expect(resample(new Float32Array(44100), 44100, 16000).length).toBe(16000);
  });
});
