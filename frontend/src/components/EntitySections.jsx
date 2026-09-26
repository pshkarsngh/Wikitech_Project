import { useMemo } from 'react'

import { Card, ConnectionStateBadge, EmptyState } from './ui'
import styles from './EntitySections.module.css'

// People and places are the point of the app, so they get their own sections
// rather than one long mixed list. `other` is deliberately not given a section:
// it is everything the classifier could not place, and listing it would bury the
// two categories that matter.
const SECTIONS = [
  {
    key: 'people',
    entityType: 'person',
    tone: 'person',
    title: 'People',
    emptyTitle: 'No people identified',
    emptyDescription:
      'No link in this article describes a person. Names are typed from the description on the article they point to, or from Wikidata when the name has no article yet.',
    missing: false,
  },
  {
    key: 'places',
    entityType: 'place',
    tone: 'place',
    title: 'Places',
    emptyTitle: 'No places identified',
    emptyDescription:
      'No link in this article describes a place. Names are typed from the description on the article they point to, or from Wikidata when the name has no article yet.',
    missing: false,
  },
  {
    key: 'missingPeople',
    entityType: 'person',
    tone: 'missing',
    title: 'Missing People',
    emptyTitle: 'No missing people',
    emptyDescription:
      'Every person linked from this article has an article of their own.',
    missing: true,
  },
  {
    key: 'missingPlaces',
    entityType: 'place',
    tone: 'missing',
    title: 'Missing Places',
    emptyTitle: 'No missing places',
    emptyDescription:
      'Every place linked from this article has an article of their own.',
    missing: true,
  },
]

// An entity is one extracted link that the classifier recognised as a person or
// a place. Everything the sections need is already on the link: the name, the
// type, the article it was mentioned in, a Wikipedia link when the target
// exists, and the existence status.
function selectEntities(links, { entityType, missing }) {
  // Two different link titles can redirect to the same article, so the same
  // person or place can arrive twice. It is one entity, so it is listed once:
  // Wikipedia titles are case-insensitive on the first letter, so the key is
  // the lowercased title.
  const seen = new Set()
  const entities = []
  for (const link of links) {
    if (link.entity_type !== entityType) continue
    if (missing ? link.exists : !link.exists) continue
    const key = link.title.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    entities.push(link)
  }
  return entities
}

function EntityRow({ entity }) {
  return (
    <li className={styles.row}>
      <div className={styles.rowMain}>
        {entity.exists && entity.url ? (
          <a
            className={styles.name}
            href={entity.url}
            target="_blank"
            rel="noreferrer noopener"
          >
            {entity.title} ↗
          </a>
        ) : (
          <span className={styles.name}>{entity.title}</span>
        )}
        {entity.source_title && (
          <span className={styles.source}>
            mentioned in{' '}
            {entity.source_url ? (
              <a
                href={entity.source_url}
                target="_blank"
                rel="noreferrer noopener"
              >
                {entity.source_title} ↗
              </a>
            ) : (
              entity.source_title
            )}
          </span>
        )}
      </div>
      <div className={styles.rowStatus}>
        <ConnectionStateBadge state={entity.state} exists={entity.exists} />
        <span className={styles.statusNote}>
          {entity.exists ? 'has an article' : 'no article yet'}
        </span>
      </div>
    </li>
  )
}

export default function EntitySections({ links = [], sourceTitle, summary = {} }) {
  const grouped = useMemo(() => {
    const byKey = {}
    for (const section of SECTIONS) {
      byKey[section.key] = selectEntities(links, {
        entityType: section.entityType,
        missing: section.missing,
      })
    }
    return byKey
  }, [links])

  if (links.length === 0) return null

  // Only a name with no article has to be looked up on Wikidata, and that is
  // capped, so the missing sections can be incomplete. The sections built from
  // an article's own descriptions are not capped and are complete.
  const classifyTruncated = summary.classify_truncated

  return (
    <div className={styles.sections}>
      {SECTIONS.map((section) => {
        const entities = grouped[section.key]
        const canBeIncomplete = section.missing && classifyTruncated

        return (
          <Card
            key={section.key}
            tone={section.tone}
            title={section.title}
            subtitle={`${entities.length} ${section.missing ? 'without an article of their own' : 'with an article'}, from ${sourceTitle || 'this article'}.`}
          >
            {entities.length === 0 ? (
              <EmptyState
                title={section.emptyTitle}
                description={section.emptyDescription}
              />
            ) : (
              <>
                <ul className={styles.list} aria-label={section.title}>
                  {entities.map((entity) => (
                    <EntityRow key={entity.title} entity={entity} />
                  ))}
                </ul>
                {canBeIncomplete && (
                  <p className={styles.note}>
                    Some names could not be typed because the Wikidata lookup
                    limit was reached, so this list can be incomplete. Raise{' '}
                    <code>CLASSIFY_MAX_ITEMS</code> in <code>backend/.env</code>{' '}
                    to check all of them.
                  </p>
                )}
              </>
            )}
          </Card>
        )
      })}
    </div>
  )
}
