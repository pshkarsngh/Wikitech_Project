import { Link, NavLink } from 'react-router-dom'

import styles from './Layout.module.css'

const NAV_ITEMS = [
  { to: '/', label: 'Home', end: true },
  { to: '/search', label: 'Search' },
  { to: '/analyze', label: 'Analysis' },
  { to: '/missing-connections', label: 'Missing Connections' },
  { to: '/one-way-connections', label: 'One-Way Connections' },
  { to: '/connection-map', label: 'Connection Map' },
]

export default function Layout({ children }) {
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <Link className={styles.brand} to="/">
            <span className={styles.brandMark} aria-hidden="true" />
            <span className={styles.brandText}>
              Find the <strong>Missing</strong> Connections
            </span>
          </Link>
          <nav className={styles.nav} aria-label="Main">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className={styles.main}>{children}</main>

      <footer className={styles.footer}>
        <p>
          Article data from Wikipedia via the MediaWiki API. Built with free and
          open source software.
        </p>
      </footer>
    </div>
  )
}
