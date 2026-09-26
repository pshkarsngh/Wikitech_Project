import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Kept separate from vite.config.js: that file owns the dev server and the /api
// proxy, and nothing a test run needs should be able to change how it serves.
// https://vitest.dev/config/
export default defineConfig({
  plugins: [react()],
  // The test files are .jsx but import nothing from React, so the automatic
  // runtime has to be requested explicitly or the classic transform looks for a
  // React binding that is not in scope.
  esbuild: { jsx: 'automatic' },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{js,jsx}'],
  },
})
