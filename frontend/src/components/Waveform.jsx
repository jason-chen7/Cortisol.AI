import { useEffect, useRef, useCallback } from 'react'

const STROKE = { green: '#22c55e', yellow: '#eab308', red: '#ef4444' }
const IDLE_STROKE = '#334155'

/**
 * Waveform — live oscilloscope canvas.
 *
 * Props:
 *   analyserNode  AnalyserNode | null  — Web Audio analyser from recorder
 *   color         'green' | 'yellow' | 'red'
 *   isRecording   boolean
 */
export default function Waveform({ analyserNode, color, isRecording }) {
  const canvasRef = useRef(null)
  const rafRef = useRef(null)
  const dataRef = useRef(null)

  const strokeColor = STROKE[color] ?? STROKE.green

  const drawFrame = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas || !analyserNode) return

    const ctx = canvas.getContext('2d')
    const { width, height } = canvas

    if (!dataRef.current) {
      dataRef.current = new Uint8Array(analyserNode.frequencyBinCount)
    }
    analyserNode.getByteTimeDomainData(dataRef.current)

    ctx.clearRect(0, 0, width, height)
    ctx.fillStyle = '#0f172a'
    ctx.fillRect(0, 0, width, height)

    ctx.lineWidth = 2.5
    ctx.strokeStyle = strokeColor
    ctx.shadowColor = strokeColor
    ctx.shadowBlur = 10
    ctx.beginPath()

    const sliceW = width / dataRef.current.length
    let x = 0
    for (let i = 0; i < dataRef.current.length; i++) {
      const y = (dataRef.current[i] / 128.0) * (height / 2)
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
      x += sliceW
    }
    ctx.lineTo(width, height / 2)
    ctx.stroke()

    rafRef.current = requestAnimationFrame(drawFrame)
  }, [analyserNode, strokeColor])

  const drawIdle = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const { width, height } = canvas
    ctx.clearRect(0, 0, width, height)
    ctx.fillStyle = '#0f172a'
    ctx.fillRect(0, 0, width, height)
    ctx.lineWidth = 2
    ctx.strokeStyle = IDLE_STROKE
    ctx.shadowBlur = 0
    ctx.beginPath()
    ctx.moveTo(0, height / 2)
    ctx.lineTo(width, height / 2)
    ctx.stroke()
  }, [])

  useEffect(() => {
    if (isRecording && analyserNode) {
      rafRef.current = requestAnimationFrame(drawFrame)
    } else {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      rafRef.current = null
      dataRef.current = null
      drawIdle()
    }
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [isRecording, analyserNode, drawFrame, drawIdle])

  return (
    <canvas
      ref={canvasRef}
      width={800}
      height={200}
      style={{
        width: '100%',
        height: '200px',
        borderRadius: '12px',
        border: `2px solid ${isRecording ? strokeColor : IDLE_STROKE}`,
        display: 'block',
        transition: 'border-color 0.4s ease',
      }}
    />
  )
}
