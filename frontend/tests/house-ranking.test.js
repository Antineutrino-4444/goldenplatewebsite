import test from 'node:test'
import assert from 'node:assert/strict'
import { compareHouses } from '../src/lib/house-ranking.js'

const houses = [
  { house: 'A', score: -4, total_count: 4, clean_rate: 75 },
  { house: 'B', score: 2, total_count: 1, clean_rate: 100 },
  { house: 'C', score: -2, total_count: 1, clean_rate: 0 },
  { house: 'D', score: -10, total_count: 1, clean_rate: 0 },
]

test('score ranks rewards and deductions independently of volume and clean rate', () => {
  assert.deepEqual(houses.slice().sort((a, b) => compareHouses(a, b, 'score')).map((h) => h.house), ['B', 'C', 'A', 'D'])
})

test('count and clean rate tabs retain their ranking rules', () => {
  assert.deepEqual(houses.slice().sort((a, b) => compareHouses(a, b, 'count')).map((h) => h.house), ['A', 'B', 'C', 'D'])
  assert.deepEqual(houses.slice().sort((a, b) => compareHouses(a, b, 'percentage')).map((h) => h.house), ['B', 'A', 'C', 'D'])
})

test('equal scores including zero use a stable alphabetical order', () => {
  const tied = houses.map((h) => ({ ...h, score: 0 })).reverse()
  assert.deepEqual(tied.sort((a, b) => compareHouses(a, b, 'score')).map((h) => h.house), ['A', 'B', 'C', 'D'])
})
