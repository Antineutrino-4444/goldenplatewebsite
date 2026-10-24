import test from 'node:test'
import assert from 'node:assert/strict'
import { emailReminderKey, needsEmailReminder } from '../src/lib/account-email-reminder.js'

const user = { id: 'new-admin', role: 'superadmin', email: 'signup@example.com', email_verified: true, last_login_at: 'first-login' }
const emptyStorage = { getItem: () => null }

test('first login offers to keep or change an already verified signup email', () => {
  assert.equal(needsEmailReminder({ ...user, signup_email_confirmation: true }, emptyStorage), true)
  assert.equal(needsEmailReminder(user, emptyStorage), false)
  assert.equal(needsEmailReminder({ ...user, email_verified: false }, emptyStorage), true)
  assert.equal(needsEmailReminder({ ...user, email: '' }, emptyStorage), true)
})

test('dismissing the prompt survives remounts and reloads in the same login', () => {
  const firstLogin = { ...user, signup_email_confirmation: true }
  const dismissed = new Map([[emailReminderKey(firstLogin), 'dismissed']])
  const storage = { getItem: (key) => dismissed.get(key) }
  assert.equal(needsEmailReminder(firstLogin, storage), false)
  assert.equal(needsEmailReminder({ ...user, last_login_at: 'later-login' }, storage), false)
})

test('other roles never get the superadmin reminder and unavailable storage is safe', () => {
  for (const role of ['user', 'admin', 'inter_school', 'guest']) {
    assert.equal(needsEmailReminder({ ...user, role, signup_email_confirmation: true }, emptyStorage), false)
  }
  assert.equal(needsEmailReminder(null, emptyStorage), false)
  const blockedStorage = { getItem: () => { throw new Error('Storage unavailable') } }
  assert.equal(needsEmailReminder({ ...user, signup_email_confirmation: true }, blockedStorage), true)
})
