import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, readFile, readdir, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const frontend = fileURLToPath(new URL('../../', import.meta.url))

test('production builds fit a small heap and retain every prebuilt Mapbox module and worker', { timeout: 60000 }, async () => {
  const outDir = await mkdtemp(path.join(tmpdir(), 'goldenplate-build-test-'))
  try {
    const build = spawnSync(process.execPath, [
      '--max-old-space-size=384', path.join(frontend, 'node_modules/vite/bin/vite.js'),
      'build', '--outDir', outDir,
    ], {
      cwd: frontend, encoding: 'utf8', timeout: 55000,
      env: { ...process.env, NODE_OPTIONS: '' },
    })
    assert.equal(build.status, 0, `${build.error || ''}\n${build.stderr}\n${build.stdout}`)

    const packageDir = path.join(frontend, 'node_modules/mapbox-gl')
    const { version } = JSON.parse(await readFile(path.join(packageDir, 'package.json'), 'utf8'))
    const distribution = path.join(packageDir, 'dist/esm')
    const vendorDirectory = `mapbox-gl-${version}`
    for (const filename of await readdir(distribution)) {
      if (!filename.endsWith('.js')) continue
      const expected = (await readFile(path.join(distribution, filename), 'utf8'))
        .replace(/\/\/# sourceMappingURL=.*?(?:\r?\n)?$/, '')
      const actual = await readFile(path.join(outDir, 'assets', vendorDirectory, filename), 'utf8')
      assert.equal(actual, expected, `${filename} must remain compatible with Mapbox's module graph`)
    }
    const chunks = await readdir(path.join(outDir, 'assets'))
    for (const component of ['WorldMap-', 'SchoolFlightMap-']) {
      const filename = chunks.find((name) => name.startsWith(component) && name.endsWith('.js'))
      assert.ok(filename, `${component} chunk is emitted`)
      const source = await readFile(path.join(outDir, 'assets', filename), 'utf8')
      assert.ok(source.includes(`/assets/${vendorDirectory}/mapbox-gl.js`), `${component} loads the self-hosted Mapbox entry`)
    }
  } finally {
    await rm(outDir, { recursive: true, force: true })
  }
})
