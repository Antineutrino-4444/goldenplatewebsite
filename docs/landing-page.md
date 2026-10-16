# Golden Plate public website

The public homepage introduces the initiative, its school workflow, and the
existing PLATE tools. `/about`, `/how-it-works`, and `/stories` provide dedicated
pages. `/login`, `/signup`, `/register`, `/portal`, `/portal/dashboard`,
`/portal/admin`, `/interschool`, `/map`, and `/live-counter` separate the main
visitor and school workflows. The Flask SPA fallback supports direct visits and
reloads. Unknown frontend URLs display a 404 page; server authorization remains
in the existing API routes.

## Content and assets

- User-supplied **Case Study — St. Andrew's College**: five photographs extracted
  directly and converted to WebP in `frontend/public/images/initiative/`.
  The original case study is available from the footer and results section as
  `frontend/public/resources/st-andrews-golden-plate-case-study.pdf`.
- The case study describes clean-plate rates going from below half to as high as
  75%. This is attributed to St. Andrew's, labelled as a reported high, and never
  represented as a live total, average, or percentage reduction in food-waste mass.
- The platform description comes from this repository's README and implemented
  recorder, roster, dashboard, house-ranking, counter, export, and privacy tools.
  The public product section now renders the same `SessionMetrics` component as
  the school dashboard, with saved totals loaded directly from PLATE. On each
  mount it requests a random public, non-discarded session with at least 44 total
  records (clean, dirty, very dirty, and faculty combined), belonging to an active
  school. Sampling is uniform across eligible sessions; repeats are possible.
  Both views use the same backend count serializer and frontend calculations.
  The exact session opens at `/guest/sessions/:sessionId` without an account or
  replacing an existing login. This read-only page loads that ID, never another
  random session, and offers Refresh. Public API responses contain aggregate
  counts only; names, rosters, owners, and winners are excluded, and free-text
  session titles follow the school's guest-privacy setting. Private, discarded,
  deleted, and disabled-school sessions return 404, including after a link was
  shared. Responses use `Cache-Control: no-store`. Empty databases and failed
  requests show explicit states, never historical or fabricated totals.
- The compact live counter on the homepage polls
  `/api/public/counter` every five seconds. It shows only clean plates, with no session-count metric: all-time combined totals from **all schools**, including private
  sessions and disabled schools' historical sessions, excluding discarded
  sessions. Faculty clean plates are included. It uses the same saved counts
  as session dashboards and publishes no per-school breakdown, people, rates,
  goals, or private-session metadata. The user explicitly requested the true
  all-schools aggregate. Loading and connection errors never invent a zero.
  Its goal-free bar has a logarithmic ruler that continuously expands as totals
  grow. Original 0–100 marks remain, with larger ranges accumulating to the right
  and earlier marks compressing left. Close labels stack on separate rows;
  intermediate tick marks remain even when their labels cannot fit. The same
  ruler is used on the large community display. Animation starts only when at
  least 75% of the bar is inside a viewport inset of 24–96px at the top/bottom.
  Fully leaving the viewport resets it to zero; returning comfortably inside
  starts a fresh animation. Edge movement does not repeatedly restart it.
  Count and bar move together with slow acceleration,
  a faster middle, and slow deceleration. Subsequent updates animate from the
  current number, including decreases after corrections or discards. Reduced
  motion shows final values immediately. Screen readers receive the saved count.
  The compact bar has round ends. Hover or keyboard focus reveals the existing
  Golden Plate mark at its fill tip; touch/pen taps reveal it for three seconds.
  The tip is decorative, cannot intercept input, and stays within the bar's
  bounds near either edge. A 44px target supports tapping without blocking
  normal page scrolling, and touch devices show a short hint. Tip transitions
  are disabled for reduced motion. The large counter retains its existing track shape.
  `/live-counter/community` provides the same counts at large scale, including
  full screen. A separate link opens the existing `/live-counter` school-specific
  counter, which retains its school login/code, time ranges, and settings.
- Geography: Natural Earth's public-domain 1:110m land outlines, downloaded from
  https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_110m_land.geojson.
  Only land shapes are displayed, without political boundaries. The globe uses
  d3-geo orthographic projection and reads school pins from `/api/map/schools`.
  School locations are never inferred. Unmapped schools remain in Others on
  the full map. The globe rotation pauses off screen, in background tabs, and
  under reduced-motion preferences; visitors can pause it manually.

## Verified external media (October 16, 2026)

- YouTube: **Golden Plate**, by Matt, https://www.youtube.com/watch?v=vQN0X-7xXVo.
  Linked in the supplied PDF; verified through YouTube's public oEmbed response.
  Loads the privacy-enhanced YouTube iframe when the visitor presses Play.
