import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parsePodcastTranscript } from '../src/lib/podcast-transcript.js'

const supplied = readFileSync(new URL('../public/resources/golden-plate-podcast-transcript.txt', import.meta.url), 'utf8')

test('the reader preserves every speaking turn and spoken word in the supplied transcript', () => {
  const turns = parsePodcastTranscript(supplied)
  assert.equal(turns.length, supplied.match(/^\[\d{2}:\d{2}\]/gm).length)
  assert.equal(turns[0].time, '00:03')
  assert.equal(turns.at(-1).time, '23:18')
  const spoken = supplied.split('TRANSCRIPT\n==========')[1]
    .replace(/^\[\d{2}:\d{2}\] [A-Z][A-Z ]+\n/gm, '').replace(/\s+/g, ' ').trim()
  assert.equal(turns.flatMap((turn) => turn.paragraphs).join(' ').replace(/\s+/g, ' ').trim(), spoken)
})

test('quote links resolve to the right speaker and include their full context', () => {
  const turns = parsePodcastTranscript(supplied)
  for (const [id, speaker, quote] of [
    ['podcast-22-44', 'Jiajun (Leo) Li', 'Having the website streamline the entire process helped us a lot.'],
    ['podcast-06-41', 'Jiajun (Leo) Li', 'Our program is fully student-run.'],
    ['podcast-09-36', 'Shuoyou (Nick) Wang', 'We wanted to improve the efficiency of the process so more people could get involved.'],
    ['podcast-19-05', 'Michael Casey', 'So dive in, try things, and learn from what happens.'],
  ]) {
    const turn = turns.find((entry) => entry.id === id)
    assert.equal(turn.speaker, speaker)
    assert.ok(turn.paragraphs.join(' ').includes(quote))
  }
  assert.deepEqual(parsePodcastTranscript(supplied.replace(/\n/g, '\r\n')), turns)
})
