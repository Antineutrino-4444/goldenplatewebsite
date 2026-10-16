import { hasGeographicCoordinates } from './mapCoordinates.js'

function sessionCount(count) {
  return Number.isFinite(count) ? Math.max(0, Math.floor(count)) : 0
}

export function maxSchoolSessions(schools) {
  return schools.reduce((maximum, school) => Math.max(maximum, sessionCount(school.session_count)), 0)
}

export function schoolActivity(count, maximum) {
  const sessions = sessionCount(count)
  // Scale against the community leader, with a readable minimum for new schools.
  const emphasis = Math.sqrt(sessions / Math.max(1, sessions, sessionCount(maximum)))
  return { sessions, emphasis, width: 30 + 18 * emphasis, height: 38 + 22 * emphasis }
}

export function schoolSessionLabel(count) {
  const { sessions } = schoolActivity(count)
  return `${sessions.toLocaleString('en')} public ${sessions === 1 ? 'session' : 'sessions'}`
}

export function schoolsWithoutLocations(schools) {
  return schools.filter((school) => !hasGeographicCoordinates(school))
}

export function submissionsInOthers(submissions, schools) {
  const schoolIds = new Set(schoolsWithoutLocations(schools).map((school) => school.school_id))
  return submissions.filter((submission) => !submission.pin_id || schoolIds.has(submission.school_id))
}
