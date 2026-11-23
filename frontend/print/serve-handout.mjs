// Start only the Vite print entry. The exporter owns this loopback server.
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { createServer } from 'vite'
import react from '@vitejs/plugin-react'

const root = fileURLToPath(new URL('../', import.meta.url))
const temporaryDirectory = process.argv[2]
const server = await createServer({
  root,
  configFile: false,
  envDir: temporaryDirectory,
  cacheDir: path.join(temporaryDirectory, 'vite-cache'),
  plugins: [react()],
  resolve: { alias: { '@': path.join(root, 'src') } },
  optimizeDeps: { entries: ['print/school-overview/index.html'] },
  server: { host: '127.0.0.1', port: 0, hmr: false },
  logLevel: 'error',
})
await server.listen()
console.log('http://127.0.0.1:' + server.httpServer.address().port)
process.on('SIGTERM', async () => { await server.close(); process.exit(0) })
