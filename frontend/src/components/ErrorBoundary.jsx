import { Component } from 'react'

import { ErrorMessage } from './ui'
import styles from './ErrorBoundary.module.css'

/**
 * Catches a render-time throw anywhere below it.
 *
 * Without this, any error during render unmounts the whole tree and the user gets a blank
 * white page with no explanation - which is what a non-technical visitor sees when a
 * component hits a null it did not expect. It has to be a class: React has no hook form
 * of an error boundary.
 *
 * `ErrorMessage` does the presenting, so a render failure looks like every other failure
 * in the app and there is one visual language for "this did not work". It also carries
 * `role="alert"`, which is why this component does not add one of its own - nesting two
 * would make a screen reader announce the failure twice.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null, retried: false }
    this.handleRetry = this.handleRetry.bind(this)
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // Kept deliberately: a render error that never reaches the console is
    // indistinguishable from a page that simply failed to load.
    console.error('Unhandled render error', error, info?.componentStack)
  }

  handleRetry() {
    this.setState({ error: null, retried: true })
  }

  render() {
    const { error, retried } = this.state
    if (!error) return this.props.children

    return (
      <div className={styles.screen}>
        {/*
          The retry is offered once. If it throws the same error again, a second identical
          button only invites the user to keep clicking something that cannot work, so
          the link out is the remaining way forward.
        */}
        <ErrorMessage error={error} onRetry={retried ? undefined : this.handleRetry} />
        <a className={styles.reload} href="/">
          Back to the start
        </a>
      </div>
    )
  }
}
