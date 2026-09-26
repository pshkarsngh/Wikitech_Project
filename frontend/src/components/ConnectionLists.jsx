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
  linksTruncated = false,
}) {
  const [filter, setFilter] = useState('all')

  // Two different link titles can redirect to the same article, so one missing
  // name can arrive twice. It is one connection, so it is listed once; Wikipedia
  // titles are case-insensitive on the first letter, hence the lowercase key.
  const unique = useMemo(() => {
    const seen = new Set()
    return connections.filter((item) => {
      const key = item.title.toLowerCase()
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
  }, [connections])

  const filtered = useMemo(
    () =>
      filter === 'all'
        ? unique
        : unique.filter((item) => item.entity_type === filter),
    [unique, filter],
  )

  const counts = useMemo(
    () => ({
      person: unique.filter((item) => item.entity_type === 'person').length,
      place: unique.filter((item) => item.entity_type === 'place').length,
      other: unique.filter((item) => item.entity_type === 'other').length,
    }),
    [unique],
  )

  // The checked total makes the section readable against the connections that
  // do have an article, which is the whole point of the classification.
  const checked = totalLinks ?? unique.length
  const existing = Math.max(0, checked - (totalMissing ?? unique.length))

  // With a truncated link set the section cannot claim to cover every link in
  // the article, so the wording and a note both say so.
  const coverage = linksTruncated
    ? `of the first ${checked} links checked`
    : `of the ${checked} links checked`

  return (
    <Card
      tone="missing"
      title="Missing Connections"
      subtitle={
        <>
          Every person or place linked from this article that has no article of
          its own yet. {existing} {coverage} have an article.
        </>
      }
      action={
        unique.length > 0 && (
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
                {item.value === 'all' && ` (${unique.length})`}
              </button>
            ))}
          </div>
        )
      }
    >
      {unique.length === 0 ? (
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
        <>
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
          {linksTruncated && (
            <p className={styles.note}>
              This article has more links than were checked, so this list can be
              incomplete. Raise <code>MAX_LINKS_PER_ARTICLE</code> in{' '}
              <code>backend/.env</code> to check all of them.
            </p>
          )}
        </>
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
