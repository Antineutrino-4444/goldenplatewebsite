const PAGE_SIZE = 50

export function normalizeLeaderboardSearch(value) {
  return value.trim().toLocaleLowerCase().replace(/\s+/g, ' ')
}

export function leaderboardPage(rows, query, requestedPage) {
  const entries = rows.map((row, index) => ({ row, rank: index + 1 }))
  const matches = query
    ? entries.filter(({ row }) => [row.display_name, row.student_identifier, row.faculty_identifier]
      .some((value) => value && normalizeLeaderboardSearch(value).includes(query)))
    : entries
  const pageCount = Math.max(1, Math.ceil(matches.length / PAGE_SIZE))
  const currentPage = Math.min(requestedPage, pageCount)
  const start = (currentPage - 1) * PAGE_SIZE
  return { currentPage, pageCount, matchCount: matches.length, visible: matches.slice(start, start + PAGE_SIZE) }
}
