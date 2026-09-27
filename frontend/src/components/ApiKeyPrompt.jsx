import { useState } from 'react'
import { Link } from 'react-router-dom'

import { writeAnalysisKey } from '../api/apiKey'
import { useAnalysis } from '../context/AnalysisContext'
import styles from './ApiKeyPrompt.module.css'

// Shown instead of the error panel when the backend answers 401. A deployment that sets
// ANALYSIS_API_KEY is invite only, so this is the front door rather than a failure: the
// visitor is being asked for the code the operator gave them.
//
// The key is held in sessionStorage by `writeAnalysisKey`, never in component state, so a
// re-render cannot drop it and nothing persists it to disk. `run` is re-called with the
// title that was refused, because the analysis never happened - there is no result to
// restore and re-running is the only way to get one.
export default function ApiKeyPrompt() {
  const { title, run } = useAnalysis()
  const [value, setValue] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = (event) => {
    event.preventDefault()
    const key = writeAnalysisKey(value)
    if (!key) return
    setBusy(true)
    // The context owns the outcome: a wrong key comes back as 401 and the prompt is
    // rendered again, so this does not need its own error state.
    Promise.resolve(run(title)).finally(() => setBusy(false))
  }

  return (
    <form className={styles.prompt} onSubmit={submit}>
      <p className={styles.title}>This deployment needs an analysis key</p>
      <p className={styles.body}>
        Analyzing an article spends a shared budget of requests to Wikipedia, so this
        deployment is limited to people with a key. Ask whoever gave you the link, then
        paste it below. It is kept for this tab only.
      </p>

      <label className={styles.label}>
        Analysis key
        <input
          className={styles.input}
          type="password"
          value={value}
          autoComplete="off"
          autoFocus
          onChange={(event) => setValue(event.target.value)}
        />
      </label>

      <div className={styles.actions}>
        <button
          className={styles.primary}
          type="submit"
          disabled={busy || value.trim() === ''}
        >
          {busy ? 'Checking...' : 'Unlock'}
        </button>
        <Link className={styles.secondary} to="/">
          Cancel
        </Link>
      </div>
    </form>
  )
}
