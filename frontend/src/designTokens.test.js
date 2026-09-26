/**
 * Design-token contract.
 *
 * A palette migration once removed six custom properties that component CSS
 * still referenced, which silently stripped the colour from the EXISTS and
 * MISSING badges. Nothing failed: the build passed and the tests passed,
 * because no test looked at the stylesheet. These assertions are that look.
 */

import { readFileSync, readdirSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

// Vitest runs with the directory holding vitest.config.js as the cwd, and
// jsdom does not give import.meta.url a file: scheme to resolve against. The
// scan is rooted at src so it never walks into node_modules or dist.
const SRC = join(process.cwd(), 'src')
const TOKENS = join(SRC, 'index.css')

const SOURCE_EXTENSIONS = new Set(['.css', '.jsx', '.js'])

function sourceFiles(dir) {
  const found = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name)
    if (entry.isDirectory()) {
      found.push(...sourceFiles(full))
    } else if (SOURCE_EXTENSIONS.has(entry.name.slice(entry.name.lastIndexOf('.')))) {
      found.push(full)
    }
  }
  return found
}
function definedTokens(css) {
  return new Set([...css.matchAll(/(--[\w-]+)\s*:/g)].map((match) => match[1]))
}

function referencedTokens(css) {
  return new Set([...css.matchAll(/var\(\s*(--[\w-]+)/g)].map((match) => match[1]))
}

describe('design tokens', () => {
  const tokensCss = readFileSync(TOKENS, 'utf8')
  const defined = definedTokens(tokensCss)
  const files = sourceFiles(SRC)

  it('finds source files to check', () => {
    expect(files.length).toBeGreaterThan(10)
  })

  it('defines the palette the status badges depend on', () => {
    // The three connection states each need a hue and a soft companion; without
    // them the connection lists and the map legend render unstyled.
    for (const token of [
      '--missing',
      '--missing-soft',
      '--oneway',
      '--mutual',
      '--mutual-soft',
      '--accent',
    ]) {
      expect(defined, `${token} is not defined in index.css`).toContain(token)
    }
  })

  it('resolves every custom property referenced in source', () => {
    const unresolved = []
    for (const file of files) {
      const referenced = referencedTokens(readFileSync(file, 'utf8'))
      for (const token of referenced) {
        if (!defined.has(token)) {
          unresolved.push(`${relative(SRC, file)} -> ${token}`)
        }
      }
    }
    expect(unresolved).toEqual([])
  })
})
