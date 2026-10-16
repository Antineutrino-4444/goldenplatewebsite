import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { fileURLToPath } from 'url'
import prebuiltMapbox from './build/mapbox-prebuilt.js'
import rootMapboxEnv from './build/root-mapbox-env.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(),tailwindcss(),rootMapboxEnv(path.resolve(__dirname, '..')),prebuiltMapbox()],
  worker: { format: 'es' },
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
