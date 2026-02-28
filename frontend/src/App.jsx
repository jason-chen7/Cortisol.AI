import { useState, useRef, useCallback } from 'react'
import Head3D from './components/Head3D.jsx'
import SummaryCard from './components/SummaryCard.jsx'
import TranscriptPanel from './components/TranscriptPanel.jsx'
import { AudioRecorder } from './utils/audioRecorder.js'
import { StressWebSocket } from './utils/websocket.js'

const STATUS = { IDLE: 'idle', RECORDING: 'recording', PROCESSING: 'processing' }

// Page-level radial gradient per stress level (behind the Three.js canvas)
const PAGE_BG = {
  green:  'radial-gradient(ellipse at 50% 40%, #064e3b 0%, #022c22 55%, #011a10 100%)',
  yellow: 'radial-gradient(ellipse at 50% 40%, #78350f 0%, #431407 55%, #1a0a00 100%)',
  red:    'radial-gradient(ellipse at 50% 40%, #7f1d1d 0%, #450a0a 55%, #1a0404 100%)',
}

const LEVEL_COLOR = { Low: '#22c55e', Medium: '#eab308', High: '#ef4444' }

export default function App() {
  const [status,       setStatus]       = useState(STATUS.IDLE)
  const [color,        setColor]        = useState('green')
  const [emotion,      setEmotion]      = useState(null)
  const [stressLevel,  setStressLevel]  = useState(null)
  const [confidence,   setConfidence]   = useState(null)
  const [summary,      setSummary]      = useState(null)
  const [analyserNode, setAnalyserNode] = useState(null)
  const [error,        setError]        = useState(null)
  const [transcriptLines, setTranscriptLines] = useState([])

  const recorderRef = useRef(null)
  const wsRef       = useRef(null)

  // ── Start recording ─────────────────────────────────────────────────────────
  const handleStart = useCallback(async () => {
    setError(null)
    setSummary(null)
    setEmotion(null)
    setStressLevel(null)
    setConfidence(null)
    setColor('green')
    setTranscriptLines([])

    try {
      const ws = new StressWebSocket({
        onChunkResult: (msg) => {
          setColor(msg.color)
          setEmotion(msg.emotion)
          setStressLevel(msg.stress_level)
          setConfidence(msg.confidence)
        },
        onTranscript: (msg) => {
          setTranscriptLines((prev) => [...prev, msg.text])
        },
        onFinalSummary: (msg) => {
          setSummary(msg)
          setStatus(STATUS.IDLE)
          wsRef.current?.close()
          wsRef.current = null
        },
        onError: (msg) => {
          setError(msg)
          setStatus(STATUS.IDLE)
          wsRef.current?.close()
          wsRef.current = null
        },
        onClose: () => {
          setStatus((s) => (s === STATUS.RECORDING ? STATUS.IDLE : s))
        },
      })
      ws.connect()
      wsRef.current = ws

      const recorder = new AudioRecorder((pcmBuffer) => ws.sendAudio(pcmBuffer))
      await recorder.start()
      recorderRef.current = recorder

      setAnalyserNode(recorder.getAnalyserNode())
      setStatus(STATUS.RECORDING)
    } catch (err) {
      setError(err.message ?? 'Microphone access denied or unavailable.')
      setStatus(STATUS.IDLE)
    }
  }, [])

  // ── Stop recording ──────────────────────────────────────────────────────────
  const handleStop = useCallback(() => {
    setStatus(STATUS.PROCESSING)
    setAnalyserNode(null)
    recorderRef.current?.stop()
    recorderRef.current = null
    // WebSocket stays open — backend sends final_summary after 2 s silence
  }, [])

  const isRecording  = status === STATUS.RECORDING
  const isProcessing = status === STATUS.PROCESSING

  return (
    <>
      {/* ── Animated full-viewport background ────────────────────────────── */}
      <div
        style={{
          position: 'fixed',
          inset: 0,
          background: PAGE_BG[color] ?? PAGE_BG.green,
          transition: 'background 1.2s ease',
          zIndex: 0,
        }}
      />

      {/* ── Three.js canvas — fills entire screen ────────────────────────── */}
      <div style={{ position: 'fixed', inset: 0, zIndex: 1 }}>
        <Head3D analyserNode={analyserNode} stressColor={color} />
      </div>

      {/* ── UI overlay (pointer-events passthrough except interactive els) ── */}
      <div
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 2,
          display: 'flex',
          flexDirection: 'column',
          pointerEvents: 'none',
          fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
        }}
      >
        {/* Logo */}
        <div style={{ padding: '26px 36px' }}>
          <span style={styles.logo}>CORTISOL.AI</span>
        </div>

        {/* Spacer — 3D head fills this space */}
        <div style={{ flex: 1 }} />

        {/* Live status pill */}
        {isRecording && emotion && (
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 10 }}>
            <div style={styles.pill}>
              <span style={styles.recDot} />
              <span style={{ color: '#fff', textTransform: 'capitalize' }}>{emotion}</span>
              <span style={{ color: '#475569' }}>·</span>
              <span style={{ color: LEVEL_COLOR[stressLevel] ?? '#fff', fontWeight: 700 }}>
                {stressLevel} Stress
              </span>
              {confidence != null && (
                <>
                  <span style={{ color: '#475569' }}>·</span>
                  <span style={{ color: '#94a3b8' }}>
                    {(confidence * 100).toFixed(0)}% conf
                  </span>
                </>
              )}
            </div>
          </div>
        )}

        {isProcessing && (
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 10 }}>
            <div style={styles.pill}>
              <span style={{ color: '#94a3b8', fontSize: '0.88rem' }}>
                ⏳ Analysing… summary arriving shortly
              </span>
            </div>
          </div>
        )}

        {/* Live transcript panel — sits just above the button */}
        <TranscriptPanel lines={transcriptLines} visible={isRecording} />

        {/* Record / Stop button */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            paddingBottom: 44,
            pointerEvents: 'all',
          }}
        >
          {!isRecording ? (
            <button
              onClick={handleStart}
              disabled={isProcessing}
              style={glassBtn(isProcessing ? '#475569' : '#22c55e', isProcessing)}
            >
              ⏺ &nbsp;Start Recording
            </button>
          ) : (
            <button onClick={handleStop} style={glassBtn('#ef4444')}>
              ⏹ &nbsp;Stop
            </button>
          )}
        </div>

        {/* Error */}
        {error && (
          <div style={{ ...styles.errorBanner, pointerEvents: 'all' }}>{error}</div>
        )}
      </div>

      {/* ── Summary overlay ───────────────────────────────────────────────── */}
      {summary && (
        <div style={styles.summaryOverlay}>
          <div style={{ maxWidth: 660, width: '100%' }}>
            <SummaryCard summary={summary} />
            <button
              onClick={() => { setSummary(null); setColor('green') }}
              style={{ ...glassBtn('#64748b'), marginTop: 16, width: '100%' }}
            >
              Close &amp; Record Again
            </button>
          </div>
        </div>
      )}

      <style>{`
        @keyframes recPulse { 0%,100%{opacity:1} 50%{opacity:0.25} }
      `}</style>
    </>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function glassBtn(accentColor, disabled = false) {
  return {
    background: `${accentColor}28`,
    color: disabled ? '#64748b' : '#fff',
    border: `2px solid ${disabled ? '#334155' : accentColor}`,
    borderRadius: 14,
    padding: '15px 48px',
    fontSize: '1rem',
    fontWeight: 700,
    cursor: disabled ? 'not-allowed' : 'pointer',
    backdropFilter: 'blur(12px)',
    letterSpacing: '0.06em',
    opacity: disabled ? 0.55 : 1,
    transition: 'opacity 0.2s',
  }
}

const styles = {
  logo: {
    fontSize: '0.95rem',
    fontWeight: 800,
    letterSpacing: '0.22em',
    color: 'rgba(255,255,255,0.45)',
  },
  pill: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    background: 'rgba(0,0,0,0.55)',
    backdropFilter: 'blur(14px)',
    borderRadius: 24,
    padding: '9px 22px',
    fontSize: '0.88rem',
  },
  recDot: {
    display: 'inline-block',
    width: 9,
    height: 9,
    borderRadius: '50%',
    background: '#ef4444',
    animation: 'recPulse 1.1s infinite',
  },
  errorBanner: {
    textAlign: 'center',
    color: '#fca5a5',
    background: 'rgba(69,10,10,0.88)',
    padding: '10px 20px',
    fontSize: '0.9rem',
  },
  summaryOverlay: {
    position: 'fixed',
    inset: 0,
    zIndex: 30,
    background: 'rgba(0,0,0,0.84)',
    backdropFilter: 'blur(16px)',
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    padding: '48px 20px',
    fontFamily: "'Inter', system-ui, sans-serif",
  },
}
