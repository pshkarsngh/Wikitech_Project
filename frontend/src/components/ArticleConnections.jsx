import { useMemo, useState } from 'react'

import { Card, ConnectionStateBadge, EmptyState, EntityBadge, Legend } from './ui'
import styles from './ArticleConnections.module.css'

const PAGE_SIZE = 50

export default function ArticleConnections({ links, sourceTitle }) {
  const [filter, setFilter] = useState('')
  const [onlyMissing, setOnlyMissing] = useState(false)
  const [visible, setVisible] = useState(PAGE_SIZE)

  const filtered = useMemo(() => {
    const needle = filter.trim().toLowerCase()
    return links.filter((link) => {
      if (onlyMissing && link.exists) return false
      if (!needle) return true
      return link.title.toLowerCase().includes(needle)
    })
  }, [links, filter, onlyMissing])

  // Counts describe the rows on screen, so they always agree with the list.
  const states = useMemo(() => {
    const exists = filtered.filter((link) => link.exists).length
    return { exists, missing: filtered.length - exists }
  }, [filtered])

  const inArticle = sourceTitle ? `in ${sourceTitle}` : 'in this article'

  return (
    <Card
      title="Article Connections"
      subtitle={`Every link ${inArticle}, classified as EXISTS or MISSING depending on whether the target has an article of its own. External websites, images, files, categories and other non-article links are excluded.`}
      action={
        <span className={styles.count}>
          {filtered.length} of {links.length}
        </span>
      }
    >
      {links.length === 0 ? (
        <EmptyState
          title="No article connections"
          description="This article does not link to any other article."
        />
      ) : (
        <>
          <div className={styles.controls}>
            <input
              className={styles.filterInput}
              type="search"
              value={filter}
              placeholder="Filter connections"
              aria-label="Filter article connections"
              onChange={(event) => {
                setFilter(event.target.value)
                setVisible(PAGE_SIZE)
              }}
            />
            <label className={styles.checkbox}>
              <input
                type="checkbox"
                checked={onlyMissing}
                onChange={(event) => {
                  setOnlyMissing(event.target.checked)
                  setVisible(PAGE_SIZE)
                }}
              />
              Missing only
            </label>
          </div>

          <Legend
            items={[
              { label: `EXISTS (${states.exists})`, color: 'var(--positive)' },
              { label: `MISSING (${states.missing})`, color: 'var(--missing)' },
            ]}
          />

          {filtered.length === 0 ? (
            <p className={styles.emptyRow}>No connections match this filter.</p>
          ) : (
            <>
              <ul className={styles.list} aria-label={`Article connections ${inArticle}`}>
                {filtered.slice(0, visible).map((link) => (
                  <li key={link.title} className={styles.row}>
                    {link.exists && link.url ? (
                      <a
                        className={styles.title}
                        href={link.url}
                        target="_blank"
                        rel="noreferrer noopener"
                      >
                        {link.title} ↗
                      </a>
                    ) : (
                      <span className={`${styles.title} ${styles.missing}`}>
                        {link.title}
                      </span>
                    )}
                    <ConnectionStateBadge
                      state={link.state}
                      exists={link.exists}
                    />
                    {link.redirected && (
                      <span className={styles.meta}>via redirect</span>
                    )}
                    {!link.is_internal && (
                      <span className={styles.external}>external link</span>
                    )}
                    <EntityBadge entityType={link.entity_type} />
                  </li>
                ))}
              </ul>
              {visible < filtered.length && (
                <button
                  type="button"
                  className={styles.showMore}
                  onClick={() => setVisible((count) => count + PAGE_SIZE)}
                >
                  Show {Math.min(PAGE_SIZE, filtered.length - visible)} more
                </button>
              )}
            </>
          )}
        </>
      )}
    </Card>
  )
}
