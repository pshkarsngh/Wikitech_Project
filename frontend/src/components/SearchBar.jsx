import { useEffect, useRef, useState } from 'react'

import { searchArticles } from '../api/client'
import styles from './SearchBar.module.css'

const DEBOUNCE_MS = 300

export default function SearchBar({
  onAnalyze,
  autoFocus = false,
  initialValue = '',
  size = 'large',
  disabled = false,
  submitLabel = 'Analyze',
}) {
  const [query, setQuery] = useState(initialValue)
  const [suggestions, setSuggestions] = useState([])
  const [open, setOpen] = useState(false)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState(null)
  const [activeIndex, setActiveIndex] = useState(-1)
  const containerRef = useRef(null)

  useEffect(() => {
    setQuery(initialValue)
  }, [initialValue])

  useEffect(() => {
    function handleClickOutside(event) {
      if (!containerRef.current?.contains(event.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    const trimmed = query.trim()
    if (trimmed.length < 2) {
      setSuggestions([])
      setSearching(false)
      return undefined
    }

    const controller = new AbortController()
    setSearching(true)
    const timer = setTimeout(async () => {
      try {
        const data = await searchArticles(trimmed, 8, { signal: controller.signal })
        setSuggestions(data.results)
        setError(null)
      } catch (cause) {
        if (cause.name !== 'AbortError') setError(cause.message)
      } finally {
        setSearching(false)
      }
    }, DEBOUNCE_MS)

    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [query])

  function choose(title) {
    setQuery(title)
    setSuggestions([])
    setOpen(false)
    setActiveIndex(-1)
    onAnalyze?.(title)
  }

  function handleSubmit(event) {
    event.preventDefault()
    const highlighted = suggestions[activeIndex]
    choose(highlighted ? highlighted.title : query)
  }

  function handleKeyDown(event) {
    if (!open || suggestions.length === 0) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((index) => (index + 1) % suggestions.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((index) => (index - 1 + suggestions.length) % suggestions.length)
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className={styles.wrapper} ref={containerRef}>
      <form
        className={`${styles.form} ${styles[size] ?? ''}`}
        onSubmit={handleSubmit}
        role="search"
      >
        <input
          className={styles.input}
          type="search"
          value={query}
          placeholder="Search Wikipedia, e.g. Ada Lovelace"
          aria-label="Article name"
          autoComplete="off"
          autoFocus={autoFocus}
          disabled={disabled}
          onChange={(event) => {
            setQuery(event.target.value)
            setOpen(true)
            setActiveIndex(-1)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
        />
        <button className={styles.button} type="submit" disabled={disabled}>
          {disabled ? `${submitLabel}...` : submitLabel}
        </button>
      </form>

      {open && (query.trim().length >= 2 || suggestions.length > 0) && (
        <div className={styles.suggestions}>
          {searching && suggestions.length === 0 && (
            <div className={styles.hint}>Searching...</div>
          )}
          {!searching && error && <div className={styles.hint}>{error}</div>}
          {!searching && !error && suggestions.length === 0 && (
            <div className={styles.hint}>No matching articles yet.</div>
          )}
          <ul className={styles.list} role="listbox">
            {suggestions.map((item, index) => (
              <li key={item.page_id ?? item.title}>
                <button
                  type="button"
                  className={`${styles.option} ${
                    index === activeIndex ? styles.active : ''
                  }`}
                  role="option"
                  aria-selected={index === activeIndex}
                  onClick={() => choose(item.title)}
                >
                  <span className={styles.optionTitle}>{item.title}</span>
                  {item.description && (
                    <span className={styles.optionDescription}>{item.description}</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
