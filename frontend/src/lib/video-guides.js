// Titles, order, IDs, and durations verified against the supplied YouTube
// playlist on 2026-10-25. Keep the catalogue local; no API key is required.
export const SCHOOL_GUIDE_PLAYLIST_ID = 'PLH6byMZYqynw'
export const SCHOOL_GUIDE_PLAYLIST_URL = `https://www.youtube.com/playlist?list=${SCHOOL_GUIDE_PLAYLIST_ID}`

const SEARCH_TERMS = {
  1: 'registration signup', 5: 'roster rosters csv upload students',
  6: 'roster rosters csv upload faculty', 7: 'scan scanning card coach coaches',
  8: 'dirty faculty leftovers', 9: 'history corrections exclusions',
  19: 'signup member members invitation', 21: 'email domain domains',
  22: 'password passwords security', 24: 'time ranges settings',
  26: 'location pin', 28: 'maps location schools',
}

export const VIDEO_GUIDES = [
  [1, 'GP4FzQN5Y2k', 'Register your school', '1:15', 'Getting started'],
  [2, 'OUHzGFpyldI', 'First-login orientation', '1:15', 'Getting started'],
  [3, '42l7z0SykaA', 'Prepare your school', '1:32', 'Getting started'],
  [4, 'pmhWraT6OrI', 'Create and switch sessions', '1:24', 'Getting started'],
  [5, 'n6X7-fE5owk', 'Load your student database', '1:41', 'Getting started'],
  [6, 'JN5rcKe-5KE', 'Load and maintain teachers', '1:44', 'Getting started'],
  [7, 'lyQzevaPOAM', 'Record clean plates', '1:29', 'Recording plates'],
  [8, 'gWSUcouhlTg', 'Record other plate types', '1:17', 'Recording plates'],
  [9, '0zMld8qVSqg', 'Check and correct records', '1:59', 'Recording plates'],
  [10, '2ol3OOjfRgA', 'Read house rankings', '1:28', 'Results and draws'],
  [11, 'XzS09QV-60A', 'Understand house estimates', '3:46', 'Results and draws'],
  [12, 'NxYhD1aWfZw', 'Understand the draw', '2:00', 'Results and draws'],
  [13, 'Pgzk0KvdSpo', 'Run and finalize draws', '3:30', 'Results and draws'],
  [14, '4TV0dI0keRA', 'Use the session dashboard', '1:42', 'Results and draws'],
  [15, 'F7Dg5wXwr50', 'Export session reports', '1:33', 'Session management'],
  [16, 'f8am7dUEO7U', 'Export multiple sessions', '2:29', 'Session management'],
  [17, 'H_tY85RjSLk', 'Combine and separate sessions', '1:39', 'Session management'],
  [18, 'c77__m5PuRg', 'Discard or delete sessions', '2:52', 'Session management'],
  [19, 'rHF2pEuNZt4', 'Invite your school team', '2:37', 'Accounts and access'],
  [20, 'F1300afhwxw', 'Manage school accounts', '2:24', 'Accounts and access'],
  [21, '0TjIYhc1wKc', 'Set school email rules', '1:41', 'Accounts and access'],
  [22, 'fGx_B3IYjfw', 'Keep your account secure', '3:45', 'Accounts and access'],
  [23, '9c-ZgOJYXrw', 'Display the live counter', '1:42', 'Sharing and maps'],
  [24, 'nKBU2n0y4Ok', 'Configure counter displays', '2:10', 'Sharing and maps'],
  [25, 'XFj2gdTcU8I', 'Share guest views safely', '2:03', 'Sharing and maps'],
  [26, 'vypIBNzbDb8', 'Place your school on the map', '2:02', 'Sharing and maps'],
  [27, '7B5VjOWtdzI', 'Explore the public website', '2:06', 'Sharing and maps'],
  [28, 'V_K5T_Lqi_E', 'Explore the school map', '5:48', 'Sharing and maps'],
  [29, 'VPwfVVr53wk', 'Review school registration requests', '2:22', 'Partner schools'],
  [30, 'sjKEVpavq-c', 'Invite and register a partner school', '4:29', 'Partner schools'],
  [31, 'HHqmIlMO8Ps', 'Manage partner schools', '4:45', 'Partner schools'],
  [32, 'HBWmH_HTweE', 'Your everyday checklist', '3:10', 'Recording plates'],
].map(([number, id, title, duration, group]) => ({ number, id, title, duration, group, keywords: SEARCH_TERMS[number] || '' }))

export function guideWatchUrl(guide) {
  return `https://www.youtube.com/watch?v=${guide.id}&list=${SCHOOL_GUIDE_PLAYLIST_ID}&index=${guide.number}`
}

export function guideEmbedUrl(guide) {
  return `https://www.youtube-nocookie.com/embed/${guide.id}?autoplay=1&playsinline=1&rel=0`
}

export function filterGuides(guides, query = '', group = '') {
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean)
  return guides.filter((guide) => (!group || guide.group === group)
    && words.every((word) => `${guide.number} ${guide.title} ${guide.group} ${guide.keywords}`.toLowerCase().includes(word)))
}
