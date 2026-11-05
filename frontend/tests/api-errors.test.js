import test from 'node:test'
import assert from 'node:assert/strict'
import { readApiJson } from '../src/lib/api-errors.js'
import { submitRecordRequest } from '../src/lib/record-submission.js'

test('failed API responses display their error code and reference', async () => {
  const payload = { error: 'record_save_failed', message: 'The database is busy.', error_code: 'RECORD_DB_BUSY', error_reference: 'AB1234CD5678' }
  const response = () => Response.json(payload, { status: 503 })
  const expected = 'The database is busy. [RECORD_DB_BUSY] Ref AB1234CD5678'
  assert.equal((await readApiJson(response())).error, expected)
  await assert.rejects(submitRecordRequest('clean', {}, async () => response()), { message: expected })
})

test('an upstream HTML error shows the HTTP code without displaying the response body', async () => {
  const response = new Response('<h1>Gateway error</h1>', { status: 502 })
  assert.equal((await readApiJson(response)).error, 'The request failed. Please try again. [HTTP_502]')
})

test('a gateway error after submitting a plate directs the recorder to history', async () => {
  const reply = async () => Response.json({ error: 'Bad Gateway' }, { status: 502 })
  await assert.rejects(submitRecordRequest('clean', {}, reply), /Check Plate Tracking History.*\[RECORD_HTTP_502\]/)
})
