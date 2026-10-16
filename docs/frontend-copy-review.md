# Frontend copy review — 16 October 2026

Reviewed every maintained frontend file individually, including unused shared components and the archived ecological-map component. The inventory below covers 140 frontend source/content files plus four build/configuration files. Also followed browser messages to their Python sources and reviewed the notification-preferences and map-approval HTML templates. Dependencies, generated `src/static` output, lockfiles, and operational configuration values were excluded.

## Changes

- Removed counter scaling narration, repeated reporting notes, implementation-heavy public-preview labels, redundant form help, and stale rollout messaging.
- Made account and school registration labels distinguish immediate invite creation from approval requests. Clarified that a school superadmin approves member requests. Corrected the use of the registration email: verification, then account signup alerts after approval; no approval-email promise.
- Aligned session-deletion titles, accessible names, and confirmation text with immediate administrator deletion versus member approval requests. Kept permanent-deletion consequences.
- Corrected the guide’s community counter description to clean plates, removed an unsupported “latest” claim on a selected-session page, and corrected an inter-school heading that also contains processed requests.
- Replaced the incorrect “codes are shown once” claim and references to copying an unavailable new-school ID with the supported invite workflow.
- Tightened status messages, estimate help, notification preferences, and map approval copy. Retained privacy controls, roster-replacement consequences, estimate uncertainty/model detail, chart legends, attribution, and reCAPTCHA terms.
- Shortened the downloadable transcript’s editorial preamble. Spoken turns and quoted writing are unchanged. Removed the unused caption CSS rule with its text.

No application permissions, data calculations, transport behavior, recipient configuration, or deployment scripts changed. Two existing test assertions were updated for revised text.

## Verification

- Production build succeeded using `/tmp/goldenplate-copy-build`; no generated production assets were replaced.
- All 81 frontend tests passed.
- 80 targeted backend tests passed (authentication, clean-percentage estimates, ecological map, notification preferences, school contacts, startup notifications). Email transport was mocked by the test suite.
- Broader backend run uncovered two existing failures, both reproduced against original `HEAD` sources in an isolated temporary workspace: `test_school_registration_flow` expects 403 where signed-in registration returns 409; `test_map_recipient_editor_reports_environment_or_no_recipients` expects 200 from an archived endpoint returning 410. These were left outside this copy task.
- Full lint reports 37 existing errors and 11 warnings. The original application hook has the same 30 unused-error-variable failures; seven further errors are in unchanged Node build tests. No new lint finding was introduced.
- Reviewed desktop (1440px) and phone (390px) renders with mocked API data: home, guide, selected guest session, signup and school registration in both modes, community and school counters, range settings, recorder, administrator deletion and member deletion requests, school administration, inter-school administration (empty and populated directory/ledger), map controls, empty/error previews, notification preferences, and map approval confirmation. No document-width overflow occurred. Screenshots are temporary QA artifacts under `/tmp/gp-copy-visual`.
- External media and map requests were blocked during preview QA. Mapbox emitted `Cannot read properties of undefined (reading 'terrain')` in that offline setup; live imagery, Street View coverage, and external embeds were not verified. The archived ecological map is no longer routed from the app; its copy was source-reviewed, not interactively exercised. The confirmation template was rendered separately using sample data.
- Reviewed all seven case-study pages as text, the relevant impact page visually, all six first-party photo/screenshot assets in a contact sheet, and SVG source. Photographic signage and the historical dashboard screenshot were preserved as source material. No visual asset was rewritten.
- `git diff --check` and parsing of changed Python files passed.

## Claim evidence and unresolved items

