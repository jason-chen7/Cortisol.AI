/**
 * audioRecorder.js
 * Captures mono 16 kHz microphone audio via AudioWorklet and calls
 * onChunk(ArrayBuffer) with raw Int16 PCM for each processed frame.
 */

const SAMPLE_RATE = 16_000

export class AudioRecorder {
  constructor(onChunk) {
    this._onChunk = onChunk
    this._ctx = null
    this._stream = null
    this._source = null
    this._worklet = null
    this._analyser = null
    this.isRecording = false
  }

  async start() {
    this._ctx = new AudioContext({ sampleRate: SAMPLE_RATE })

    this._stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        sampleRate: SAMPLE_RATE,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    })

    this._source = this._ctx.createMediaStreamSource(this._stream)

    // Analyser for waveform visualisation
    this._analyser = this._ctx.createAnalyser()
    this._analyser.fftSize = 2048
    this._source.connect(this._analyser)

    // AudioWorklet for PCM capture
    await this._ctx.audioWorklet.addModule('/audioProcessor.js')
    this._worklet = new AudioWorkletNode(this._ctx, 'pcm-processor')
    this._worklet.port.onmessage = (e) => {
      if (this.isRecording && e.data.pcm) {
        this._onChunk(e.data.pcm)
      }
    }
    this._source.connect(this._worklet)

    this.isRecording = true
  }

  /** Returns the AnalyserNode so Waveform can visualise audio live. */
  getAnalyserNode() {
    return this._analyser
  }

  stop() {
    this.isRecording = false
    this._worklet?.disconnect()
    this._source?.disconnect()
    this._stream?.getTracks().forEach((t) => t.stop())
    this._ctx?.close()
    this._worklet = null
    this._source = null
    this._stream = null
    this._ctx = null
    this._analyser = null
  }
}
