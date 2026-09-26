import { useNavigate } from 'react-router-dom'

import SearchBar from '../components/SearchBar'
import styles from './HomePage.module.css'

const FEATURES = [
  {
    title: 'Missing connections',
    body: 'People and places that an article mentions, but that have no article of their own yet.',
  },
  {
    title: 'One-way connections',
    body: 'Articles that the source links to, but that never link back to the source.',
  },
  {
    title: 'Connection map',
    body: 'Every relationship drawn as a directed graph, so gaps stand out at a glance.',
  },
]

const EXAMPLES = ['Chandni Chowk', 'Ada Lovelace', 'Bongaon']

export default function HomePage() {
  const navigate = useNavigate()
  const search = (title) => navigate(`/search?title=${encodeURIComponent(title)}`)

  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <h1 className={styles.title}>Find the Missing Connections</h1>
        <h2 className={styles.description}> The Connected KnowledgeBase</h2>
        <p className={styles.description}>
          Discover people and places mentioned in articles that don&apos;t have their
          own article yet, or connections that only work in one direction.
        </p>

        <div className={styles.search}>
          <SearchBar autoFocus submitLabel="Search" onAnalyze={search} />
        </div>

        <p className={styles.hint}>
          Try{' '}
          {EXAMPLES.map((example, index) => (
            <span key={example}>
              <button type="button" className={styles.example} onClick={() => search(example)}>
                {example}
              </button>
              {index < EXAMPLES.length - 1 && ', '}
            </span>
          ))}
        </p>
      </section>

      <section className={styles.features}>
        {FEATURES.map((feature) => (
          <div key={feature.title} className={styles.feature}>
            <h2 className={styles.featureTitle}>{feature.title}</h2>
            <p className={styles.featureBody}>{feature.body}</p>
          </div>
        ))}
      </section>
    </div>
  )
}
