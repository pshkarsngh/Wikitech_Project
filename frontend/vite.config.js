import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Backend the dev server proxies /api to. Override if the backend runs elsewhere:
//   VITE_API_PROXY_TARGET=http://127.0.0.1:8123 npm run dev
const apiTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  build: {
    // 0 disables inlining small assets as data: URIs. A CSP then never has to allow
    // `data:` in script-src, and it removes the mechanism CVE-2025-31486 used to walk
    // around server.fs.deny through the inline-limit path.
    assetsInlineLimit: 0,
  },

  server: {
    port: 5173,

    // Loopback only, and stated rather than left to default. Every Vite dev-server file
    // disclosure this year needed the server reachable from the network (`--host` or
    // server.host), and there is an active mass-scanning campaign exploiting exactly that
    // against internet-exposed instances - F5 counted 800 attacks and 32,000 raw events in
    // a month, pulling .env files, AWS and Azure credentials, Terraform state,
    // /proc/self/environ and /etc/passwd. The dev server must never be the reason this
    // machine's secrets are readable by a stranger.
    host: '127.0.0.1',

    // Lets the frontend call the API at /api without CORS in development.
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
    },

    // CVE-2025-24010: Vite's dev server used to answer any origin with
    // `Access-Control-Allow-Origin: *` and to skip Origin validation on its HMR
    // WebSocket, so any page a developer visited could read the dev server's responses
    // and open a socket to it. The package fix is in, but an explicit allow-list means a
    // regression upstream cannot silently reopen it, and it documents who is meant to be
    // able to talk to this server at all.
    cors: {
      origin: ['http://localhost:5173', 'http://127.0.0.1:5173'],
    },

    fs: {
      // Refuse anything outside this project root rather than serving it because it was
      // reachable. The default deny list covers .env and certificates; these are the
      // rest of the things that are secret and have no business being served.
      strict: true,
      deny: [
        '.env',
        '.env.*',
        '*.{crt,pem,key,p12,pfx}',
        '**/.git/**',
        '**/.ssh/**',
        '**/.aws/**',
        '**/.azure/**',
        '**/*.tfstate',
        '**/*.tfvars',
        '**/secrets.*',
      ],
    },
  },
})
