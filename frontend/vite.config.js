import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { fileURLToPath } from 'url'
import prebuiltMapbox from './build/mapbox-prebuilt.js'
import rootMapboxEnv from './build/root-mapbox-env.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

function serveLegalPages(server) {
  server.middlewares.use((req, res, next) => {
    if (req.method === 'GET' || req.method === 'HEAD') {
      req.url = req.url.replace(/^\/(privacy|terms)\/?(?=\?|$)/, '/$1.html')
    }
    next()
  })
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(), tailwindcss(), rootMapboxEnv(path.resolve(__dirname, '..')), prebuiltMapbox(),
    { name: 'legal-page-urls', configureServer: serveLegalPages, configurePreviewServer: serveLegalPages },
  ],
  worker: { format: 'es' },
  // Preserve Mapbox's module-relative worker URLs in development. Prebundling
  // moves the entry into .vite/deps without its sibling worker modules.
  optimizeDeps: { exclude: ['mapbox-gl/esm'] },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: path.resolve(__dirname, '../src/static'),
    emptyOutDir: true,
    copyPublicDir: true,
  },
})
