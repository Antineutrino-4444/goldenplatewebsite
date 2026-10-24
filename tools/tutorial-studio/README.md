# Golden Plate tutorial studio

A small, local video authoring engine for Golden Plate. It renders the real website components frame by frame, with scripted example data, measured highlights, animated instruction cards, cursor motion, click indicators and subtitles. It does not use a screen recording or Remotion.

The included registration recipe produces one continuous **74.5-second, silent, 3840×2160, 60 FPS SDR** tutorial. It explains email verification, school details, the primary administrator account, submission and the approval wait. The walkthrough finishes after the Login click, then a 9.5-second title-and-logo animation introduces the next tutorial. Portal orientation belongs in another recipe; the ending contains no footage of it.

## Install and check

Run from the repository root. Requirements: Node.js 22 or newer, FFmpeg and FFprobe on `PATH`, the frontend's npm dependencies, and a Chromium browser.

```sh
npm --prefix frontend ci
npm --prefix tools/tutorial-studio ci
node tools/tutorial-studio/cli.mjs doctor
```

The tool uses an installed Playwright Chromium, Microsoft Edge or Google Chrome. If none is installed:

```sh
cd tools/tutorial-studio
npx playwright install chromium
```

On the author's Mac it was tested with Node 26.4, Playwright 1.62.1, Microsoft Edge and FFmpeg 9.0.2. Georgia and Avenir Next are the website's fonts; install those fonts on another machine for the same appearance. Browser, font and frontend changes can change pixels. Exports are repeatable for a fixed environment, including seeking to frames in any order.

Optional environment variables: `TUTORIAL_BROWSER_PATH`, `TUTORIAL_FFMPEG`, `TUTORIAL_FFPROBE`, and `TUTORIAL_PLAYWRIGHT_PATH`. `doctor` reports which browser and dependencies will be used.

## Preview, render and verify

```sh
node tools/tutorial-studio/cli.mjs preview
node tools/tutorial-studio/cli.mjs storyboard
node tools/tutorial-studio/cli.mjs render --workers 2 --resume
node tools/tutorial-studio/cli.mjs verify --out output/tutorial-studio/school-registration-3840x2160-60fps.mp4
```

The preview is at `http://127.0.0.1:5199`. It provides playback, a scene picker and a scrubber. Stop it with Ctrl-C. Preview size does not determine export resolution. The live preview shows individual scene animations; the encoded export also blends scenes with half-second crossfades.

The render writes the MP4, `.srt` and `.vtt` subtitles, `.audit.json` layout/render evidence and `.verified.json` export checks under `output/tutorial-studio/`. Captions are also burned into the video. The MP4 has no audio stream.

`render` automatically verifies the completed file's dimensions, frame rate, frame count, duration, SDR Rec.709 metadata and absence of audio, then decodes the whole video to check for corruption. Every source frame is checked for target clipping, highlight collisions, label visibility and camera/viewport consistency before encoding. A failed check stops the render.

Useful variations:

```sh
# Fast small review export; same composition and timing
node tools/tutorial-studio/cli.mjs render --width 1920 --height 1080 --fps 30 --quality draft --out output/tutorial-studio/review.mp4

# Inspect particular scenes at two seconds, as native-resolution PNGs
node tools/tutorial-studio/cli.mjs storyboard --scenes email,school --time 2 --out output/tutorial-studio/review-stills

# Use a different recipe or output filename
node tools/tutorial-studio/cli.mjs render --recipe tools/tutorial-studio/recipes/registration.mjs --out output/tutorial-studio/my-tutorial.mp4 --resume
```

Two workers are a reasonable starting point for 4K rendering; `--workers 1` reduces memory use. Ctrl-C stops a render. `--resume` reuses completed scene clips only when their source fingerprint, quality level, dimensions, frame rate, browser version and encoded file hash still match. A draft cache cannot silently reduce a final export's quality. Partial clips are regenerated. `--work directory` chooses the scene-cache folder; the default is `.tmp/tutorial-studio/`. Clear that cache after changing system fonts, which are external to the source fingerprint. Output and cache files are ignored by Git. Use separate output filenames if preserving earlier versions matters.

## Author another tutorial

Start by copying `recipes/registration.mjs`. A recipe exports an object with `id`, output dimensions, frame rate, transition duration, named `targets` and an ordered `scenes` array.

Targets use CSS selectors or accessible roles/names, rather than screenshot coordinates:

```js
targets: {
  email: { selector: '#school-email' },
  send: { role: 'button', name: 'Send Code', exact: true },
  // A single envelope around a group of controls:
  codeGroup: { union: ['code1', 'code6'] },
}
```

