import { readFileSync, readdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'

const require = createRequire(import.meta.url)
const packagePath = require.resolve('mapbox-gl/package.json')
const { version } = JSON.parse(readFileSync(packagePath, 'utf8'))
const distribution = path.join(path.dirname(packagePath), 'dist/esm')

// Mapbox ships minified ESM with relative imports for its styles and workers.
// Serve that module graph directly instead of parsing and bundling it again.
export default function prebuiltMapbox() {
  let assetDirectory
  let moduleUrl
  return {
    name: 'prebuilt-mapbox',
    apply: 'build',
    enforce: 'pre',
    configResolved(config) {
      assetDirectory = path.posix.join(config.build.assetsDir, `mapbox-gl-${version}`)
      moduleUrl = `${config.base}${assetDirectory}/mapbox-gl.js`
    },
    resolveId(source) {
      if (source === 'mapbox-gl/esm') return { id: moduleUrl, external: 'absolute' }
    },
    buildStart() {
      for (const filename of readdirSync(distribution)) {
        if (!filename.endsWith('.js')) continue
        const source = readFileSync(path.join(distribution, filename), 'utf8')
          .replace(/\/\/# sourceMappingURL=.*?(?:\r?\n)?$/, '')
        this.emitFile({ type: 'asset', fileName: `${assetDirectory}/${filename}`, source })
      }
    },
  }
}