The supplied St. Andrew’s case study supports the school origin, Compost Coaches, awards/menu requests, staff collaboration, Middle School participation, and reported clean-plate high. Kept the concise “Reported high after launch” label beside 75%. The [official SAC contact directory](https://www.sac.on.ca/contact-us) supports the office address, general email, phone, and business hours. [SAC’s environmental article](https://www.sac.on.ca/news-detail?pk=1541348) identifies Matthew Jaekel’s environmental role. [IBSC’s Golden Plate entry](https://www.theibsc.org/news/stories/friendship) supports the initiative’s peer connections and Middle School mentoring.

The following existing claims remain unchanged because their original evidence could not be independently established in this review:

| Exact wording | Source | Missing evidence |
| --- | --- | --- |
| “A clean plate soon became a symbol of our shared community values.” | `frontend/src/lib/initiative-writing.js`, displayed in `LandingPage.jsx` | Comment attributes this to supplied private writing, archive p. 90; the original writing is not in the maintained public sources. |
| “This experience taught me that joyous communities are built when you create traditions that exemplify your shared values.” | `frontend/src/lib/initiative-writing.js`, displayed in `LandingPage.jsx` | Same original-writing provenance gap. |
| “matthew.jaekel@sac.on.ca” | `frontend/src/components/InitiativeContact.jsx` | The reviewed official directory confirms the general office contact, but does not publish this individual email. No message was sent to verify it. |
| “The winners chose grilled cheese.” | `frontend/src/components/LandingPage.jsx`, Instagram section | The linked reel was not independently reviewed. The photograph itself does not establish this menu claim. |
| “Schools are using PLATE.” | `frontend/src/components/LandingPage.jsx` | The supplied transcript describes multiple schools historically; current multi-school usage cannot be established from this local checkout alone. |
| “The Golden Plate playbook.” | `frontend/src/components/LandingPage.jsx`, newsletter link | The linked newsletter could not be fetched. Its exact contents were not verified. |

The historical podcast statements remain attributed spoken content, not current product guarantees. The edited transcript was not checked against the audio. The case study links to a Green Schools Alliance page that returned 404 during this review; the local PDF remains available and unchanged. These evidence gaps were recorded here rather than turned into new visitor-facing caveats.

## File-by-file frontend inventory

“Reviewed; no authored copy” marks files whose maintained source provides styling, behavior, or passed-through content without its own prose. Standard accessible controls were retained where useful. “Edited” means copy or associated empty styling was changed.

| File | Review |
| --- | --- |
| `frontend/build/mapbox-prebuilt.js` | Reviewed; no authored copy |
| `frontend/build/root-mapbox-env.js` | Reviewed; no authored copy |
| `frontend/eslint.config.js` | Reviewed; no authored copy |
| `frontend/index.html` | Reviewed; retained |
| `frontend/public/resources/golden-plate-podcast-transcript.txt` | Reviewed; edited |
| `frontend/public/resources/plate-student-roster-template.csv` | Reviewed; retained |
| `frontend/public/resources/plate-teacher-roster-template.csv` | Reviewed; retained |
| `frontend/public/theme-init.js` | Reviewed; no authored copy |
| `frontend/src/App.css` | Reviewed; no authored copy |
| `frontend/src/App.jsx` | Reviewed; retained |
| `frontend/src/assets/react.svg` | Reviewed; no authored copy |
| `frontend/src/components/AccountMenu.jsx` | Reviewed; retained |
| `frontend/src/components/AdminSessionExport.jsx` | Reviewed; retained |
| `frontend/src/components/CommunityCounter.jsx` | Reviewed; edited |
| `frontend/src/components/CounterCelebration.jsx` | Reviewed; retained |
| `frontend/src/components/GettingStartedPage.jsx` | Reviewed; edited |
| `frontend/src/components/GuestPrivacySettings.jsx` | Reviewed; retained |
| `frontend/src/components/GuestSessionBoundary.jsx` | Reviewed; retained |
| `frontend/src/components/GuestSessionPage.jsx` | Reviewed; edited |
| `frontend/src/components/HouseEstimates.jsx` | Reviewed; edited |
| `frontend/src/components/HouseRanking.jsx` | Reviewed; retained |
| `frontend/src/components/HouseScoreSettings.jsx` | Reviewed; retained |
| `frontend/src/components/InitiativeContact.jsx` | Reviewed; retained |
| `frontend/src/components/InterschoolPortal.jsx` | Reviewed; edited |
| `frontend/src/components/LandingPage.css` | Reviewed; edited |
| `frontend/src/components/LandingPage.jsx` | Reviewed; edited |
| `frontend/src/components/LegacyHouseEstimates.jsx` | Reviewed; retained |
| `frontend/src/components/LiveCounterPage.jsx` | Reviewed; edited |
| `frontend/src/components/LiveCounterProgress.jsx` | Reviewed; retained |
| `frontend/src/components/LiveCounterSettings.jsx` | Reviewed; edited |
| `frontend/src/components/LoginView.jsx` | Reviewed; edited |
| `frontend/src/components/MainPortal.jsx` | Reviewed; edited |
| `frontend/src/components/MapPortal.jsx` | Reviewed; edited |
| `frontend/src/components/MatchSessionRoster.jsx` | Reviewed; retained |
| `frontend/src/components/Modal.jsx` | Reviewed; no authored copy |
| `frontend/src/components/OverlayElements.jsx` | Reviewed; retained |
| `frontend/src/components/PasswordSettings.jsx` | Reviewed; retained |
| `frontend/src/components/PlaceSearch.jsx` | Reviewed; edited |
| `frontend/src/components/PodcastTranscriptPage.jsx` | Reviewed; retained |
| `frontend/src/components/PortalHeader.jsx` | Reviewed; retained |
| `frontend/src/components/PublicHeader.jsx` | Reviewed; retained |
| `frontend/src/components/PublicSessionDashboard.jsx` | Reviewed; edited |
| `frontend/src/components/RecaptchaNotice.jsx` | Reviewed; retained |
| `frontend/src/components/RosterUpload.jsx` | Reviewed; edited |
| `frontend/src/components/SchoolArrival.jsx` | Reviewed; retained |
| `frontend/src/components/SchoolContactSettings.jsx` | Reviewed; retained |
| `frontend/src/components/SchoolFlightMap.jsx` | Reviewed; retained |
| `frontend/src/components/SchoolGlobe.jsx` | Reviewed; retained |
| `frontend/src/components/SchoolGuestEntry.jsx` | Reviewed; retained |
| `frontend/src/components/SchoolLocationDialog.jsx` | Reviewed; retained |
| `frontend/src/components/SchoolMapPortal.jsx` | Reviewed; retained |
| `frontend/src/components/SchoolRegistration.jsx` | Reviewed; edited |
| `frontend/src/components/SearchableNameInput.jsx` | Reviewed; retained |
| `frontend/src/components/SessionMetrics.jsx` | Reviewed; retained |
| `frontend/src/components/SessionRecordExclusions.jsx` | Reviewed; retained |
| `frontend/src/components/SessionSwitcher.jsx` | Reviewed; edited |
| `frontend/src/components/SignupAccessNotice.jsx` | Reviewed; retained |
| `frontend/src/components/SiteLink.jsx` | Reviewed; no authored copy |
| `frontend/src/components/SiteShell.jsx` | Reviewed; no authored copy |
| `frontend/src/components/StudentRosterUpload.jsx` | Reviewed; no authored copy |
| `frontend/src/components/TeacherNameEditor.jsx` | Reviewed; retained |
| `frontend/src/components/ThemeToggle.jsx` | Reviewed; retained |
| `frontend/src/components/VerificationCodeInput.jsx` | Reviewed; retained |
| `frontend/src/components/WorldMap.css` | Reviewed; no authored copy |
| `frontend/src/components/WorldMap.jsx` | Reviewed; edited |
| `frontend/src/components/ui/accordion.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/alert-dialog.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/alert.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/aspect-ratio.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/avatar.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/badge.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/breadcrumb.jsx` | Reviewed; retained |
| `frontend/src/components/ui/button.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/calendar.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/card.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/carousel.jsx` | Reviewed; retained |
| `frontend/src/components/ui/chart.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/checkbox.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/collapsible.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/command.jsx` | Reviewed; retained |
| `frontend/src/components/ui/context-menu.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/dialog.jsx` | Reviewed; retained |
| `frontend/src/components/ui/drawer.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/dropdown-menu.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/form.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/hover-card.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/input-otp.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/input.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/label.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/menubar.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/navigation-menu.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/pagination.jsx` | Reviewed; retained |
| `frontend/src/components/ui/popover.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/progress.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/radio-group.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/resizable.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/scroll-area.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/select.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/separator.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/sheet.jsx` | Reviewed; retained |
| `frontend/src/components/ui/sidebar.jsx` | Reviewed; edited |
| `frontend/src/components/ui/skeleton.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/slider.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/sonner.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/switch.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/table.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/tabs.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/textarea.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/toggle-group.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/toggle.jsx` | Reviewed; no authored copy |
| `frontend/src/components/ui/tooltip.jsx` | Reviewed; no authored copy |
| `frontend/src/hooks/use-mobile.js` | Reviewed; no authored copy |
| `frontend/src/hooks/useAnimatedCounter.js` | Reviewed; no authored copy |
| `frontend/src/hooks/useCounterFullscreen.js` | Reviewed; no authored copy |
| `frontend/src/hooks/useLiveCounter.js` | Reviewed; retained |
| `frontend/src/hooks/usePlateApp.js` | Reviewed; edited |
| `frontend/src/hooks/usePublicCounter.js` | Reviewed; retained |
| `frontend/src/hooks/usePublicSession.js` | Reviewed; retained |
| `frontend/src/index.css` | Reviewed; no authored copy |
| `frontend/src/lib/EnglishScaleControl.js` | Reviewed; retained |
| `frontend/src/lib/counter-animation.js` | Reviewed; no authored copy |
| `frontend/src/lib/counter-visibility.js` | Reviewed; no authored copy |
| `frontend/src/lib/globe-animation.js` | Reviewed; no authored copy |
| `frontend/src/lib/globe-origin.js` | Reviewed; no authored copy |
| `frontend/src/lib/guest-session.js` | Reviewed; no authored copy |
| `frontend/src/lib/house-ranking.js` | Reviewed; no authored copy |
| `frontend/src/lib/initiative-writing.js` | Reviewed; retained |
| `frontend/src/lib/live-counter.js` | Reviewed; retained |
| `frontend/src/lib/mapCoordinates.js` | Reviewed; retained |
| `frontend/src/lib/mapLayers.js` | Reviewed; retained |
| `frontend/src/lib/mapView.js` | Reviewed; no authored copy |
| `frontend/src/lib/names.js` | Reviewed; no authored copy |
| `frontend/src/lib/navigation.js` | Reviewed; retained |
| `frontend/src/lib/podcast-transcript.js` | Reviewed; retained |
| `frontend/src/lib/recaptcha-client.js` | Reviewed; retained |
| `frontend/src/lib/recaptcha.js` | Reviewed; retained |
| `frontend/src/lib/record-submission.js` | Reviewed; retained |
| `frontend/src/lib/school-flight.js` | Reviewed; no authored copy |
| `frontend/src/lib/schoolMap.js` | Reviewed; retained |
| `frontend/src/lib/session-metrics.js` | Reviewed; no authored copy |
| `frontend/src/lib/utils.js` | Reviewed; no authored copy |
| `frontend/src/main.jsx` | Reviewed; no authored copy |
| `frontend/src/theme.css` | Reviewed; no authored copy |
| `frontend/vite.config.js` | Reviewed; no authored copy |

## Server-provided UI sources

Reviewed browser-facing messages across `src/routes/golden_plate_recorder_db`, following the frontend fetch destinations and estimate/roster helpers. The full browser templates are maintained in `notification_routes.py` and `map_routes.py`; notification preference labels come from `src/services/notification_preferences.py`. Also checked the retained legacy recorder and CSV route strings. Application internals, console logs, and email bodies were not rewritten as frontend copy.
