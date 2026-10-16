# Public website visual refactor — October 16, 2026

## Review conditions

Reviewed the actual React/Vite frontend served locally by Flask, using copied
preview databases and a mocked email transport. The public homepage was captured
at **390, 768, and 1440 CSS pixels**, with a 900px viewport height and full-page
screenshots. This is a subjective assessment of recognizable template patterns,
not a test of AI authorship. Source photos, historical results, the student quote,
and external media attribution were retained from the supplied case study and
previously verified sources.

Baseline files: `deai-before-{390,768,1440}.jpg`.
Final files: `deai-after-{390,768,1440}.jpg`, with matching `-top.jpg` crops.
These are saved in this chat's local visualization artifact directory. Scrolled
media verification is saved as `deai-media-mobile.jpg`. Full-page captures can
omit cross-origin iframe contents; the scrolled view confirms the video poster
and official Spotify player render. Instagram has a direct original-reel link
and a control that restores its photograph preview after embedding.

## Preserved items

- Golden Plate name, plate/leaf mark, green/gold identity, authentic PDF photos.
- Case-study attribution, reported clean-plate high of 75%, historical context,
  and distinction between clean-plate rates and food-waste weight.
- Public pages, primary registration/login actions, form contracts, API access
  rules, school workspace, guest privacy, and optional school login flight.
- YouTube, Spotify, Instagram, published coverage, original PDF, GitHub links,
  school map, real public pins, loading/error states, and reduced motion.
- Accessible heading hierarchy, image alternatives, keyboard focus indicators,
  mobile navigation, FAQ controls, and skip navigation.

## Priorities and changes

1. Replace the slogan/image split with a school field report: a concrete headline,
   visible registration action, documentary photo of Compost Coaches, descriptive
   caption, and a narrow explanation of the school's actual reward.
2. Remove the circular slogan sticker, overlapping statistic, ornamental icon
   strip, italic accent headings, decorative shapes, and repeated sales sections.
3. Present the historical result beside its source and readable qualifier. The
   reported high remains distinct from an average or a live website statistic.
4. Replace the invented dashboard illustration with the real screenshot from the
   supplied PDF. Add a readable transcription of its 151 clean / 211 total / 60
   dirty figures and a full-size image link.
5. Use plain descriptions of school roles, fewer sections, larger supporting
   text, squared photographs, and quiet ruled groupings. Retain native embeds
   and existing actions. Add Escape-to-close with focus restoration to mobile
   navigation and an Instagram preview recovery control.

The brand-swap test is improved by the dining-hall workflow, school reward,
Compost Coaches, student developer photograph, actual session record, and named
sources. The one-deletion test removed ornaments that carried no new information.

## Scorecard

A: layout formula (0–3); B: generic visual language (0–2); C: decorative residue
(0–1); D: generic copy/evidence (0–2); E: lack of subject specificity (0–2).
Higher totals indicate a stronger generic-template impression.

### Primary review

| Width | Before A/B/C/D/E | Before | After A/B/C/D/E | After |
|---|---|---:|---|---:|
| 390 | 3/2/1/1/1 | 8 | 1/1/0/0/0 | 2 |
| 768 | 3/2/1/1/1 | 8 | 1/1/0/0/0 | 2 |
| 1440 | 3/2/1/1/1 | 8 | 1/1/0/0/0 | 2 |

Before: the split slogan, mirrored image, overlapping metric, circular badge,
repeating feature rhythm, and general-purpose promotional copy dominated the
composition. Genuine school material limited the copy/specificity penalties.
After: a large headline and familiar editorial conventions remain (A=1), as does
a familiar green/paper/serif combination (B=1). The real workflow, evidence, and
photo captions now determine the page structure; decorative residue is absent.

### Separate review

A separate agent rated the screenshots without receiving a target score or the
primary reviewer's scores. Its integer judgments were:

| Width | Before A/B/C/D/E | Before | After A/B/C/D/E | After |
|---|---|---:|---|---:|
| 390 | 3/2/1/1/1 | 8 | 1/1/0/0/0 | 2 |
| 768 | 2/2/1/1/1 | 7 | 1/1/0/0/0 | 2 |
| 1440 | 2/2/1/1/1 | 7 | 1/1/0/0/0 | 2 |

The reviewer found the redesign more specific to the organization. It identified
small captions and an unreadable scaled dashboard as remaining issues; the final
revision increases photo captions and the result qualifier to 13px and adds the
visible session transcription and image enlargement link. The reviewer's initial
concern about missing media was withdrawn after it inspected the scrolled media
capture. Ratings remain subjective; the initial desktop/tablet ratings differ
from the primary assessment by one point.

## Verification and limits

- Production build passed. All 42 existing frontend tests passed, including
  supported local login return paths and map-subdomain links.
- Browser checks at 390/768/1440 found no horizontal page overflow, one top-level
  heading on the homepage, and alternatives for every image.
- Mobile menu opens; Escape closes it and restores focus to its trigger.
- Keyboard skip link focuses the main content. Navigation to the getting-started
  and media pages works. FAQ expansion works.
- Source images and the video poster finish loading when viewed. Spotify's
  official player renders. The Instagram embed can be loaded and closed,
  restoring its photo preview. All media retain direct external links.
- Primary destinations, registration/login routes, form handlers, school APIs,
  and the globe's logic were not changed. Backend tests were not repeated for
  this visual refactor; no backend code or email settings were modified.
- Third-party playback and embedding remain dependent on those providers and
  browser policies. No new external tracking or dependencies were introduced.
- No implementation blocker remains. The refactor is built locally and has not
  been deployed publicly.

## Follow-up: real dashboard and community counter

The historical dashboard image has since been replaced with the actual shared
dashboard metrics component and a random public, non-discarded session from the
server. A guest link opens that session. The earlier image-enlargement workaround
and transcription are no longer used. The compact counter and its larger display
show the combined clean-plate and session totals from all schools, without rates
or goals. Its labelled ruler compresses as the total grows, with synchronized
slow–fast–slow number/bar animation that starts on entry into view.

The photo-led composition, wordmark, green/paper identity, sourced content, media,
globe, and school workflows remain. The public header is now shared across the
map, counters, guest session, registration, and informational pages. Its return
link retains the source page. Registration remains accessible when already signed
in, without replacing that login merely to view the form.

Follow-up checks at 390, 768, and 1440px found no horizontal overflow. Confirmed
exact-session guest links, live polling after a private-session count change,
counter fullscreen/Escape, reduced motion, mobile navigation, and return paths
between the map, school counter, community counter, and registration. Relevant
backend tests, all 46 frontend tests, and the production build passed. New
captures and the recorded animation use isolated preview data because the local
working database has no saved sessions. No real mail was sent and notification
configuration was not changed. The earlier independent visual scores apply to
the editorial redesign; a second independent score was not repeated for this
bounded follow-up.
