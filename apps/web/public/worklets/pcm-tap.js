// Copies microphone samples to the page in batches of 1024. The output stays silent.
class PcmTap extends AudioWorkletProcessor {
  constructor() {
    super();
    this.batch = new Float32Array(1024);
    this.filled = 0;
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (channel) {
      let offset = 0;
      while (offset < channel.length) {
        const take = Math.min(channel.length - offset, this.batch.length - this.filled);
        this.batch.set(channel.subarray(offset, offset + take), this.filled);
        this.filled += take;
        offset += take;
        if (this.filled === this.batch.length) {
          this.port.postMessage(this.batch, [this.batch.buffer]);
          this.batch = new Float32Array(1024);
          this.filled = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor("pcm-tap", PcmTap);
