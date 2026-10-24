# Golden Plate tutorial studio

The audience is a school administrator registering a new school. The visual reference is the accepted 4K tutorial in this conversation. Authentic details: school contact email verification, a separate PLATE approval step, and a primary school administrator's first Login click. The walkthrough ends at that click, then a title-only closing animation connects it to the future account-orientation tutorial.

## Composition choices, before implementation

1. Task-first: a large real website viewport with an instruction rail outside it. It preserves room for labels and leaves the website unobscured.
2. Content-first: a full-width website with a bottom instruction band. It makes the website larger but reduces space for contextual instructions and requires more zoom changes.
3. Brand-first: chapter cards alternating with full-screen demonstrations. It gives chapters more emphasis but interrupts this short, continuous workflow.

Choose the task-first direction, matching the approved tutorial. The real registration form is the primary focal point; camera framing and a moving cursor clarify each action. Gold, forest green, Georgia, Avenir Next, and PlateMark are inherited from the website, not a newly invented identity.

## System

- Composition: 1920×1080 logical pixels, rendered at device scale 2 to 3840×2160, 60 frames per second. Other output sizes are explicit export options.
- Website viewport: x=560, y=144, width=1296, height=816 logical pixels. The instruction card remains in the left rail. Headers, subtitles and progress stay outside the website.
- Type: site Georgia headings, Avenir Next body; tutorial headings 46px, instruction text 26px, burned-in subtitles 25px. No tiny technical labels in the finished video.
- Palette: existing #101a16 background, #edf0e6 ink, #b6c4b9 muted text, #ddc38a editorial gold, #f8f7f0 instruction paper.
- Geometry: measure real elements on every rendered state; derive all four corner radii from computed CSS and any clipping parent. Highlights follow a control border without an expanding halo. Pointers are above the viewport frame.
- Motion: a single continuous slide-to-rest for instruction cards, the same rounded path during stroke reveal and hold, minimum-jerk cursor movement, and click rings plus a momentary target wash.
- Camera: frame named elements and their contextual headings, not manually entered screenshot coordinates. Keep every target and its label inside the viewport.
- Preview: the video keeps its 16:9 composition at 390, 768 and 1440px widths; playback controls reflow below it. Mobile resizing must not change an export's layout.
- Provenance: real SchoolRegistration, LoginView, PublicHeader, PlateMark and LandingPage components and real site assets. Input values are explicitly example data; no production backend, registration or email delivery is used.

## Preview review — 24 October 2026

Reviewed actual screenshots in `output/tutorial-studio/browser-verification/` at 390, 768 and 1440 CSS pixels. The content and imported assets were checked against the real local frontend. This is a self-review using the anti-ai-web-design visual rubric; the numbers describe template resemblance, not authorship.

| Viewport | A: layout /3 | B: language /2 | C: residue /1 | D: copy /2 | E: specificity /2 | Total /10 |
|---|---:|---:|---:|---:|---:|---:|
| 390 | 1 | 0 | 0 | 0 | 0 | 1 |
| 768 | 1 | 0 | 0 | 0 | 0 | 1 |
| 1440 | 1 | 0 | 0 | 0 | 0 | 1 |

- A=1: the outer preview uses conventional media playback controls. The video itself follows a task-specific instruction rail and real school-registration interface, rather than a landing-page formula.
- B=0: Georgia, Avenir Next, gold, cream and forest green follow the existing website. The authentic PlateMark retains its pointed leaf.
- C=0: the progress rule, cursor, gold leaders and click pulses communicate timing or interaction. There are no decorative metrics, badges or floating ornaments.
- D=0: copy names the actual school contact email, six-digit verification, optional school code, primary administrator, PLATE approval and Login steps. Example values are clearly example data.
- E=0: the form, verification sequence, approval explanation and site assets are specific to this school workflow.

The 768px screenshot exposed a collapsed scene selector; its controls were reflowed to two rows, then fresh screenshots at all three widths were reviewed. The 390px preview keeps the 16:9 video intact and provides usable controls. Detailed website text is best reviewed in the native export or a larger player; responsive preview sizing deliberately does not rearrange the exported composition.

Visual corrections made during review: preserve full verification/login context above the controls; reset native focus scrolling before every capture; derive round corners with circular SVG arcs; trace control borders without expanded overlapping outlines; retain the same path/card throughout animation; draw leaders above the viewport border; fade the outgoing cursor during scene transitions. Explicit browser screenshot scaling and PNG-header checks enforce actual 3840×2160 rasterization before encoding.

The automated browser report checks 103 rendered states, real local form handlers, arbitrary-seek pixel equality, stability beyond the 30-second browser timer, click positions, backend isolation and all three preview widths. Full export checks and final encoded-frame review are recorded separately in the output folder. No external reviewer or unrelated reference-site comparison is claimed.

## Title-only closing sequence

The revised video runs 74.5 seconds. At 65 seconds, the Login hold dissolves into a 9.5-second closing title using the same header, Georgia type, forest background and editorial gold. It names only the next tutorial: “Getting started in your school account.” No future workflow footage or portal interface appears.

Two title lines rise gently into place with a 0.18-second stagger. A thin gold shaft draws left to right, followed by its arrowhead. After a reading hold, the title masks upward and the surrounding header and rules retract. The arrowhead withdraws, and the same gold path bends through circular arcs into the plate's outer ring. The inner ring draws, the native pointed leaf unfurls and the wordmark settles upward. The finished logo and next-video title remain on screen for the final hold; the ending has no fade to an empty screen.

The outer path keeps four cubic segments throughout. Constant-curvature intermediate arcs prevent cusps and preserve continuous tangents. The final 82px centreline radius / 8px stroke and 60px inner radius / 4px stroke match the real PlateMark at four times its native size. The leaf itself is the actual site's CSS component. Empty dash paths are hidden so round line caps cannot leave stray dots. The native 4K motion and signature stills are in `output/tutorial-studio/browser-verification/` and `output/tutorial-studio/signature-review/`; browser checks verify safe bounds, title separation, the leaf's full shape and the terminal signature. The visual language and all three preview scores remain unchanged.
