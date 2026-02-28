/**
 * TranscriptPanel — live scrolling transcript from ElevenLabs.
 * Appears at the bottom of the screen while recording.
 * Hidden when transcript is empty.
 */

import { useEffect, useRef } from 'react'

export default function TranscriptPanel({ lines, visible }) {
  const bottomRef = useRef(null)

  // Auto-scroll to the latest line
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines])

  if (!visible || lines.length === 0) return null

  return (
    <div style={styles.wrapper}>
      <p style={styles.label}>Live Transcript</p>
      <div style={styles.scroll}>
        {lines.map((line, i) => (
          <span key={i} style={{ ...styles.word, opacity: i === lines.length - 1 ? 1 : 0.65 }}>
            {line}{' '}
          </span>
        ))}
        <span ref={bottomRef} />
      </div>
    </div>
  )
}

const styles = {
  wrapper: {
    position: 'fixed',
    bottom: 110,
    left: '50%',
    transform: 'translateX(-50%)',
    width: '88%',
    maxWidth: 640,
    maxHeight: 96,
    background: 'rgba(0,0,0,0.62)',
    backdropFilter: 'blur(14px)',
    borderRadius: 14,
    padding: '10px 18px 12px',
    zIndex: 3,
    overflowY: 'auto',
    boxSizing: 'border-box',
  },
  label: {
    color: '#475569',
    fontSize: '0.7rem',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.1em',
    marginBottom: 4,
    margin: '0 0 4px',
  },
  scroll: {
    lineHeight: 1.6,
  },
  word: {
    color: '#e2e8f0',
    fontSize: '0.88rem',
    fontFamily: "'Inter', system-ui, sans-serif",
    transition: 'opacity 0.3s',
  },
}
