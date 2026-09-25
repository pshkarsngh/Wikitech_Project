import { useMemo, useState } from 'react'

import {
  Card,
  ConnectionStateBadge,
  EmptyState,
  EntityBadge,
} from './ui'
import styles from './ConnectionLists.module.css'

const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'person', label: 'People' },
  { value: 'place', label: 'Places' },
  { value: 'other', label: 'Other' },
]

// A connection is only typed when the classifier recognised a person or a
// place. Anything else is listed without a type rather than guessed at.
const TYPED = new Set(['person', 'place'])

export function MissingConnectionsList({
  connections,
  totalLinks,
  totalMissing,
}) {
  const [filter, setFilter] = useState('all')

  const filtered = useMemo(
    () =>
      filter === 'all'
        ? connections
        : connections.filter((item) => item.entity_type === filter),
    [connections, filter],
  )

  const counts = useMemo(
    () => ({
      person: connections.filter((item) => item.entity_type === 'person').length,
      place: connections.filter((item) => item.entity_type === 'place').length,
      other: connections.filter((item) => item.entity_type === 'other').length,
    }),
    [connections],
  )

  // The checked total makes the section readable against the connections that
  // do have an article, which is the whole point of the classification.
  const checked = totalLinks ?? connections.length
  const existing = Math.max(0, checked - (totalMissing ?? connections.length))

  return (
    <Card
      tone="missing"
      title="Missing Connections"
      subtitle={
        <>
          Every person or place linked from this article that has no article of
          its own yet. {existing} of the {checked} checked links have an
          article.
        </>
      }
      action={
        connections.length > 0 && (
          <div className={styles.filters} role="group" aria-label="Filter by type">
            {FILTERS.map((item) => (
              <button
                key={item.value}
                type="button"
                className={`${styles.filter} ${
                  filter === item.value ? styles.filterActive : ''
                }`}
                aria-pressed={filter === item.value}
                onClick={() => setFilter(item.value)}
              >
                {item.label}
                {item.value !== 'all' && ` (${counts[item.value]})`}
                {item.value === 'all' && ` (${connections.length})`}
              </button>
            ))}
          </div>
        )
      }
    >
      {connections.length === 0 ? (
        <EmptyState
          title="No missing connections"
          description="Every main-namespace link in this article points to an article that exists. That is rare for a well-developed article."
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="Nothing in this category"
          description="Clear the filter to see all missing connections."
        />
      ) : (
        <ul className={styles.list} aria-label="Missing connections">
          {filtered.map((item) => (
            <li key={item.title} className={styles.itemMissing}>
              <div className={styles.itemMain}>
                <span className={styles.itemTitle}>{item.title}</span>
                {item.source_title && (
                  <span className={styles.source}>
                    from{' '}
                    {item.source_url ? (
                      <a
                        href={item.source_url}
                        target="_blank"
                        rel="noreferrer noopener"
                      >
                        {item.source_title} ↗
                      </a>
                    ) : (
                      item.source_title
                    )}
                  </span>
                )}
              </div>
              <div className={styles.itemStatus}>
                {TYPED.has(item.entity_type) && (
                  <EntityBadge entityType={item.entity_type} />
                )}
                <ConnectionStateBadge
                  state={item.state}
                  exists={item.exists}
                />
                <span className={styles.statusNote}>no article yet</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

export function OneWayConnectionsList({ connections, checkedCount, truncated }) {
  return (
    <Card
      title="One-Way Connections"
      subtitle={
        checkedCount
          ? `These articles are linked from the source article but do not link back. ${checkedCount} target${checkedCount === 1 ? '' : 's'} checked.`
          : 'These articles are linked from the source article but do not link back.'
      }
    >
      {connections.length === 0 ? (
        <EmptyState
          title="No one-way connections found"
          description="Every target article that was checked links back to the source article."
        />
      ) : (
        <>
          <ul className={styles.list}>
            {connections.map((item) => (
              <li key={item.target_title} className={styles.item}>
                <a
                  className={styles.itemTitle}
                  href={
                    item.target_url ??
                    `https://en.wikipedia.org/wiki/${encodeURIComponent(
                      item.target_title.replace(/ /g, '_'),
                    )}`
                  }
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  {item.target_title} ↗
                </a>
                <span className={styles.direction}>links one way only</span>
              </li>
            ))}
          </ul>
          {truncated && (
            <p className={styles.note}>
              Only the first targets were checked. Raise <code>ONE_WAY_MAX_TARGETS</code>{' '}
              in <code>backend/.env</code> to check more.
            </p>
          )}
        </>
      )}
    </Card>
  )
}