- Spotify: **Spoiler Alert — S2 E02 The Golden Plate**, Second Harvest Youth
  Council, https://open.spotify.com/episode/0e3Fu2pkadTsyrRyeFraXe.
  Title, publisher, and discussion subject verified from Spotify's public episode
  and show pages. Embedded via Spotify's official episode embed; never autoplays.
- Instagram: SAC Environmental Council, **Golden Plate Winners Chose Grilled
  Cheese For Friday Lunch!**, October 24, 2024,
  https://www.instagram.com/reel/DBgb3-MRESr/.
  Verified on the public Instagram reel, including publisher and caption.
  The visitor can load the Instagram iframe; the original reel and council
  profile remain directly linked even when embedding is blocked.
- International Boys' Schools Coalition, **Friendship and Connectedness**:
  https://www.theibsc.org/news/stories/friendship (St. Andrew's / Golden Plate).
- Green Schools Alliance's public feature announcement:
  https://www.linkedin.com/posts/the-green-schools-alliance_sustainableschools-greenschools-teachers-activity-7375757042549972992--T7C.
  The old `best-practices-1/golden-plate` URL in the PDF currently resolves to
  general Green Schools Alliance content, so the verified announcement is linked.
- Matt Jaekel's Sustainable School newsletter, February 16, 2025:
  https://thesustainableschool.beehiiv.com/p/sustainable-school-newsletter-let-s-eat-55fa70ca5798ec89.
  Publicly indexed text identifies the initiative and its school playbook.

### Podcast transcript availability

An initial search did not find an accessible transcript or full audio file for
transcription. The user subsequently supplied **The Golden Plate — Cleaned
Four-Speaker Transcript.txt**, an edited Otter.ai transcript, and explicitly
requested quotation. He subsequently confirmed the names **Jiajun (Leo) Li** and
**Shuoyou (Nick) Wang**, used in the public copy, credits and transcript labels.

The supplied spoken text is preserved at
`frontend/public/resources/golden-plate-podcast-transcript.txt`, available from
the readable `/stories/transcript` page linked beside the player.
The reader preserves every speaking turn, offers topic jumps and a text-file
download, and uses the shared header/return navigation. The source file includes its original provenance
notes, with the owner-confirmed full names added to the speaker key. It has not
been independently checked against the full recording.
Transcript text is reproduced from that edited source and labelled accordingly; timestamps
refer to approximate speaking-turn starts, not exact audio seek points.

- The podcast section identifies all three student speakers and retains the
  embedded episode and complete edited reader. The informal highlighted excerpts
  were removed at the user's request; public promotional quotations use the
  formal writing described below.
- No interview-era school-registration count or unverified food-waste-by-weight
  reduction has been inserted into live totals or the impact headline. The case
  study's clean-plate-rate figures retain their original qualification.

The episode remains embedded and linked on Spotify. The podcast host is unnamed
in this source; ambiguous teacher names are not inferred.

### Formal writing and practical guidance

The owner supplied `EVERYTHING_DOCUMENT.pdf`, a 224-page private writing archive.
Only initiative-related writing was used. Two exact sentences from the submitted
school-community essay on archive page 90 appear as attributed quotations in
`initiative-writing.js`. Page 89 supports the description of replacing handwritten
names with student identifiers and centralized records; page 98 supports the
community-led initiative framing. The quotations were checked against extracted
text and the rendered source page. Application prompts, editorial comments,
unrelated personal material, historical adoption counts and inconsistent historical
percentages are not published. The PDF itself is not copied into public assets.
The public attribution describes the source simply as Jiajun Li's writing on
sustainability and school community.

`/how-it-works` explains the initiative's purpose, lunch routine, recognition and
community ownership. `/getting-started` separately documents actual website
operations: school email verification/approval, member approval/invites, role
boundaries, roster uploads, session creation/switching, the four recording
categories, identity matching/count-only records, save/history checks, results,
draw finalization, exports, guest access, counters and school location settings.
Labels and permissions were checked against the current implementation. Student
and teacher CSV downloads contain fictional example rows only. Guide chapter
anchors, navigation and return paths use the existing site shell.

The shared contact section appears on both pages. Matthew's school email was
provided by the owner. Verified professional/institutional sources:

- Matthew Jaekel's SAC-affiliated LinkedIn: https://ca.linkedin.com/in/mattjaekel.
- His Golden Plate newsletter: https://thesustainableschool.beehiiv.com/p/sustainable-school-newsletter-let-s-eat-55fa70ca5798ec89
  (February 16, 2025; indexed source confirms author and initiative).
- SAC's account of his environmental work: https://www.sac.on.ca/news-detail?pk=1541348.
- SAC office directory: https://www.sac.on.ca/contact-us (verified October 16,
  2026), for info@sac.on.ca, +1 905-727-3178, 15800 Yonge Street, Aurora ON L4G 3H7,
  Canada, and Monday-Friday 8am-4pm office hours. The number is labelled as the
  school office, not a verified direct number for Matthew. No personal numbers,
  unverified extensions or lookalike profiles are included.

