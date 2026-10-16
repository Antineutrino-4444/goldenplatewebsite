# Dark mode

The public and school portal headers now include an Appearance menu with Light,
Dark, and Use device setting. The default follows the device. Choices are saved
in this browser under `goldenplate.theme`, shared across tabs, and applied before
first paint. The existing next-themes dependency manages later device changes
and persistence. Blocked storage falls back to device preferences.

The design preserves Golden Plate's green and gold identity, real dining-hall
photographs, formal initiative content, routing, counters, and school workflows.
Deep green paper, warm light ink, restrained surface separation, and gold focus
rings extend the existing design. No layout rebuild, decorative gradients, new
imagery, or invented content was needed. Prior issues were the lack of an
appearance control, hard-coded pale surfaces, and dark text unsuitable for a
dark background. Shared palette tokens now cover public pages and authentication;
semantic component tokens cover cards, menus, dialogs, and inputs. Explicit
utility mappings support the recorder's older neutral and status classes.

The four recording categories retain their colors, with darker action backgrounds
for white labels. Calculated text contrast is 15.41:1 for body text, 8.66:1 for
muted text on cards, 5.56:1 for primary buttons, and 5.11–5.93:1 for category
buttons. Navigation and form behavior remain the same. The portal wordmark stays
on one line on phones; narrow-phone Live and Map links retain their text while
omitting their redundant icons to leave room for the theme control.

Map lighting follows the resolved theme through Mapbox's existing light preset.
Changing appearance retains the Map instance and camera. Hybrid remains the
initial basemap; English labels and the CN worldview are preserved. DOM map
controls, popups, and layer choices use the dark surfaces. Media embeds remain
under their providers' control; images and video are not inverted or filtered.
The satellite login flight retains its existing presentation and four-second
camera sequence.

## Verification

- All 70 frontend tests pass, including first-paint defaults, saved overrides,
  unavailable/invalid storage, map lighting and map-instance retention.
- Focused lint and the production build pass.
- Browser checks verified saved Dark after reload, Light overriding a dark
  device preference, and live device changes in Use device setting mode.
- Actual dark screenshots were reviewed at 390, 768, and 1440 pixels. Mobile
  navigation and header controls fit without horizontal overflow. A 951px
  breakpoint check also fits.
- Reviewed the recorder, recording dialog (cancelled without saving), map and
  layers, community counter, school counter, fullscreen entry/exit, login, and
  school registration. No registration email was sent. The configured reCAPTCHA
  key rejects localhost, so actual registration submission was not attempted.
- Browser viewport and emulated device preferences were restored after QA.

## Visual review

The existing photograph-led composition is retained. The de-AI skill score is a
subjective template-pattern assessment, not an authorship claim. Source and
initial light captures informed a provisional baseline; final dark captures were
reviewed directly on 16 October 2026. No independent reviewer was used.

| Width | Baseline (provisional) | Dark (rendered) | A/B/C/D/E |
| --- | --- | --- | --- |
| 390px | 2/10 | 2/10 | 1/0/0/0/1 |
| 768px | 2/10 | 2/10 | 1/0/0/0/1 |
| 1440px | 2/10 | 2/10 | 1/0/0/0/1 |

The remaining conventional elements are the large headline above a documentary
photograph (A=1), and a broadly reusable introductory composition (E=1). Actual
Compost Coach photographs, the award/menu tradition, specific school context,
and live recorder data give the page its subject specificity. Gold remains the
plate identity and focus color. Removing these authentic artifacts would reduce
clarity; no new decoration was added. This change addresses theme usability,
with no claim of a structural aesthetic redesign.
