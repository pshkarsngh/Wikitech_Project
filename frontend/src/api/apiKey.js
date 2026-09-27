// The shared analysis key, held for the tab and not for the browser.
//
// sessionStorage, not localStorage: a deployment that sets ANALYSIS_API_KEY is invite
// only, and the key is a shared secret between the operator and whoever they gave it to.
// Keeping it in localStorage would outlive the tab on a shared machine, which is the
// difference between a code someone typed and a code the next person inherits.
//
// Every read and write is guarded because sessionStorage throws rather than degrades in
// two real situations: a sandboxed iframe without `allow-same-origin`, and Safari's
// private mode on older versions. Neither should turn into a blank page, so a key that
// cannot be stored is simply a key the visitor has to paste again.

const STORAGE_KEY = 'wikitech.analysisApiKey'

function storage() {
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

export function readAnalysisKey() {
  try {
    return storage()?.getItem(STORAGE_KEY) ?? ''
  } catch {
    return ''
  }
}

export function writeAnalysisKey(key) {
  const value = String(key ?? '').trim()
  const store = storage()
  if (!store) return value
  try {
    if (value) {
      store.setItem(STORAGE_KEY, value)
    } else {
      store.removeItem(STORAGE_KEY)
    }
  } catch {
    // Nothing to do: the key is still returned so the caller can use it for this request.
  }
  return value
}

export function clearAnalysisKey() {
  const store = storage()
  if (!store) return
  try {
    store.removeItem(STORAGE_KEY)
  } catch {
    // See writeAnalysisKey.
  }
}
