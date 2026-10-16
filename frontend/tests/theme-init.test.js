import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { runInNewContext } from 'node:vm'

const bootstrap = await readFile(new URL('../public/theme-init.js', import.meta.url), 'utf8')
function initialTheme(preference, deviceDark, storageBlocked = false) {
  const root = { classList: { toggle(name, active) { root[name] = active } }, style: {} }
  runInNewContext(bootstrap, {
    localStorage: { getItem: () => { if (storageBlocked) throw new Error('Storage unavailable'); return preference }, removeItem: () => {} },
    matchMedia: () => ({ matches: deviceDark }),
    document: { documentElement: root },
  })
  return { dark: root.dark, colorScheme: root.style.colorScheme }
}
test('first paint follows the device when no theme is saved', () => {
  assert.deepEqual(initialTheme(null, true), { dark: true, colorScheme: 'dark' })
  assert.deepEqual(initialTheme(null, false), { dark: false, colorScheme: 'light' })
  assert.deepEqual(initialTheme('system', true), { dark: true, colorScheme: 'dark' })
})
test('explicit saved choices override the device before the app loads', () => {
  assert.deepEqual(initialTheme('dark', false), { dark: true, colorScheme: 'dark' })
  assert.deepEqual(initialTheme('light', true), { dark: false, colorScheme: 'light' })
})
test('blocked or invalid storage still produces a usable device-based theme', () => {
  assert.deepEqual(initialTheme(null, true, true), { dark: true, colorScheme: 'dark' })
  assert.deepEqual(initialTheme('old-invalid-theme', true), { dark: true, colorScheme: 'dark' })
})
