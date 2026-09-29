/**
 * Dependency-free SVG charts.
 *
 * Deliberately no charting library: a few small components cover every chart
 * the prototype needs and keep the bundle small.
 */

import { clampScore } from '../../utils/format'

export const TONE_VAR = {
  classical: 'var(--classical)',
  quantum: 'var(--quantum)',
  hybrid: 'var(--hybrid)',
  brand: 'var(--brand-500)',
  success: 'var(--success)',
  warning: '#f59e0b',
  danger: 'var(--danger)',
}

export const APPROACH_LABEL = {
  classical: 'Classical AI',
  quantum: 'Quantum AI',
  hybrid: 'Hybrid AI',
}

/* ---------------- Horizontal bar chart ---------------- */

export function BarChart({ data = [], tone = 'brand', suffix = '', max = 0 }) {
  const ceiling = max || Math.max(...data.map((d) => d.value || 0), 1)

  return (
    <div className="bar-chart">
      {data.map((item) => (
        <div className="bar-chart__row" key={item.label}>
          <span className="bar-chart__label" title={item.label}>
            {item.label}
          </span>
          <div className="progress">
            <div
              className="progress__fill"
              style={{
                width: `${clampScore(((item.value || 0) / ceiling) * 100)}%`,
                background: item.tone ? TONE_VAR[item.tone] : TONE_VAR[tone],
              }}
            />
          </div>
          <span className="bar-chart__value">
            {item.display ?? Math.round(item.value || 0)}
            {suffix}
          </span>
        </div>
      ))}
    </div>
  )
}

/* ---------------- Grouped score comparison ---------------- */

export function GroupedBars({ criteria = [], keys = ['classical', 'quantum', 'hybrid'] }) {
  return (
    <div className="bar-chart">
      {criteria.map((criterion) => (
        <div key={criterion.criterion} className="stack stack--sm">
          <span className="small" style={{ fontWeight: 600 }}>
            {criterion.criterion}
            {criterion.weight ? (
              <span className="muted" style={{ fontWeight: 400 }}>
                {' '}· weight {Math.round(criterion.weight * 100)}%
              </span>
            ) : null}
          </span>
          {keys.map((key) => (
            <div className="meter-row" key={key}>
              <span className="meter-row__label">{APPROACH_LABEL[key] || key}</span>
              <div className="progress">
                <div
                  className="progress__fill"
                  style={{
                    width: `${clampScore(criterion[key]?.score)}%`,
                    background: TONE_VAR[key],
                  }}
                />
              </div>
              <span className="meter-row__value">{criterion[key]?.score ?? '—'}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

/* ---------------- Radar chart ---------------- */

const SIZE = 280
const CENTER = SIZE / 2
const RADIUS = 108

const polar = (index, total, value) => {
  const angle = (Math.PI * 2 * index) / total - Math.PI / 2
  const scaled = (RADIUS * clampScore(value)) / 100
  return [CENTER + scaled * Math.cos(angle), CENTER + scaled * Math.sin(angle)]
}

export function RadarChart({ axes = [], series = [], size = SIZE }) {
  if (!axes.length || !series.length) return null
  const rings = [25, 50, 75, 100]

  return (
    <div className="stack stack--sm" style={{ alignItems: 'center' }}>
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={`Radar chart comparing ${series.map((s) => s.label).join(', ')}`}
      >
        {rings.map((ring) => (
          <polygon
            key={ring}
            points={axes.map((_, i) => polar(i, axes.length, ring).join(',')).join(' ')}
            fill="none"
            stroke="var(--border)"
            strokeWidth="1"
          />
        ))}
        {axes.map((axis, i) => {
          const [x, y] = polar(i, axes.length, 100)
          return <line key={axis} x1={CENTER} y1={CENTER} x2={x} y2={y} stroke="var(--border)" strokeWidth="1" />
        })}
        {series.map((s) => (
          <polygon
            key={s.key}
            points={s.values.map((v, i) => polar(i, axes.length, v).join(',')).join(' ')}
            fill={TONE_VAR[s.key] || TONE_VAR.brand}
            fillOpacity="0.12"
            stroke={TONE_VAR[s.key] || TONE_VAR.brand}
            strokeWidth="2"
            strokeLinejoin="round"
          />
        ))}
      </svg>

      <div className="legend">
        {series.map((s) => (
          <span className="legend__item" key={s.key}>
            <span className="legend__swatch" style={{ background: TONE_VAR[s.key] || TONE_VAR.brand }} />
            {s.label}
          </span>
        ))}
      </div>
    </div>
  )
}

/* ---------------- Vertical column chart ---------------- */

export function ColumnChart({ data = [], suffix = '', height = 130 }) {
  const max = Math.max(...data.map((d) => d.value || 0), 1)

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${Math.max(data.length, 1)}, minmax(0, 1fr))`,
        gap: 'var(--sp-2)',
        alignItems: 'end',
        height,
      }}
    >
      {data.map((item) => (
        <div key={item.label} className="stack stack--sm" style={{ alignItems: 'center', gap: 4 }}>
          <span className="small" style={{ fontWeight: 650, fontVariantNumeric: 'tabular-nums' }}>
            {item.display ?? item.value}
            {suffix}
          </span>
          <div
            style={{
              width: '100%',
              maxWidth: 56,
              height: `${Math.max(4, ((item.value || 0) / max) * (height - 46))}px`,
              background: item.tone ? TONE_VAR[item.tone] : TONE_VAR.brand,
              borderRadius: '4px 4px 0 0',
            }}
          />
          <span className="small muted" style={{ lineHeight: 1.2, textAlign: 'center' }}>
            {item.label}
          </span>
        </div>
      ))}
    </div>
  )
}

/* ---------------- Vertical gauge ---------------- */

export function ScoreGauge({ score = 0, label, tone = 'brand', height = 84 }) {
  const value = clampScore(score)
  return (
    <div className="gauge">
      <div>
        <div className="gauge__value" style={{ color: TONE_VAR[tone] }}>
          {Math.round(value)}
        </div>
        <div className="stat__label">{label || 'out of 100'}</div>
      </div>
      <div className="gauge__track" style={{ height }}>
        <div className="gauge__fill" style={{ height: `${value}%`, background: TONE_VAR[tone] }} />
      </div>
    </div>
  )
}