A website scene supplies its initial controlled component `state`, page provider, camera anchors, highlighted targets, instructional copy and timed actions:

```js
{
  id: 'email', page: 'register', duration: 8,
  label: 'REGISTER A SCHOOL', title: 'Use an email\nyou can access.',
  instruction: 'Enter your school contact\nemail, then send the code.',
  caption: 'Enter the contact email and select Send Code.',
  state: { schoolEmail: '', verificationSent: false },
  highlights: ['email', 'send'], camera: { card: true },
  actions: [
    { type: 'type', target: 'email', field: 'schoolEmail', value: 'school@example.org', at: 1.5, duration: 2.6 },
    { type: 'click', target: 'send', at: 5.8, after: 0.3, set: { verificationLoading: true } },
  ],
}
```

Actions support `type`, `click`, `focus` and `move`. Cursor travel ends at `at`; optional `travel` sets its duration and `position: [xFraction, yFraction]` sets the point within the target. `set` applies controlled state after a click's optional `after` delay. Typing derives each frame from elapsed time, so seeking does not replay network activity or depend on earlier browser events.

`camera: { fullPage: true }` fits the home page; `{ card: true }` fits an auth card. For a subset use `{ targets: ['schoolName', 'schoolCode'], padding: 75 }`. Optional `topAnchor` and `topPadding` preserve a heading above the controls, and `minWidth` limits zoom. `leader: 'above'` or `'below'` routes the leader around a crowded viewport; the default connects through the side rail. Titles use `kind: 'title'`; the included approval interlude uses `kind: 'approval'`. A reusable `kind: 'closing'` scene takes `subtitle`, a two-line `title`, `description` and `caption`: its title rises into place and a gold arrow draws underneath. After a reading hold, the title masks upward, the arrowhead retracts and the same shaft bends into the plate logo. The native leaf unfurls, the wordmark settles in, and the brand and next-video title hold through the end. Use at least 8 seconds for the complete motion, preferably 9.5 seconds for a comfortable final hold.

The current demo providers are **home, register and login**. To add a portal tutorial, import its real component and supply a controlled demo provider in `src/demo.jsx`, then allow that page in `engine/timeline.mjs`. Add explicit local fixtures for any data it needs in `demo.html`. Add meaningful workflow/browser checks for the new page. This is an extensible authoring engine, not a crawler that automatically understands arbitrary pages.

Always review the generated storyboard and encoded video after changing a recipe or the website. Automated geometry checks cannot judge whether the prose teaches well or whether a new page has enough context.

## How it works

- `engine/timeline.mjs`: pure frame state, timing, cursor easing, circular corner geometry, camera projection and collision checks.
- `engine/closing.mjs`: smooth circular-arc geometry for the line-to-plate ending and its timed leaf/wordmark reveals.
- `src/demo.jsx`: actual website components with isolated, local example handlers; production frontend files remain unchanged.
- `src/studio.jsx` and `.css`: composition, SVG overlays, measured DOM targets, continuous callout animation, click pulses and preview controls.
- `engine/runtime.mjs`: isolated Vite server, browser, dependency discovery and native PNG frames.
- `cli.mjs`: parallel scene rendering, resumable cache, smooth scene composition, captions and export verification.

Callout paths derive all four corner radii from computed website CSS, including clipping parents. They follow control borders without expanded halos, so neighboring fields/buttons retain their gap. Leaders render above the website viewport frame. The same path and card exist during entrance, hold and exit; there is no moving-to-static asset swap. Cursor movement uses minimum-jerk easing and visible presses include a ring, center mark and target wash. The actual website PlateMark supplies the leaf.

The server binds only to localhost and starts **no Flask/WSGI backend**. It does not read the root `.env`. The demo uses example values and a strict list of local API fixtures; unknown fetches throw. Export browser contexts also block backend and external requests. No school registration, login, notification email or real verification message is sent. CAPTCHA is disabled only inside this isolated demo.

## Checks

```sh
npm --prefix tools/tutorial-studio test
npm --prefix tools/tutorial-studio run test:browser
```

Unit tests cover timeline state, cursor endpoints, corner geometry, collision rejection, camera projection and cusp-free closing curves. Browser checks cover 103 rendered states, the real form components' local handlers, actual 3840×2160 PNG dimensions, repeatable 4K pixels after seeking and a 31-second idle, visible click indicators, the Login hold, intermediate closing geometry and native leaf shape, the final branded hold, backend isolation, and previews at 390, 768 and 1440 pixels. Final export verification is separate from these tests.

See `DESIGN.md` for the visual decisions and screenshot review.
