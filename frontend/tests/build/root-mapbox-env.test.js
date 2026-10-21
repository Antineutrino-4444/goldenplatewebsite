import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, realpath, writeFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { build } from 'vite'
import rootMapboxEnv from '../../build/root-mapbox-env.js'

const tokenName = 'VITE_MAPBOX_ACCESS_TOKEN'

async function compileEnvironment(files, exportedToken) {
  const directory = await realpath(await mkdtemp(path.join(tmpdir(), 'goldenplate-env-test-')))
  const previousToken = process.env[tokenName]
  try {
    if (exportedToken === undefined) delete process.env[tokenName]
    else process.env[tokenName] = exportedToken
    const frontend = path.join(directory, 'frontend')
    await mkdir(frontend)
    await writeFile(path.join(frontend, '.env'), 'VITE_MAPBOX_ACCESS_TOKEN=pk.frontend.signature\nVITE_TURNSTILE_SITE_KEY=frontend-captcha\n')
    for (const [filename, content] of Object.entries(files)) {
      await writeFile(path.join(directory, filename), content)
    }
    await writeFile(path.join(frontend, 'index.html'), '<script type="module" src="/main.js"></script>')
    await writeFile(path.join(frontend, 'main.js'), `document.body.textContent = JSON.stringify({
      mapbox: import.meta.env.VITE_MAPBOX_ACCESS_TOKEN,
      captcha: import.meta.env.VITE_TURNSTILE_SITE_KEY,
      secret: import.meta.env.SECRET_KEY,
      environment: import.meta.env,
    })`)
    const result = await build({
      configFile: false, root: frontend, mode: 'production', logLevel: 'silent',
      plugins: [rootMapboxEnv(directory)],
      build: { write: false, minify: false },
    })
    return result.output.filter((entry) => entry.type === 'chunk').map((entry) => entry.code).join('\n')
  } finally {
    if (previousToken === undefined) delete process.env[tokenName]
    else process.env[tokenName] = previousToken
    await rm(directory, { recursive: true, force: true })
  }
}

test('root public Mapbox token reaches the bundle without backend secrets or changes to frontend Turnstile', async () => {
  const code = await compileEnvironment({
    '.env': 'VITE_MAPBOX_ACCESS_TOKEN=pk.root.signature\nSECRET_KEY=backend-secret-fixture\nBREVO_API_KEY=brevo-secret-fixture\nTURNSTILE_SECRET_KEY=captcha-secret-fixture\nVITE_TURNSTILE_SITE_KEY=root-captcha\n',
  })
  assert.ok(code.includes('mapbox: "pk.root.signature"'))
  assert.ok(!code.includes('pk.frontend.signature'))
  assert.ok(code.includes('captcha: "frontend-captcha"'))
  for (const value of ['backend-secret-fixture', 'brevo-secret-fixture', 'captcha-secret-fixture', 'root-captcha']) {
    assert.ok(!code.includes(value), `${value} must not reach the browser`)
  }
})

test('frontend token remains the fallback when root files omit the variable', async () => {
  const code = await compileEnvironment({ '.env': 'SECRET_KEY=backend-secret-fixture\n' })
  assert.ok(code.includes('mapbox: "pk.frontend.signature"'))
})

test('an explicitly empty root token disables the frontend fallback', async () => {
  const code = await compileEnvironment({ '.env': 'VITE_MAPBOX_ACCESS_TOKEN=\n' })
  assert.ok(code.includes('mapbox: ""'))
  assert.ok(!code.includes('pk.frontend.signature'))
})

test('exported build token overrides the root file', async () => {
  const code = await compileEnvironment({ '.env': 'VITE_MAPBOX_ACCESS_TOKEN=pk.root.signature\n' }, 'pk.exported.signature')
  assert.ok(code.includes('mapbox: "pk.exported.signature"'))
})

test('root mode-specific local files follow Vite environment precedence', async () => {
  const code = await compileEnvironment({
    '.env': 'VITE_MAPBOX_ACCESS_TOKEN=pk.root.signature\n',
    '.env.local': 'VITE_MAPBOX_ACCESS_TOKEN=pk.local.signature\n',
    '.env.production': 'VITE_MAPBOX_ACCESS_TOKEN=pk.production.signature\n',
    '.env.production.local': 'VITE_MAPBOX_ACCESS_TOKEN=pk.productionLocal.signature\n',
  })
  assert.ok(code.includes('mapbox: "pk.productionLocal.signature"'))
})
