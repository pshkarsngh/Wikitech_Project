import styles from './ui.module.css'

const ENTITY_LABELS = {
  person: 'Person',
  place: 'Place',
  other: 'Other',
}

export function EntityBadge({ entityType }) {
  const label = ENTITY_LABELS[entityType] ?? ENTITY_LABELS.other
  return (
    <span className={`${styles.badge} ${styles[`badge_${entityType ?? 'other'}`]}`}>
      {label}
    </span>
  )
}

export function ConnectionStateBadge({ state, exists }) {
  // The API classifies every connection as `exists` or `missing`; `exists` is
  // the fallback for anything carrying only the boolean. Anything unrecognised
  // reads as missing, so an unknown classification is never shown as a
  // confirmed article.
  const resolved = (state ?? (exists ? 'exists' : 'missing')) === 'exists'
    ? 'exists'
    : 'missing'
  return (
    <span className={`${styles.badge} ${styles[`state_${resolved}`]}`}>
      {resolved === 'exists' ? 'EXISTS' : 'MISSING'}
    </span>
  )
}

export function StatCard({ label, value, hint, tone = 'neutral' }) {
  return (
    <div className={`${styles.statCard} ${styles[`stat_${tone}`]}`}>
      <span className={styles.statValue}>{value}</span>
      <span className={styles.statLabel}>{label}</span>
      {hint && <span className={styles.statHint}>{hint}</span>}
    </div>
  )
}

export function Card({ title, subtitle, action, tone, children }) {
  return (
    <section className={`${styles.card} ${tone ? styles[`card_${tone}`] : ''}`}>
      {(title || action) && (
        <header className={styles.cardHeader}>
          <div>
            {title && <h2 className={styles.cardTitle}>{title}</h2>}
            {subtitle && <p className={styles.cardSubtitle}>{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  )
}

export function EmptyState({ title, description, action }) {
  return (
    <div className={styles.empty}>
      <p className={styles.emptyTitle}>{title}</p>
      {description && <p className={styles.emptyDescription}>{description}</p>}
      {action}
    </div>
  )
}

export function Loading({ label = 'Analyzing article...' }) {
  return (
    <div className={styles.loading} role="status">
      <span className={styles.spinner} aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}

export function ErrorMessage({ error, onRetry }) {
  if (!error) return null
  return (
    <div className={styles.error} role="alert">
      <div>
        <p className={styles.errorTitle}>Something went wrong</p>
        <p className={styles.errorBody}>{String(error.message ?? error)}</p>
      </div>
      {onRetry && (
        <button className={styles.retry} type="button" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}

export function Legend({ items }) {
  return (
    <ul className={styles.legend}>
      {items.map((item) => (
        <li key={item.label} className={styles.legendItem}>
          <span
            className={styles.swatch}
            style={{ background: item.color, borderColor: item.border ?? item.color }}
          />
          {item.label}
        </li>
      ))}
    </ul>
  )
}
