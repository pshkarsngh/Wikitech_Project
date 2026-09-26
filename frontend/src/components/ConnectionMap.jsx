import { useEffect, useRef } from 'react'
import cytoscape from 'cytoscape'

import { EmptyState, Legend } from './ui'
import styles from './ConnectionMap.module.css'

const LEGEND_ITEMS = [
  { label: 'Source article', color: 'var(--seed)' },
  { label: 'Article node', color: 'var(--mutual)' },
  { label: 'Person node', color: 'var(--person)' },
  { label: 'Place node', color: 'var(--place)' },
  { label: 'Missing entity', color: 'var(--missing)', dashed: true },
]

// Cytoscape has its own style parser and never reads CSS custom properties: a
// colour value is resolved by colour2tuple, which understands named colours,
// hex, rgb() and hsl() only. Handing it 'var(--missing)' makes it drop the
// property, so the graph would render in Cytoscape's defaults and nothing would
// look missing. The tokens are therefore read off :root and passed as literals.
const _tokenCache = new Map()

function token(name) {
  if (_tokenCache.has(name)) return _tokenCache.get(name)
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim()
  if (!value) {
    // Silently rendering with Cytoscape's default here is how the broken
    // var() version survived; say so instead.
    console.warn(`ConnectionMap: design token ${name} is not defined in index.css`)
  }
  _tokenCache.set(name, value)
  return value
}

function elementsFor(map) {
  const elements = []

  for (const node of map.nodes) {
    elements.push({
      group: 'nodes',
      data: {
        id: node.id,
        label: node.label,
        exists: node.exists,
        isSeed: node.is_seed,
        entityType: node.entity_type,
        url: node.url,
      },
    })
  }

  for (const edge of map.edges) {
    elements.push({
      group: 'edges',
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        status: edge.status,
        exists: edge.exists,
      },
    })
  }

  return elements
}

function stylesheet() {
  const mutual = token('--mutual')
  const oneway = token('--oneway')
  const missing = token('--missing')
  const muted = token('--muted')
  const canvas = token('--canvas')

  return [
    {
      selector: 'node',
      style: {
        label: 'data(label)',
        'font-size': 10,
        'text-valign': 'bottom',
        'text-margin-y': 6,
        color: token('--text-soft'),
        'text-outline-color': canvas,
        'text-outline-width': 2,
        width: 22,
        height: 22,
        'background-color': mutual,
        'border-width': 2,
        'border-color': canvas,
      },
    },
    {
      selector: 'node[?isSeed]',
      style: {
        width: 46,
        height: 46,
        'font-size': 13,
        'font-weight': 'bold',
        'background-color': token('--seed'),
        color: token('--text'),
      },
    },
    {
      selector: 'node[entityType = "person"]',
      style: {
        'background-color': token('--person'),
        shape: 'ellipse',
      },
    },
    {
      selector: 'node[entityType = "place"]',
      style: {
        'background-color': token('--place'),
        shape: 'round-rectangle',
      },
    },
    {
      selector: 'node[!exists]',
      style: {
        'background-color': missing,
        'border-style': 'dashed',
        'border-width': 3,
        shape: 'round-diamond',
      },
    },
    {
      selector: 'edge',
      style: {
        width: 2,
        'curve-style': 'bezier',
        'target-arrow-shape': 'triangle',
        'arrow-scale': 1.1,
        'line-color': mutual,
        'target-arrow-color': mutual,
      },
    },
    {
      selector: 'edge[status = "one-way"]',
      style: {
        'line-color': oneway,
        'target-arrow-color': oneway,
        'line-style': 'dashed',
      },
    },
    {
      selector: 'edge[status = "missing"]',
      style: {
        'line-color': missing,
        'target-arrow-color': missing,
        'line-style': 'dotted',
        'line-cap': 'round',
      },
    },
    {
      selector: 'edge[status = "unchecked"]',
      style: {
        'line-color': muted,
        'target-arrow-color': muted,
        opacity: 0.5,
      },
    },
    {
      selector: ':selected',
      style: {
        'border-color': token('--ink'),
        'border-width': 3,
      },
    },
  ]
}

export default function ConnectionMap({ map }) {
  const containerRef = useRef(null)
  const cyRef = useRef(null)

  useEffect(() => {
    if (!containerRef.current) return undefined

    const cy = cytoscape({
      container: containerRef.current,
      elements: elementsFor(map),
      style: stylesheet(),
      layout: { name: 'breadthfirst', directed: true, roots: '#' + map.nodes.find((n) => n.is_seed)?.id, padding: 40, spacingFactor: 1.1 },
      wheelSensitivity: 0.2,
    })

    cyRef.current = cy

    // Cytoscape caches the container size, so a rotated phone or a resized
    // window would otherwise leave the graph cropped or offset.
    const observer = new ResizeObserver(() => {
      cy.resize()
    })
    observer.observe(containerRef.current)

    return () => {
      observer.disconnect()
      cy.destroy()
      cyRef.current = null
    }
  }, [map])

  if (!map || map.nodes.length === 0) {
    return (
      <EmptyState
        title="No connections to draw"
        description="This article has no outgoing links to map."
      />
    )
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.toolbar}>
        <Legend items={LEGEND_ITEMS} />
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.button}
            onClick={() => cyRef.current?.fit(undefined, 40)}
          >
            Fit
          </button>
          <button
            type="button"
            className={styles.button}
            onClick={() => {
              cyRef.current?.layout({ name: 'breadthfirst', directed: true, padding: 40 }).run()
            }}
          >
            Re-layout
          </button>
        </div>
      </div>
      <div className={styles.canvas} ref={containerRef} />
      {map.truncated && (
        <p className={styles.note}>
          The map shows the first {map.nodes.length - 1} connections. Raise{' '}
          <code>MAP_NODE_LIMIT</code> in <code>backend/.env</code> for more.
        </p>
      )}
    </div>
  )
}
