import test from 'node:test'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import React from 'react'
import { renderToString } from 'react-dom/server'
import { createServer } from 'vite'

test('the recorder submits one unnamed dirty plate without dialogs only when the school disables name input', async (t) => {
  // Render the real hook without mounting effects, so no auth polling or real API
  // requests run. Render-phase updates let us inspect the resulting dialog state.
  const server = await createServer({
    configFile: false,
    root: fileURLToPath(new URL('..', import.meta.url)),
    resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
    server: { middlewareMode: true, ws: false },
    optimizeDeps: { noDiscovery: true, include: [] },
  })
  const timers = []
  const originalTimeout = globalThis.setTimeout
  t.mock.method(globalThis, 'setTimeout', (...args) => {
    const timer = originalTimeout(...args)
    timers.push(timer)
    return timer
  })
  try {
    const { usePlateApp } = await server.ssrLoadModule('/src/hooks/usePlateApp.js')
    for (const [enabled, category, dialog] of [
      [false, 'dirty', null], [true, 'dirty', 'showDirtyDialog'],
      [undefined, 'dirty', 'showDirtyDialog'], [false, 'clean', 'showCleanDialog'],
      [false, 'red', 'showRedDialog'], [false, 'faculty', 'showFacultyDialog'],
    ]) {
      const requests = []
      let releaseSave
      const pendingSave = new Promise(resolve => { releaseSave = resolve })
      const fetchMock = t.mock.method(globalThis, 'fetch', async (url, options) => {
        requests.push({ url, options })
        if (url === '/api/record/dirty') return pendingSave
        return { ok: true, json: async () => ({ names: [], teacher_names: [] }) }
      })
      let result, clicked = false
      function Recorder() {
        const app = usePlateApp()
        if (!app.user) app.setUser({
          id: 'test-recorder', role: 'user', school_id: 'test-school',
          school: { dirty_plate_name_input_enabled: enabled },
        })
        else if (!clicked) { clicked = true; app.handleCategoryClick(category) }
        result = app
        return null
      }
      renderToString(React.createElement(Recorder))
      for (const name of ['showCleanDialog', 'showDirtyDialog', 'showRedDialog', 'showFacultyDialog']) {
        assert.equal(result[name], name === dialog, `${category}, input ${enabled}: ${name}`)
      }
      if (category === 'dirty' && enabled === false) {
        assert.equal(requests.length, 1)
        assert.equal(requests[0].url, '/api/record/dirty')
        assert.deepEqual(JSON.parse(requests[0].options.body), { input_value: '' })
        result.handleCategoryClick('dirty')
        assert.equal(requests.length, 1, 'an in-flight double-click must not submit twice')
        releaseSave({ ok: true, json: async () => ({
          status: 'success', is_count_only: true, display_name: 'Dirty plate (count only)',
        }) })
        await new Promise(resolve => setImmediate(resolve))
      } else assert.equal(requests.length, 0, 'name-entry modes must wait for input submission')
      fetchMock.mock.restore()
    }
  } finally {
    timers.forEach(clearTimeout)
    await server.close()
  }
})
