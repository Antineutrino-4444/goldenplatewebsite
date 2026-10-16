export const PODCAST_TRANSCRIPT_URL = '/resources/golden-plate-podcast-transcript.txt'

const speakers = { HOST: 'Host', NICK: 'Shuoyou (Nick) Wang', LEO: 'Jiajun (Leo) Li', 'MICHAEL CASEY': 'Michael Casey' }

export function parsePodcastTranscript(text) {
  const source = text.replace(/\r\n/g, '\n')
  const pattern = /(?:^|\n)\[(\d{2}:\d{2})\] ([A-Z][A-Z ]+)\n([\s\S]*?)(?=\n\[\d{2}:\d{2}\] [A-Z][A-Z ]+\n|$)/g
  return Array.from(source.matchAll(pattern), ([, time, speaker, body]) => ({
    id: `podcast-${time.replace(':', '-')}`,
    time,
    speaker: speakers[speaker.trim()] || speaker.trim(),
    paragraphs: body.trim().split(/\n\s*\n/).filter(Boolean),
  }))
}
