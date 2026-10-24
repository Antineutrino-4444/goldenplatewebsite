export function emailReminderKey(user) {
  return `gp:account-email-reminder:${user?.id}:${user?.last_login_at || 'session'}`
}

export function needsEmailReminder(user, storage) {
  if (user?.role !== 'superadmin') return false
  if (user.email && user.email_verified && !user.signup_email_confirmation) return false
  try { return (storage || globalThis.sessionStorage).getItem(emailReminderKey(user)) !== 'dismissed' }
  catch { return true }
}
