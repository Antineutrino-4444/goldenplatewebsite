import test from 'node:test'
import assert from 'node:assert/strict'
import { leaderboardPage, normalizeLeaderboardSearch } from '../src/lib/leaderboard.js'

const rows = Array.from({ length: 103 }, (_, index) => ({ display_name: `Student ${index + 1}` }))

test('jumping to a page retains school-wide ranks and shows podium entries only on the first page', () => {
  const first = leaderboardPage(rows, '', 1)
  assert.equal(first.pageCount, 3)
  assert.equal(first.visible.length, 50)
  assert.equal(first.visible[0].rank, 1)
  assert.equal(leaderboardPage(rows, '', 2).visible[0].rank, 51)
  assert.deepEqual(leaderboardPage(rows, '', 3).visible.map(({ rank }) => rank), [101, 102, 103])
})

test('search covers every page and preserves ranks for duplicate names and visible IDs', () => {
  const roster = [...rows,
    { display_name: 'Alex Smith', student_identifier: 'ID-104' },
    { display_name: 'Alex Smith', student_identifier: 'ID-105' },
  ]
  const names = leaderboardPage(roster, normalizeLeaderboardSearch(' ALEX   smith '), 3)
  assert.equal(names.currentPage, 1)
  assert.equal(names.matchCount, 2)
  assert.deepEqual(names.visible.map(({ rank }) => rank), [104, 105])
  assert.equal(leaderboardPage(roster, 'id-105', 1).visible[0].rank, 105)
  assert.equal(leaderboardPage(roster, 'no match', 1).matchCount, 0)
})
