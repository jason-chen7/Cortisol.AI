const LEVEL_COLOR = { Low: '#22c55e', Medium: '#eab308', High: '#ef4444' }

/**
 * SummaryCard — displays the final session summary from the backend.
 * Props:
 *   summary  object | null  — final_summary WebSocket message
 */
export default function SummaryCard({ summary }) {
  if (!summary) return null

  const {
    overall_stress,
    average_score,
    distribution,
    dominant_emotion,
    reasoning,
    enhanced_reasoning,
    transcript,
  } = summary

  const accent = LEVEL_COLOR[overall_stress] ?? '#94a3b8'

  return (
    <div
      style={{
        background: '#1e293b',
        borderRadius: '16px',
        padding: '28px',
        border: `2px solid ${accent}`,
        boxShadow: `0 0 40px ${accent}28`,
        animation: 'fadeIn 0.4s ease',
      }}
    >
      <h2 style={{ color: '#f1f5f9', marginBottom: '20px', fontSize: '1.35rem', fontWeight: 700 }}>
        Session Summary
      </h2>

      {/* KPI row */}
      <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap', marginBottom: '24px' }}>
        <KPI label="Overall Stress"    value={overall_stress}                          color={accent}    />
        <KPI label="Avg Score"         value={`${(average_score * 100).toFixed(0)}%`}  color="#94a3b8"   />
        <KPI label="Dominant Emotion"  value={dominant_emotion}                        color="#94a3b8" capitalize />
      </div>

      {/* Distribution bar */}
      <p style={styles.sectionLabel}>Stress Distribution</p>
      <DistributionBar distribution={distribution} />

      {/* Enhanced reasoning (Featherless AI) — shown when available */}
      {enhanced_reasoning ? (
        <ReasoningBlock
          label="AI Analysis"
          badgeText="Featherless AI"
          badgeColor="#818cf8"
          text={enhanced_reasoning}
          accent="#818cf8"
        />
      ) : (
        <ReasoningBlock
          label="Audio Analysis"
          text={reasoning}
          accent={accent}
        />
      )}

      {/* Transcript — shown when ElevenLabs returned text */}
      {transcript && transcript.trim().length > 0 && (
        <div style={{ marginTop: 20 }}>
          <p style={styles.sectionLabel}>Transcript</p>
          <div
            style={{
              background: '#0f172a',
              borderRadius: 8,
              padding: '14px 16px',
              maxHeight: 140,
              overflowY: 'auto',
            }}
          >
            <p style={{ color: '#64748b', fontSize: '0.88rem', lineHeight: 1.7, margin: 0 }}>
              {transcript}
            </p>
          </div>
        </div>
      )}

      <style>{`
        @keyframes fadeIn { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:none; } }
      `}</style>
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────
function ReasoningBlock({ label, text, accent, badgeText, badgeColor }) {
  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <p style={{ ...styles.sectionLabel, margin: 0 }}>{label}</p>
        {badgeText && (
          <span
            style={{
              background: `${badgeColor}22`,
              color: badgeColor,
              border: `1px solid ${badgeColor}55`,
              borderRadius: 20,
              padding: '1px 10px',
              fontSize: '0.7rem',
              fontWeight: 700,
              letterSpacing: '0.05em',
            }}
          >
            {badgeText}
          </span>
        )}
      </div>
      <div
        style={{
          background: '#0f172a',
          borderRadius: 8,
          padding: '14px 16px',
          borderLeft: `4px solid ${accent}`,
        }}
      >
        <p style={{ color: '#94a3b8', fontSize: '0.9rem', lineHeight: 1.65, margin: 0 }}>
          {text}
        </p>
      </div>
    </div>
  )
}

function KPI({ label, value, color, capitalize = false }) {
  return (
    <div style={{ flex: '1 1 120px' }}>
      <p style={{ color: '#64748b', fontSize: '0.75rem', marginBottom: 4, fontWeight: 600 }}>
        {label}
      </p>
      <p style={{ color, fontSize: '1.4rem', fontWeight: 800, textTransform: capitalize ? 'capitalize' : 'none', margin: 0 }}>
        {value}
      </p>
    </div>
  )
}

function DistributionBar({ distribution }) {
  const segments = [
    { key: 'Low',    color: '#22c55e' },
    { key: 'Medium', color: '#eab308' },
    { key: 'High',   color: '#ef4444' },
  ]
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: 'flex', height: 12, borderRadius: 6, overflow: 'hidden', gap: 2, background: '#0f172a' }}>
        {segments.map(({ key, color }) =>
          distribution[key] > 0 ? (
            <div
              key={key}
              style={{ width: `${distribution[key]}%`, background: color, transition: 'width 0.6s ease' }}
              title={`${key}: ${distribution[key]}%`}
            />
          ) : null,
        )}
      </div>
      <div style={{ display: 'flex', gap: 20, marginTop: 8 }}>
        {segments.map(({ key, color }) => (
          <span key={key} style={{ color, fontSize: '0.8rem', fontWeight: 600 }}>
            {key}: {distribution[key]}%
          </span>
        ))}
      </div>
    </div>
  )
}

const styles = {
  sectionLabel: {
    color: '#64748b',
    fontSize: '0.75rem',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.07em',
    marginBottom: 8,
  },
}
