export function dashboardMetrics(sessionStats = {}) {
  const studentCleanCount = Number(sessionStats.clean_count ?? 0)
  const dirtyCount = Number(sessionStats.dirty_count ?? 0)
  const redCount = Number(sessionStats.red_count ?? 0)
  const combinedDirty = Number(sessionStats.combined_dirty_count ?? (dirtyCount + redCount))
  const facultyCount = Number(sessionStats.faculty_clean_count ?? 0)
  const cleanCount = studentCleanCount + facultyCount
  const totalRecorded = studentCleanCount + dirtyCount + redCount + facultyCount
  const cleanPercentage = totalRecorded ? (cleanCount / totalRecorded) * 100 : 0
  const dirtyPercentage = totalRecorded ? (combinedDirty / totalRecorded) * 100 : 0

  return {
    cleanCount,
    dirtyCount,
    redCount,
    combinedDirty,
    facultyCount,
    totalRecorded,
    cleanPercentage,
    dirtyPercentage
  }
}
