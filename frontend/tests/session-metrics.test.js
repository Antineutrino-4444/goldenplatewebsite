import assert from 'node:assert/strict'
import test from 'node:test'
import { dashboardMetrics } from '../src/lib/session-metrics.js'

test('dashboard clean rate includes faculty, dirty rate includes very dirty plates', () => {
  const stats = dashboardMetrics({ clean_count: 7, faculty_clean_count: 2, dirty_count: 2, red_count: 1,
    combined_dirty_count: 3, total_recorded: 12 })
  assert.equal(stats.totalRecorded, 12)
  assert.equal(stats.cleanCount, 9)
  assert.equal(stats.combinedDirty, 3)
  assert.equal(stats.cleanPercentage, 75)
  assert.equal(stats.dirtyPercentage, 25)
})

test('empty sessions have zero rates instead of NaN', () => {
  const stats = dashboardMetrics()
  assert.equal(stats.totalRecorded, 0)
  assert.equal(stats.cleanPercentage, 0)
  assert.equal(stats.dirtyPercentage, 0)
})
