import test from 'node:test'
import assert from 'node:assert/strict'
import { recordSuccessMessage, submitRecordRequest } from '../src/lib/record-submission.js'

const reply = (data, ok = true) => async () => ({ ok, json: async () => data })

test('a confirmed save reports category, count-only and manual matches accurately', async () => {
  const data = await submitRecordRequest('red', { input_value: '123' }, reply({ status: 'success', preferred_name: 'Alex', last_name: 'Doe' }))
  assert.equal(recordSuccessMessage('red', data), 'Alex Doe recorded as VERY DIRTY.')
  assert.match(recordSuccessMessage('dirty', { ...data, is_manual_entry: true }), /manual entry without a unique roster match/)
  assert.equal(recordSuccessMessage('clean', { is_count_only: true, display_name: 'Clean plate (count only)' }), 'Clean plate (count only) recorded')
  assert.doesNotMatch(recordSuccessMessage('faculty', { ...data, is_manual_entry: true }), /roster/)
})

test('duplicate and save-failure responses use descriptive server feedback', async () => {
  for (const error of ['duplicate', 'record_save_failed']) {
    await assert.rejects(submitRecordRequest('clean', {}, reply({ error, message: 'Specific explanation' }, false)), { message: 'Specific explanation' })
  }
})

test('a lost or unreadable success response directs users to history before retrying', async () => {
  for (const fetcher of [async () => { throw new Error('offline') }, async () => ({ json: async () => { throw new Error('invalid JSON') } }), reply({}), reply(null)]) {
    await assert.rejects(submitRecordRequest('clean', {}, fetcher), /Check Plate Tracking History before trying again/)
  }
})
