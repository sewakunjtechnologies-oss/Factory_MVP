// AudioWorklet for the voice assistant's mic capture path.
//
// Gemini Live wants 16-bit signed PCM, mono, 16,000 Hz, little-endian.
// Browsers run the AudioContext at 44.1 kHz or 48 kHz, so we average-down
// (a one-pole moving-average over the decimation window) and pack to Int16.
// 100 ms chunks (1600 samples) hit a good latency/throughput balance.
//
// The main thread loads this via `audioContext.audioWorklet.addModule(...)`.

const TARGET_RATE = 16000;
const CHUNK_FRAMES = 1600; // 100 ms at 16 kHz

class VoiceMicProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._ratio = sampleRate / TARGET_RATE;
    this._acc = 0; // running fractional sample index
    this._sum = 0; // running average accumulator
    this._sumCount = 0;
    this._out = new Int16Array(CHUNK_FRAMES);
    this._outIdx = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;
    const channel = input[0]; // first channel only — mono
    if (!channel) return true;

    for (let i = 0; i < channel.length; i += 1) {
      this._sum += channel[i];
      this._sumCount += 1;
      this._acc += 1;
      if (this._acc >= this._ratio) {
        const avg = this._sum / this._sumCount;
        const clamped = Math.max(-1, Math.min(1, avg));
        this._out[this._outIdx] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
        this._outIdx += 1;
        this._acc -= this._ratio;
        this._sum = 0;
        this._sumCount = 0;
        if (this._outIdx === CHUNK_FRAMES) {
          // Transfer ownership of the buffer to avoid copies in the main thread.
          const transferable = this._out.buffer;
          this.port.postMessage(transferable, [transferable]);
          this._out = new Int16Array(CHUNK_FRAMES);
          this._outIdx = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor("voice-mic-processor", VoiceMicProcessor);