These are public contact links only; they do not change notification recipients
or send messages.

## Login transition

Only a newly successful school login to `/portal` starts the flight. It fetches
the existing public school list and matches the authenticated school ID. The
full-screen Mapbox globe uses the school map's Hybrid basemap, English labels and
CN worldview, without changing saved map preferences. All flights start above
Jiamusi Maternal and Child Health Hospital (佳木斯市妇幼保健院), at WGS84
130.3128° E, 46.80853° N. After a 200ms opening beat, the globe follows a shortest
spherical route for 1.9 seconds with quintic ease-in/out. Zoom stays fixed during
the turn and is sized against the viewport's smaller dimension, so the whole
globe remains visible. Then a 1.9-second quadratic zoom accelerates toward the school.
The final 28% of
the zoom crossfades to the actual recorder mounted beneath the map; it does not
shrink or clip an SVG within a small square. The map can naturally fill the screen
as the camera moves from the full globe to the school area.

Missing coordinates, guests, inter-school accounts, reduced motion, unavailable
Mapbox/WebGL, and deep links to other destinations bypass the animation. A visible
Continue button and Escape always allow entry. Map loading has a 6.5-second limit;
an independent 12-second preparation deadline and a playback deadline guard against network/rendering stalls.
Backgrounding the page or enabling reduced motion also completes the optional
arrival. Restored sessions do not replay it. The arrival traps keyboard focus;
the recorder is inert until arrival completes. Participating schools retain public
pins, and map attribution remains visible.

The globe follow-up passed 54 frontend tests, including spherical travel across
the date line, turn easing, constant zoom acceleration, fade timing, viewport
framing, and fixed hospital origins for distant and nearby destinations. The new flight modules pass focused
lint and the production build passes. Browser QA used an isolated account and
copied databases at 390, 768 and 1440 pixels, checked the complete animated
handoff, Continue, Escape, reduced-motion bypass, and focus on the recording
heading after arrival. Authentication and recorder URLs share a persistent
workspace route so the final handoff retains its loaded data and rendered page.

## Shared public navigation

School pin popup contents are keyboard-accessible guest-entry links. The school
details panel (including Others) and the landing globe's selected-school callout
use the same `/guest/schools/:schoolId` entry. It calls the established guest login
with `school_id`, initializes the existing guest session, and replaces the entry
URL with `/portal`. Visitors see the normal MainPortal with its session switcher,
privacy and read-only permissions. It switches the current browser login into
guest mode, matching the existing login form. The portal's School map link
returns to the map. Failed entry offers Retry and Back to the school map.

The landing preview's exact-session public dashboard is unchanged.

The homepage, stories, map, guest dashboard, counter pages, login, and school
registration use one persistent public header outside the route loading boundary.
Internal links use client-side navigation and record their source page. A visible
header link returns to that source, or Home on a direct visit. Return destinations
are restricted to known local routes. Returning through the header and browser
history restores saved scroll positions. The map retains school-account tools
within its page toolbar. The same paper background, type, and header frame
continue through each destination. Route content enters over 220ms; reduced
motion skips this transition. Forms and private portal state are not remounted
merely to animate a route. Map subdomains link back to the corresponding main
host for public navigation.

## Verification

The formal-writing and guide follow-up passed all 55 frontend tests, focused
lint, and the production build. Both published essay excerpts were checked
against page 90 of the supplied archive, including its rendered page. Browser
checks covered the overview, guide chapter and contact jumps, source-page return
navigation, the student CSV download, and 390-, 768-, and 1440-pixel layouts
without horizontal overflow. Preview data and mail transport remained isolated.

Build the frontend, run the frontend Node tests (including safe redirects and map
host links), and run the relevant Flask authentication, school registration,
public map, plate recording, startup-notification, and school-contact tests.
Browser QA should use copied/isolated databases and a mocked email transport;
never issue real registration/signup emails as an automated test.

The transcript follow-up passed all 48 frontend tests, focused lint, and the
production build. Parser checks preserve every spoken paragraph from the supplied
edited transcript and verify the featured quotations against their speaker turns.
Browser checks covered the quotation-to-passage link, topic jumps, shared-header
return navigation, and layouts at 390, 768, and 1440 pixels. The 390-pixel transcript
reader has no horizontal overflow. Preview data and mail transport were isolated.


## Editorial redesign

The October 16 visual refactor retains the wordmark, green/gold identity,
case-study photography and attribution, media sources, primary actions, public
routes, authentication workflows, and globe behavior. It replaces the decorative
split slogan, sticker, floating metric, icon strip, tilted mock dashboard, and
repeated promotional panels with an editorial school field report. See
[design-review.md](design-review.md) for the before/after review and checks.

