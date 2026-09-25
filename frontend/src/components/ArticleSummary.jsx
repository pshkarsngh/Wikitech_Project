import styles from './ArticleSummary.module.css'

export default function ArticleSummary({ article, generatedAt }) {
  if (!article) return null

  return (
    <article className={styles.summary}>
      <div className={styles.header}>
        <h2 className={styles.title}>{article.title}</h2>
        {article.url && (
          <a
            className={styles.wikiLink}
            href={article.url}
            target="_blank"
            rel="noreferrer noopener"
          >
            Read on Wikipedia ↗
          </a>
        )}
      </div>

      {article.description && <p className={styles.description}>{article.description}</p>}
      {article.extract && <p className={styles.extract}>{article.extract}</p>}

      <dl className={styles.meta}>
        {article.page_id && (
          <div>
            <dt>Page ID</dt>
            <dd>{article.page_id}</dd>
          </div>
        )}
        {article.length && (
          <div>
            <dt>Article size</dt>
            <dd>{article.length.toLocaleString()} bytes</dd>
          </div>
        )}
        {generatedAt && (
          <div>
            <dt>Analyzed</dt>
            <dd>{new Date(generatedAt).toLocaleString()}</dd>
          </div>
        )}
      </dl>
    </article>
  )
}
