/**
 * websocket.js
 * Thin WebSocket wrapper that routes server messages to typed callbacks.
 */

// Uses Vite's dev-server proxy (/stream → ws://localhost:8000/stream)
// so no cross-origin issues. In production, replace with your actual WS URL.
const WS_URL = `ws://${window.location.host}/stream`

export class StressWebSocket {
  /**
   * @param {{
   *   onChunkResult:  (msg: object) => void,
   *   onFinalSummary: (msg: object) => void,
   *   onTranscript:   (msg: object) => void,
   *   onVoiceAudio:   (msg: object) => void,
   *   onError:        (message: string) => void,
   *   onClose:        () => void,
   * }} handlers
   */
  constructor({ onChunkResult, onFinalSummary, onTranscript, onVoiceAudio, onError, onClose }) {
    this._handlers = { onChunkResult, onFinalSummary, onTranscript, onVoiceAudio, onError, onClose }
    this._ws = null
  }

  connect() {
    this._ws = new WebSocket(WS_URL)
    this._ws.binaryType = 'arraybuffer'

    this._ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if      (msg.type === 'chunk_result')  this._handlers.onChunkResult(msg)
        else if (msg.type === 'final_summary') this._handlers.onFinalSummary(msg)
        else if (msg.type === 'transcript')    { console.log('[WS] transcript:', msg.text); this._handlers.onTranscript?.(msg) }
        else if (msg.type === 'voice_audio')   this._handlers.onVoiceAudio?.(msg)
        else if (msg.type === 'error')         this._handlers.onError(msg.message)
      } catch {
        this._handlers.onError('Failed to parse server message.')
      }
    }

    this._ws.onerror = () => {
      this._handlers.onError('WebSocket connection failed. Is the backend running?')
    }

    this._ws.onclose = () => {
      this._handlers.onClose()
    }
  }

  /** Send raw PCM ArrayBuffer to the server. */
  sendAudio(buffer) {
    if (this._ws?.readyState === WebSocket.OPEN) {
      this._ws.send(buffer)
    }
  }

  close() {
    this._ws?.close()
  }

  get isOpen() {
    return this._ws?.readyState === WebSocket.OPEN
  }
}
