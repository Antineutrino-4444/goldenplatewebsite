import assert from 'node:assert/strict'
import test from 'node:test'
import { makeSchoolPost, postPlatforms, postTemplates, schoolPostDestination } from '../src/lib/school-posts.js'

test('every platform and template opens with a ready-to-edit caption and no unfilled markers', () => {
  for (const platform of Object.keys(postPlatforms)) {
    for (const template of Object.keys(postTemplates)) {
      assert.ok(postTemplates[template].fields.includes('school'))
      const text = makeSchoolPost(template, platform, {})
      assert.match(text, /Golden Plate|clean plates/i)
      assert.doesNotMatch(text, /\[|\]|undefined|NaN| {2}/)
      assert.ok(text.length > 20 && text.length <= 280)
    }
  }
})

test('filled-in captions reuse school and date and keep the wording specific to each template', () => {
  const details = { school: ' Evergreen ', winner: 'Morgan', reward: 'Morgan chose the lunch menu!', date: 'Friday', place: 'the garden café', count: '12' }
  assert.ok(postTemplates.winner.fields.includes('date'))
  for (const platform of Object.keys(postPlatforms)) {
    const win = makeSchoolPost('winner', platform, details)
    assert.match(win, /Morgan, our Golden Plate winner at Evergreen on Friday! Morgan chose the lunch menu!/)
    assert.doesNotMatch(win, /garden|12/)
  }
  const launch = makeSchoolPost('launch', 'facebook', details)
  assert.match(launch, /at Evergreen on Friday! Look for our student team at the garden café\./)
  assert.doesNotMatch(launch, /Morgan|12|\n/)
  const results = makeSchoolPost('results', 'bluesky', details)
  assert.match(results, /12 clean plates at Evergreen on Friday/)
  assert.doesNotMatch(results, /Morgan|garden/)
  assert.match(makeSchoolPost('results', 'x', { count: '0' }), /0 clean plates/)
  assert.match(makeSchoolPost('results', 'x', { count: '1' }), /1 clean plate at lunch/)
  assert.doesNotMatch(makeSchoolPost('results', 'x', { count: '-3' }), /-3/)
})

test('only native composer URLs receive caption text and preserve punctuation, Unicode and line breaks', () => {
  const caption = 'Jo & Lee #GoldenPlate\nCafé 🥇 + 70%?'
  for (const platform of ['x', 'bluesky']) {
    const url = new URL(schoolPostDestination(platform, caption))
    assert.equal(url.searchParams.get('text'), caption)
    assert.equal(url.origin + url.pathname, postPlatforms[platform].composer)
    assert.equal(url.hash, '')
  }
  for (const platform of ['instagram', 'facebook']) {
    assert.equal(schoolPostDestination(platform, caption), postPlatforms[platform].home)
  }
})
