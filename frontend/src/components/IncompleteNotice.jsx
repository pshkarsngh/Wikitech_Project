import styles from './IncompleteNotice.module.css'

// An analysis that ran out of time still answers, because the article's links and
// its missing connections are resolved first and are the part a reader needs. The
// parts that did not finish are not shown as if they had: the numbers on screen
// are a floor, and this says which panels they belong to.
//
// Deliberately not an error banner. Nothing failed - the deployment is working and
// said so in a bounded way - and styling it as a failure would train people to
// ignore the one warning that does matter.
export default function IncompleteNotice({ summary = {} }) {
  if (!summary.aborted) return null

  const {
    abort_reason: reason,
    entity_types_incomplete: typesIncomplete,
    links_truncated: linksCut,
    one_way_truncated: oneWayCut,
  } = summary

  // What did not finish, in the reader's words rather than the pipeline's. The
  // link graph and the missing connections are never listed here because they
  // are resolved before anything optional runs.
  const missing = []
  if (typesIncomplete) {
    missing.push('which of those names are people or places')
  }
  if (oneWayCut) {
    missing.push('which of the linked articles link back')
  }

  // "Complete" is only true of the link set when the crawl itself was not capped.
  // `links_truncated` is a separate reason the same numbers are a floor - a
  // different budget, hit before the clock ran out - and this notice must not
  // contradict the hint the tile already shows for it.
  const links = linksCut
    ? 'The links below already stopped at the per-article limit, and the missing connections cover every link in that set, but not every link in the article.'
    : 'The links and missing connections below are complete.'

  return (
    <div className={styles.notice} role="status">
      <p className={styles.title}>This analysis is incomplete</p>
      <p className={styles.body}>
        It {reason === 'disconnect' ? 'stopped' : 'ran out of time'} before
        finishing. {links} {missing.length > 0 ? (
          <span>
            Not finished: {missing.join(', and ')}.
          </span>
        ) : null}{' '}
        Every count on this page is a minimum, not a final figure.
      </p>
    </div>
  )
}
