/**
 * audioProcessor.js — AudioWorkletProcessor
 * Converts float32 audio frames → Int16 PCM and posts them to the main thread.
 * Must live in /public so Vite serves it as a static asset.
 */

class PCMProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0]?.[0]
    if (!channel) return true

    const int16 = new Int16Array(channel.length)
    for (let i = 0; i < channel.length; i++) {
      const s = Math.max(-1, Math.min(1, channel[i]))
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
    }

    // Transfer ownership to avoid copy
    this.port.postMessage({ pcm: int16.buffer }, [int16.buffer])
    return true
  }
}

registerProcessor('pcm-processor', PCMProcessor)