## Page entrance

Public pages use a short fade and 12px upward entrance: navigation first,
then the homepage heading, introduction, photograph, and side notes. The longest
stage ends after 940ms. Opening another public route restarts its entrance.
Images fade in when their load event arrives, including lazy-loaded photos.
Animation uses opacity and transforms without moving the page layout or blocking
interaction. Keyboard-focused groups and anchor destinations skip the entrance;
reduced-motion preferences show everything immediately. Login, recording, and the
existing school-flight logic are unchanged.

## Recorder section controls

The session name, student total, faculty total, and winner appear above the
management buttons and recording area. Guest mode has a full-width read-only
notice above the balanced two-column category buttons. For every role, optional
rankings, draw, and permitted database panels start closed. Their buttons toggle
content in place below recording; clicking an open section closes it. Expand all
shows every permitted panel, and Collapse all returns to the compact view.
Plate Tracking History always remains outside these controls. Panel visibility
does not change guest restrictions or administrator permissions.

## Guest visit lifetime and sign-up protection

Guest visits end when navigation leaves the school portal (Recorder and session
dashboard remain one workspace). The school live counter has its own guest
visit, which also ends when leaving that page. Public/authentication destinations
wait for guest-only cleanup before checking access, including on a fresh visit
with an old guest cookie. Guest entry and exit requests are serialized to prevent
a delayed pin-login response from restoring access after leaving. Closing or
leaving a guest page also sends best-effort cleanup; switching browser tabs does
not end access. Regular account sessions are preserved by the guest-only endpoint.

If cleanup fails, or an existing account is signed in, both `/signup` and
`/register` display an accessible dialog explaining that sign-up needs logout,
with Log out and continue and Return to portal actions. Closing the dialog keeps
the same recovery actions on the page. The API also rejects authenticated account
or school creation requests before processing verification or sending alerts.
Failed explicit logout keeps the existing session and reports the error.

Verification: 60 frontend tests and 104 focused backend tests passed, along with
the production build and lint on the new lifecycle/notice modules. Browser checks
covered portal-to-map-to-registration cleanup, a simulated failed automatic exit
and its guest recovery dialog, existing-account notices on registration and
account signup, successful Log out and continue actions, and a 390px dialog
without horizontal overflow. No sign-up submissions or real emails were sent.
The wider backend run encountered the existing legacy-map recipient-settings
test expecting 200 while that disabled map returns 410; unrelated hook lint
errors (unused catch variables) and existing effect warnings also remain.

## Login globe loading follow-up

Map loading and camera playback now have separate safety deadlines: up to 12
seconds to prepare the globe, then the full turn/zoom sequence with its own
watchdog. The previous 6.5-second map deadline and shared 14-second overall
deadline could skip or shorten a cold-load flight. The map stays hidden behind
a readable paper-colored preparation view until its first ready camera frame;
it then fades in over 240ms. Missing locations, unavailable map modules, Escape,
and Continue to portal still allow login to finish. Loading/initialization
failures are logged instead of silently discarded. Explicit workspace route
elements also remove the misleading empty-leaf-route console warnings.

Browser checks completed the turn, zoom, and portal arrival at 1440px with the
browser cache disabled (about 7 seconds including preparation), and at 390px
without horizontal overflow or console warnings. Blocking the globe module
confirmed that the portal still opens. Timing tests simulate an 11-second load
followed by the complete camera sequence, plus failed-load and unmount exits.

Camera playback now takes 4 seconds
(200ms initial hold, 1.9-second turn, 1.9-second zoom). All visitors now
start above Jiamusi Maternal and Child Health Hospital, replacing IP lookup and
the previous nearby-school shortcut. The public landing globe, default school
map/globe view, and world reset use the same hospital orientation. Explicit school
and location editing focus still takes precedence.

The hospital's main campus address is 26 Youyi Road, confirmed in the
[Jiamusi government hospital directory](https://jms.zwfw.hlj.gov.cn/zczx/tzgg/art/2023/art_8aeb084547934f158d18d2ff9261f7d3.html).
The WGS84 position comes from the
[OpenStreetMap hospital footprint, displayed by Mapcarta](https://mapcarta.com/W1360053052).
Loading deadlines, easing, English labels, territorial worldview, and portal fade
remain in place. Tests cover the fixed opening view for Canadian, nearby Chinese,
and southern-hemisphere schools, spherical travel across the date line, and the
complete camera sequence.

## Appearance

A shared light/dark/device appearance menu is available in public and portal
headers. Theme tokens cover public pages, forms, recorder surfaces, dialogs,
counters, and map controls; map lighting responds without resetting the camera.
See [dark mode implementation and QA](dark-mode.md).
