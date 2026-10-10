export const DEFAULT_HOUSE_SCORE_SETTINGS = {
  clean_points: 2,
  dirty_penalty: 2,
  very_dirty_penalty: 10,
}

export const compareHouses = (a, b, sortBy) => {
  if (sortBy === 'score') {
    return b.score - a.score || a.house.localeCompare(b.house)
  }
  if (sortBy === 'percentage') {
    return b.clean_rate - a.clean_rate || b.total_count - a.total_count || a.house.localeCompare(b.house)
  }
  return b.total_count - a.total_count || a.house.localeCompare(b.house)
}
