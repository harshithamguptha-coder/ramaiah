/** Card, Button, Badge and other primitives. Grouped to keep imports simple. */

import Icon from './Icon'

/* ---------------- Card ---------------- */

export function Card({ children, className = '', accent, ...rest }) {
  const accentClass = accent ? ` card--${accent}` : ''
  return (
    <section className={`card${accentClass} ${className}`.trim()} {...rest}>
      {children}
    </section>
  )
}

export function CardHeader({ title, subtitle, actions, children }) {
  return (
    <header className="card__head">
      <div>
        <h3 className="card__title">{title}</h3>
        {subtitle && <p className="card__subtitle">{subtitle}</p>}
        {children}
      </div>
      {actions && <div className="row row--tight">{actions}</div>}
    </header>
  )
}

export function CardBody({ children, tight = false, className = '' }) {
  return <div className={`card__body${tight ? ' card__body--tight' : ''} ${className}`.trim()}>{children}</div>
}

export function CardFooter({ children }) {
  return <footer className="card__foot">{children}</footer>
}

/* ---------------- Button ---------------- */

export function Button({
  children,
  variant = 'secondary',
  size,
  loading = false,
  icon,
  iconRight,
  block = false,
  disabled,
  type = 'button',
  ...rest
}) {
  const classes = [
    'btn',
    `btn--${variant}`,
    size ? `btn--${size}` : '',
    block ? 'btn--block' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <button type={type} className={classes} disabled={disabled || loading} {...rest}>
      {loading ? <span className="spinner" aria-hidden="true" /> : icon ? <Icon name={icon} size={15} /> : null}
      {children}
      {iconRight && !loading ? <Icon name={iconRight} size={15} /> : null}
    </button>
  )
}

/* ---------------- Badge ---------------- */

export function Badge({ children, tone = 'neutral', ...rest }) {
  return (
    <span className={`badge badge--${tone}`} {...rest}>
      {children}
    </span>
  )
}

/** Explicit "this value is fabricated" marker used across the analysis pages. */
export function MockBadge({ label = 'Mock data' }) {
  return (
    <Badge tone="mock" title="Placeholder value — no real model or circuit has been run.">
      {label}
    </Badge>
  )
}

/* ---------------- Stat ---------------- */

export function StatTile({ label, value, hint, tone }) {
  return (
    <div className="stat">
      <span className="stat__label">{label}</span>
      <span className="stat__value" style={tone ? { color: `var(--${tone})` } : undefined}>
        {value}
      </span>
      {hint && <span className="stat__hint">{hint}</span>}
    </div>
  )
}

/* ---------------- Progress ---------------- */

export function ProgressBar({ value, tone, label }) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0))
  return (
    <div
      className={`progress${tone ? ` progress--${tone}` : ''}`}
      role="progressbar"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
    >
      <div className="progress__fill" style={{ width: `${pct}%` }} />
    </div>
  )
}

/** Labelled horizontal meter used for scores across the analysis pages. */
export function MeterRow({ label, value, tone, displayValue }) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0))
  return (
    <div className="meter-row">
      <span className="meter-row__label" title={label}>
        {label}
      </span>
      <ProgressBar value={pct} tone={tone} label={label} />
      <span className="meter-row__value">{displayValue ?? Math.round(pct)}</span>
    </div>
  )
}

/* ---------------- Alerts ---------------- */

export function Alert({ tone = 'info', title, children, icon }) {
  const iconName = icon || { info: 'info', warning: 'warning', danger: 'warning', success: 'check', neutral: 'info' }[tone]
  return (
    <div className={`alert alert--${tone}`} role={tone === 'danger' ? 'alert' : 'status'}>
      <Icon name={iconName} size={17} className="alert__icon" />
      <div>
        {title && <div className="alert__title">{title}</div>}
        <div>{children}</div>
      </div>
    </div>
  )
}

/* ---------------- Feedback states ---------------- */

export function Spinner({ large = false }) {
  return <span className={`spinner${large ? ' spinner--lg' : ''}`} role="status" aria-label="Loading" />
}

export function LoadingBlock({ label = 'Loading…', large = false }) {
  return (
    <div className="loading-block">
      <Spinner large={large} />
      <span>{label}</span>
    </div>
  )
}

export function EmptyState({ icon = 'search', title, children, action }) {
  return (
    <div className="empty">
      <div className="empty__icon">
        <Icon name={icon} size={22} />
      </div>
      {title && <div className="empty__title">{title}</div>}
      {children && <p className="empty__text">{children}</p>}
      {action}
    </div>
  )
}

export function Skeleton({ height = 16, width = '100%', style }) {
  return <div className="skeleton" style={{ height, width, ...style }} aria-hidden="true" />
}

/** Generic async wrapper: renders loading / error / empty before children. */
export function AsyncBoundary({ loading, error, isEmpty, loadingLabel, emptyState, children, onRetry }) {
  if (loading) return <LoadingBlock label={loadingLabel} />
  if (error) {
    return (
      <Alert tone="danger" title="Something went wrong">
        {error}
        {onRetry && (
          <div className="mt-2">
            <Button size="sm" variant="secondary" onClick={onRetry}>
              Try again
            </Button>
          </div>
        )}
      </Alert>
    )
  }
  if (isEmpty) return emptyState || null
  return children
}
