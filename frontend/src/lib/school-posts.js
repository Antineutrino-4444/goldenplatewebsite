export const postPlatforms = {
  instagram: { name: 'Instagram', home: 'https://www.instagram.com/' },
  facebook: { name: 'Facebook', home: 'https://www.facebook.com/' },
  bluesky: { name: 'Bluesky', composer: 'https://bsky.app/intent/compose' },
  x: { name: 'X', composer: 'https://x.com/intent/tweet' },
}

export const postTemplates = {
  winner: { label: 'Announce a winner', fields: ['school', 'winner', 'date', 'reward'] },
  launch: { label: 'Invite students to lunch', fields: ['school', 'date', 'place'] },
  results: { label: 'Share lunch results', fields: ['school', 'count', 'date'] },
}

function sentence(text) {
  return /[.!?…]$/u.test(text) ? text : text + '.'
}

export function makeSchoolPost(template, platform, details) {
  const school = details.school?.trim()
  const where = school ? ' at ' + school : ''
  const date = details.date?.trim()
  const when = date ? ' on ' + date : ''
  let opening
  let detail = ''
  let closing

  if (template === 'winner') {
    const winner = details.winner?.trim()
    const recipient = winner ? `${winner}, our Golden Plate winner` : 'our Golden Plate winner'
    opening = `Congratulations to ${recipient}${where}${when}!`
    if (details.reward?.trim()) detail = sentence(details.reward.trim())
    closing = 'Thanks to the student team who counted clean plates at the dish return.'
  } else if (template === 'launch') {
    opening = `Join us for a Golden Plate lunch${where}${when}!`
    const place = details.place?.trim() || 'the dish return'
    detail = `Look for our student team at ${place}.`
    closing = 'Choose a portion you can finish, then bring your plate back to be counted.'
  } else {
    const count = details.count?.trim()
    opening = count && /^\d+$/.test(count)
      ? `We counted ${count} clean ${Number(count) === 1 ? 'plate' : 'plates'}${where || ' at lunch'}${when}!`
      : `Our student team${where} finished counting clean plates at lunch${when}.`
    closing = 'Thank you to everyone who took part in Golden Plate.'
  }

  const lead = [opening, detail].filter(Boolean).join(' ')
  if (platform === 'x' || platform === 'bluesky') return lead
  return [lead, closing].join(platform === 'instagram' ? '\n\n' : ' ')
}

export function schoolPostDestination(platform, caption) {
  const site = postPlatforms[platform]
  if (!site?.composer) return site?.home
  const url = new URL(site.composer)
  url.searchParams.set('text', caption)
  return url.href
}
