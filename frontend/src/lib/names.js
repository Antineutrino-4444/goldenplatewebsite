export const normalizeName = (value) => (value ?? '').toString().trim()

export const makeStudentKey = (preferred, last, studentId = '') => {
  const studentIdNorm = normalizeName(studentId).toLowerCase()
  if (studentIdNorm) {
    return `id:${studentIdNorm}`
  }
  const preferredNorm = normalizeName(preferred).toLowerCase()
  const lastNorm = normalizeName(last).toLowerCase()
  if (!preferredNorm && !lastNorm) {
    return null
  }
  return `${preferredNorm}|${lastNorm}`
}

export const sanitizeSelection = (entry) => {
  if (!entry) return null
  const preferred = normalizeName(entry.preferred ?? entry.preferred_name)
  const last = normalizeName(entry.last ?? entry.last_name)
  const studentId = normalizeName(entry.student_id)
  const existingKey = entry.key ? String(entry.key).toLowerCase() : null
  const key = existingKey || makeStudentKey(preferred, last, studentId)
  return {
    ...entry,
    preferred,
    preferred_name: entry.preferred_name ?? preferred,
    last,
    last_name: entry.last_name ?? last,
    student_id: studentId,
    key
  }
}
