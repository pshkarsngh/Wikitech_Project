import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Backend the dev server proxies /api to. Override if the backend runs elsewhere:
//   VITE_API_PROXY_TARGET=http://127.0.0.1:8123 npm run dev
const apiTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Lets the frontend call the API at /api without CORS in development.
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
})
