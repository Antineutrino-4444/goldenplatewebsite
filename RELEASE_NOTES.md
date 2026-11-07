# Golden Plate release notes

<!-- golden-plate-release-baseline: 1.2.5.2 c21404b48430c1fa62d2dbe0bf1a3715db2f5914 -->

Historical versions were assigned retrospectively from the main branch using their commit dates. New entries use the date they are prepared in Eastern Time.

## 1.2.5.2

November 7, 2026 · Current-roster ranking fixes and clearer error details

Author: Jiajun (Leo) Li

- Fixed former students remaining in Plate Leaderboards when an older database still marked them active. Student rankings, displayed win chances, and House Rankings ticket totals now require membership in the school's saved current roster. The fix also applies to guest plate rankings; a missing or empty current roster leaves student rankings empty.
- Creating a session no longer adds historical student identities back into an existing current roster. Uploading a replacement roster updates its membership, while past plate records remain available.
- For newly logged SQLite duplicate-constraint failures, Server Log now includes the affected database table and column names when they match the application's schema. Inter-school administrators can use these details to investigate recording failures without exposing submitted values or SQL parameters.

## 1.2.5.1

November 7, 2026 · Leaderboard colors

Author: Jiajun (Leo) Li

- First place in the Tickets and Clean Plates rankings now uses gold highlights. Very Dirty Plates uses red for counts, ranking bars, and the first-place card.

## 1.2.5.0

November 6, 2026 · School-wide Plate Leaderboards

Author: Jiajun (Leo) Li

- Open Plate Leaderboards from the school portal navigation. The page works independently of the Recorder’s selected session. Each ranking includes only current roster members and uses activity since the latest upload for that roster, even for people who appeared on earlier rosters.
- Search by name or a displayed roster ID to see how many people match across the full ranking. Matches keep their original ranks. To jump directly to a page, type its number and select Go.
- For signed-in users, each row shows one ticket total. Win chance uses current-roster balances and qualifying clean plates for the latest active session’s unfinished draw. If that draw is finalized or there’s no active session, the page shows a projection for the next draw. Guest standings use public sessions and anonymize names when the school enables guest privacy.

## 1.2.4.0

November 6, 2026 · Plate Leaderboards and faculty ticket draws

Author: Jiajun (Leo) Li

- Open Plate Leaderboards in the Recorder to compare students and teachers across sessions by Tickets or Clean Plates. The Very Dirty Plates tab ranks students. Signed-in users can search by name or displayed roster ID, and IDs appear when ranked names repeat and an ID is available.
- Each signed-in ranking shows plate counts, ticket balance, finalized wins, and win chance where applicable. Student entries also show the share of their recorded plates that were clean. Win chance uses the current unfinished draw, the next eligible session, or a projection from current balances if no eligible session is available. Guests can see plate rankings based on public sessions, with roster IDs, ticket balances, and draw odds hidden.
- In Draw Center, school admins and superadmins can run and finalize separate Faculty Ticket Draw and Student Ticket Draw results. Each section shows the top three candidates, the eligible list, the selected winner, and its own draw history. School superadmins can override a faculty winner or reset a finalized faculty draw from Faculty draw options.
- Faculty win chances are weighted by eligible tickets. Teachers on the roster carry tickets across sessions and need a qualifying clean plate in the session being drawn. Faculty entered by name can earn tickets for that session. Finalizing a faculty winner resets the winner’s applicable ticket balance.
- House Rankings has a Tickets tab that totals the current ticket balances of students assigned to each house. Updated ranking bars show how scores and clean rates compare, and Estimates marks the predicted values and ranges.
- The macOS local deployment launcher is now named `deploy_local.command`.

## 1.2.3.0

November 5, 2026 · Live Server Log and clearer error messages

Author: Jiajun (Leo) Li

- Inter-school administrators can open Server Log under Inter-School Administration to see requests from signed-in users, guests, and anonymous visitors across schools. The log refreshes every three seconds and shows when each request ran, what action it performed, and how long it took.
- Use Find an action to search by account, school, route, error code, or reference. Select Failures only to narrow the results, Pause to hold the feed, or Jump to latest to return to the newest requests. The live view shows up to 200 matches. Export CSV downloads all matching entries from the last 30 days.
- Error messages across the site now include codes when a server request fails. Server errors also include a reference for that occurrence, which inter-school administrators can look up in Server Log when helping someone troubleshoot.
- The Recorder now retries some brief database conflicts. When two staff members submit the same plate at nearly the same time, the second submission can receive the usual duplicate message. If the Recorder can’t confirm whether a plate was saved, it directs staff to check Plate Tracking History before trying again.

## 1.2.2.0

November 4, 2026 · Public release history and multi-file roster imports

Author: Jiajun (Leo) Li

- Open Release history from the public site footer or the portal’s account menu to browse every published version. Each version has a link you can share, and anyone can read the history without signing in.
- Golden Plate emails new release notes to admin and superadmin account addresses and any additional recipients configured for website updates. When several versions are published together, the email includes up to three entries and links to the full history. Recipients can manage Release notes in their email preferences.
- Admins and superadmins can combine up to 10 files into one student or faculty roster. In the Recorder, open Student and teacher databases and select Choose files or Add files. Review shows which files are ready and which need attention. You can preview each file, choose a sheet or table when prompted, adjust its column assignments, or remove it before importing.
- Roster review flags duplicate student or faculty IDs across files before saving. If you select Generate student IDs from row order, numbering continues across the selected files. The combined roster can contain up to 20,000 rows.
- Help icons beside controls explain how to sign in, register a school, and find or place a school on the map. In the portal, they also explain roster column matching, why Start Draw may be unavailable, and what to check before sharing a session export. Some tips link to a video guide.

## 1.2.1.1

November 4, 2026 · Spreadsheet roster import and portal release notes

Author: Jiajun (Leo) Li

- Golden Plate now shows release notes in the school portal. If you miss a release, you’ll see its notes alongside the newer updates when you next sign in.
- Select Got it to acknowledge the displayed releases on your account across devices. Closing the dialog leaves those entries unread for your next sign-in.

- Admins could import student or faculty rosters from CSV, TSV, Excel (.xlsx or .xls), Apple Numbers, and delimited text. For workbooks with several sheets or tables, the review let admins choose which one to use.
- The review suggested matches for recognized headings. Admins could assign columns by hand for files with unfamiliar headings or no header, and choose whether to exclude the first row as a heading or title.
- The preview showed source row numbers and marked the columns assigned to each roster field. Admins could page through 20 rows at a time and verify the selection before saving.
- Both rosters required a first or preferred name and a last name. For students, grade, advisor, house, and clan were optional. Faculty imports could also map a stable Faculty ID to keep records linked through name changes.
- Student imports could use an existing Student ID column or generate sequential IDs from row order. When the same students would be uploaded again in a different order, the review advised using stable IDs.
- Missing required values and duplicate IDs were reported by row. Reviewing or canceling an upload left the current roster in place.
- Replacing a roster preserved past plate records and draw logs. Students missing from the new roster were excluded from future roster-based ticket draws.

## 1.2.0.0

October 25, 2026 · Video guides across Golden Plate

Author: Jiajun (Leo) Li

- Added The school video guide to Getting Started. The library included 32 short videos with titles and runtimes, a keyword search, and a Topic filter covering seven areas from first-time setup to managing partner schools.
- Each guide could play on the same page or open on YouTube. The library also linked to the full playlist, and each contextual help section linked back to the library.
- Added Watch this step to the written Getting Started chapters. New schools could watch registration and first-login walkthroughs, while staff joining an existing school could jump to invites, account setup, and their first session.
- Added help alongside everyday Recorder controls. Staff could watch how to load student and faculty rosters, create and switch sessions, record different types of plates, and correct entries in Plate Tracking History.
- Added videos for reading house rankings and estimates, understanding tickets, and running and finalizing draws. The Session Dashboard linked to walkthroughs for reading results, exporting session reports, and discarding or deleting sessions. School admins also had guides for combining sessions and exporting several at once.
- Added administrator videos on managing school accounts, setting email rules, and keeping passwords secure. The Inter-School Control Center linked to videos on reviewing registrations, inviting partner schools, and managing schools.
- Added guides at the Live Counter, guest views, and School Map so people could learn how to set up a display, share results safely, place their school on the map, or explore other schools.

## 1.1.4.4

October 24, 2026

Author: Jiajun (Leo) Li

- Clarified the empty recorder message when a guest’s school had no public sessions.

## 1.1.4.3

October 24, 2026 · School approval and signup email confirmation

Author: Jiajun (Leo) Li

- Added a school approval email so the applicant could see that registration had been accepted.
- The approval still created the school and its lead administrator if email delivery failed. The inter-school reviewer saw a warning asking them to let the applicant know they could sign in.
- On their first sign-in, a school superadmin with a verified signup address could keep it or verify a different address.

## 1.1.4.2

October 23, 2026 · Collapsible inter-school sections

Author: Jiajun (Leo) Li

- Made the Inter-School Control Center sections collapsible so administrators could focus on the school, request, or invite list they were using.

## 1.1.4.1

October 23, 2026 · Inter-school overview loading

Author: Jiajun (Leo) Li

- Fixed the Inter-School Control Center so the school, registration, and invite lists loaded immediately after sign-in.
- The sections showed loading messages while fetching data, and pending registration requests appeared before completed decisions.

## 1.1.4.0

October 22, 2026 · Draw eligibility for name-only records

Author: Jiajun (Leo) Li

- Named clean-plate entries could join the Draw Center even when no student roster row matched the person.
- This covered names entered by hand and clean records entered with an ID that matched no student. The Draw Center could select and finalize those entries alongside roster participants.
- The name-only participant’s tickets stayed within the session. Their draw eligibility could be removed or restored through the existing record exclusion controls.

## 1.1.3.0

October 20, 2026 · Cloudflare Turnstile

Author: Jiajun (Leo) Li

- Switched bot protection to Cloudflare Turnstile for account signup, verification flows, and password recovery.
- The forms displayed a challenge when needed and let users retry when verification expired or failed.

## 1.1.2.3

October 19, 2026 · Pending request badges

Author: Jiajun (Leo) Li

- Added badges for pending school admin requests so staff could see when action was needed from the portal header.
- The counts refreshed while the portal was open.

## 1.1.2.2

October 19, 2026

Author: Jiajun (Leo) Li

- Fixed a CAPTCHA timing check that could reject valid verification attempts.

## 1.1.2.1

October 19, 2026

Author: Jiajun (Leo) Li

- Showed account emails to school superadmins in user lists.

## 1.1.2.0

October 19, 2026 · Email sign-in and password recovery

Author: Jiajun (Leo) Li

- Members could sign in with their username or a verified email and their password. Accounts sharing an email address could continue using their usernames.
- The Forgot password? dialog gave members a choice between asking their school superadmin for help and requesting a recovery link at an address they had already verified. Members who shared an email address could use their username to start recovery.
- The link could be used once within 20 minutes. After choosing and confirming a new password, other devices were signed out, and members returned to sign-in with the new password.

## 1.1.1.0

October 19, 2026 · Inactive accounts and account deletion

Author: Jiajun (Leo) Li

- Added inactivity notices and a Disabled Accounts panel. Eligible accounts could be disabled after 60 days without a verified email or 120 days with one, with a 30-day recovery window before ordinary inactive accounts could be deleted.
- Verified account owners could receive reminders before disablement and again before deletion. Disabled Accounts showed the reason, the scheduled date or review date, and whether a failed email delivery was awaiting retry.
- School administrators could review and recover disabled accounts within their school. Admin accounts required deletion review. School superadmins and inter-school administrators were exempt from automatic inactivity actions.
- Added a credential check and two confirmations for account deletion. Deletion removed the account and sign-in while preserving school plate records and sessions.

## 1.1.0.0

October 18, 2026 · Verified account emails and school email rules

Author: Jiajun (Leo) Li

- New members verified their email by code when applying, including through an invite. Existing members could verify or update their account address.
- School admins could enable School Email Rules and allow specific domains, addresses, or exceptions. Applicants outside those rules received feedback before a code was sent.
- Allowed domains matched exactly, so an administrator who wanted to accept a subdomain could list it separately. An individual exception still had to verify its address with a code.
- In schools that required an approved address, affected existing members were asked to verify before continuing into the portal. Members could sign out from that prompt.
- School superadmins could require an admin at their school to verify again on the next sign-in.

## 1.0.2.4

October 18, 2026 · Globe arrival on portal pages

Author: Jiajun (Leo) Li

- Extended the school arrival animation to additional portal routes.
- Shortened the zoom at the end of the flight so staff could get to the destination page sooner.

## 1.0.2.3

October 18, 2026

Author: Jiajun (Leo) Li

- Made the school arrival animation move more quickly.

## 1.0.2.2

October 16, 2026 · Clearer portal guidance

Author: Jiajun (Leo) Li

- Updated Getting Started to distinguish school registration, account requests, and legacy invites, and to explain who reviews each request.
- Clarified when the Live Counter was reconnecting, what public session results showed, and how to select the default counter view.
- Made the assumptions behind house estimates and manually matched rosters easier to find.

## 1.0.2.1

October 16, 2026 · Globe and counter polish

Author: Jiajun (Leo) Li

- Smoothed the globe’s movement and refined the scale on the community counter.
- Clarified how to open a school’s guest view, export roster data, and interpret overlapping house estimate ranges.

## 1.0.2.0

October 16, 2026 · Light and dark appearance

Author: Jiajun (Leo) Li

- Added an Appearance menu with Light, Dark, and Use Device Setting choices across the public site and school portals.
- Updated the public site and signed-in layouts, including navigation, map controls, registration forms, guest views, and both the school and community counters, for dark mode.
- Slowed the school arrival animation so visitors had more time to follow the globe as it moved toward their school.

## 1.0.1.0

October 16, 2026 · Permanent faculty identity

Author: Jiajun (Leo) Li

- Added Faculty ID and an Edit Name action so admins could update a teacher’s preferred or last name without disconnecting earlier plate records or draw results.
- Faculty members with identical names could stay separate. Historical records retained the name originally recorded, even when the portal showed the updated display name.
- Set a consistent starting view for the globe before the school arrival animation.

## 1.0.0.4

October 16, 2026

Author: Jiajun (Leo) Li

- Shortened the globe animation when opening a school and skipped the long turn when the school was already nearby.

## 1.0.0.3

October 16, 2026 · Separate faculty name fields

Author: Jiajun (Leo) Li

- Teacher imports stored first or preferred names separately from last names.
- The portal could display faculty names from those fields instead of relying only on a single combined name.

## 1.0.0.2

October 16, 2026 · Community counter and globe timing

Author: Jiajun (Leo) Li

- Adjusted the community counter scale and when the counter became visible as users scrolled.
- Refined the globe’s timing when opening a school and updated the public session display.

## 1.0.0.1

October 16, 2026 · Teacher file headings

Author: Jiajun (Leo) Li

- Required name column headings for teacher CSV and TXT uploads.
- Updated the upload instructions and validation feedback so admins could fix the file before trying again.

## 1.0.0.0

October 16, 2026 · The REAL Golden Plate website

Author: Jiajun (Leo) Li

- Rebuilt the homepage around how schools run Golden Plate. The site showed how Compost Coaches record plates at dish return, how winners help choose Friday’s menu, and what the initiative looked like at St. Andrew’s College.
- Added dedicated pages for the initiative’s story, How It Works, Getting Started, and Stories. Visitors could explore the case study, watch the initiative video, or read a podcast transcript. The written guide walked schools from registration through their first lunch session.
- Added a public navigation menu linking to the School Map, Live Counter, school sign-in, and initiative pages. The Recorder, Session Dashboard, and school administration each gained their own portal page, while school registration and member signup became separate entry points.
- Added a public community Live Counter showing the combined all-time clean plates recorded by students and faculty across schools. Schools retained their own Live Counter display.
- The homepage loaded an example from a randomly selected public school session. Its dashboard showed total records, clean and dirty counts and rates, and separate counts for very dirty plates and faculty clean plates.
- Added shareable links to individual public sessions. Anyone with a link could see the aggregate dashboard without switching accounts or seeing participant names. Links stopped showing results if the school made the session unavailable to guests.
- School Map visitors could open a participating school’s guest portal directly from its entry. The site also introduced a globe animation that traveled toward the school when visitors entered its portal.

## 0.7.10.0

October 16, 2026 · House rank ranges and safer recording

Author: Jiajun (Leo) Li

- House estimates began showing a range of possible ranks alongside the predicted order so readers could see where intervals overlapped.
- A house with a higher predicted rate could still overlap with another house in the rank range. The display kept ties and uncertainty visible while staff recorded more plates.
- Plate saves updated the totals and duplicate checks only after the record was saved. A failed save could be retried without a false duplicate or an extra count.
- If the save succeeded but refreshing the lookup failed, the recorder reported the save accurately. An unmatched student ID remained a manual entry in later sessions.

## 0.7.9.0

October 15, 2026 · The public School Map

Author: Jiajun (Leo) Li

- Replaced Ecological Map posts and moderation with a globe and directory of participating schools. Visitors could search by school code or name and see activity from shared sessions.
- Schools with saved locations appeared as pins. Schools without a location remained discoverable in Others.
- Added globe and flat map views, zoom and pan controls, a Show schools action, and a school pin toggle. Larger, more golden pins showed schools with more public sessions.
- Search could find a participating school by its code or preview a place on the map. The school list was still available when the interactive globe could not load.
- School superadmins could set their own pin, place it manually, or choose to remain unmapped. Inter-school admins could manage locations across schools.
- An explicit choice to remain unmapped stopped location reminders and kept the school in Others. Schools could reverse that choice later.

## 0.7.8.1

October 14, 2026

Author: Jiajun (Leo) Li

- Enabled Guest Privacy by default for newly registered schools.

## 0.7.8.0

October 14, 2026 · Guest Privacy

Author: Jiajun (Leo) Li

- School admins could use Guest Privacy to hide participant names from guests. Consistent aliases kept guest-facing history and draw views readable.
- School staff continued to see the real identities. Guests remained restricted from roster and export tools.

## 0.7.7.1

October 11, 2026

Author: Jiajun (Leo) Li

- Recognized roster grade labels such as Gr. 9 as well as Grade 9 or 9 when determining which students belonged in the Upper School estimate.

## 0.7.7.0

October 11, 2026 · Upper School clean-rate estimates

Author: Jiajun (Leo) Li

- Added a separate clean-rate model for grades 9–12 using the session’s saved roster. The rate estimated clean plates among participants, with assumed absences shown separately.
- The model kept known house records in place and allocated anonymous plates among eligible students. While staff were still counting, a gap between the roster and the recorded plates appeared as assumed lunch absences.
- House cards displayed predicted rates, ranks, and individual 90% prediction intervals. The results updated as records arrived, and equal predicted rates rounded to three decimals shared a rank.
- The estimate also showed the chance a house had no participating students. The detailed view explained the model’s assumptions and what interval coverage would be needed to separate the displayed ranking.
- Older sessions without the required history showed why the estimate was unavailable. Existing manual roster matches could still be used, and the portal identified cases where it used linked student profiles because the saved roster had no grades.

## 0.7.6.0

October 11, 2026 · Student history in exports

Author: Jiajun (Leo) Li

- Detailed exports retained student details as recorded at the time, even if a later roster changed the student’s name, grade, or house.
- A later roster could help explain a change without filling in a field that had originally been blank. Older records were matched using their ID first, with uncertainty flagged when the history could not distinguish students who shared a name.
- Anonymized exports masked identifying values in roster notes as well as in the selected fields.

## 0.7.5.0

October 11, 2026 · Detailed exports across sessions

Author: Jiajun (Leo) Li

- Admins could select which sessions to include, see how many records they were about to export, and optionally skip discarded sessions.
- The download could be one CSV with session sections or a ZIP with one CSV per session. A selected empty session still appeared in the export.
- Admins could anonymize specific columns, names only, or all available columns. A consistent Person label let staff follow the same student across sessions within the download, including students who shared a name. Labels changed for each new export.
- Individually excluded rows were left out, and a merged session exported its own records so the same entries would not appear twice.

## 0.7.4.4

October 11, 2026 · Readable account names

Author: Jiajun (Leo) Li

- Replaced opaque account labels with readable display names and usernames across school and inter-school views.
- The labels also appeared in session ownership, draw history, and exports so staff could recognize who took an action.

## 0.7.4.3

October 10, 2026

Author: Jiajun (Leo) Li

- Clarified the House Data cards, estimate explanations, and roster matching prompts.

## 0.7.4.2

October 10, 2026 · Estimated house order

Author: Jiajun (Leo) Li

- Showed a house’s rank by its estimated score alongside its prediction range.
- This let readers follow the estimated order while still seeing when the model could not clearly separate houses.

## 0.7.4.1

October 10, 2026 · Review before matching

Author: Jiajun (Leo) Li

- Let superadmins compare records against the current roster without replacing the roster already saved for the session.
- After resolving conflicts, admins could retry Use Current Roster to complete the match.

## 0.7.4.0

October 10, 2026 · Reversible record exclusions

Author: Jiajun (Leo) Li

- Superadmins could use Roster Conflicts and Exclusions to review a session’s records and remove individual entries from calculations.
- The review distinguished all records from excluded records. A superadmin could inspect a conflict and restore an excluded record without re-entering it.
- An exclusion updated session totals, the Live Counter, house estimates, exports, and draw eligibility. Excluding a rostered student removed that record from the estimate without treating the student as absent.
- If the excluded record made a selected winner ineligible, the affected selection could be cleared while the draw history remained available. Exclusions in an extra session could also affect the main session’s draw.

## 0.7.3.1

October 10, 2026 · Estimates with missing houses

Author: Jiajun (Leo) Li

- Kept school-level estimates available when some roster rows lacked house data.
- Showed unassigned entries separately so they did not appear as a ranked house.

## 0.7.3.0

October 10, 2026 · Match a session to a roster

Author: Jiajun (Leo) Li

- Authorized school admins could use the current roster to match an older session whose saved roster was missing or unsuitable.
- The portal checked for conflicts before saving the match. An unsuccessful match left the prior roster assignment in place.

## 0.7.2.0

October 10, 2026 · Roster-based house estimates

Author: Jiajun (Leo) Li

- Added estimates based on each session’s recorded plates and roster membership. Saving the roster with the session kept later roster changes from rewriting earlier estimates.
- Known house assignments stayed with their recorded plates. The model used the remaining roster to estimate where anonymous outcomes and assumed absences could fall.
- Displayed score, dirty-plate, and absence ranges. A house was shown as clearly ahead only when its score range separated from the other house’s range.
- Older sessions without a saved roster, or sessions recorded across incompatible roster changes, showed why an estimate was unavailable.

## 0.7.1.2

October 10, 2026 · Fullscreen display refinements

Author: Jiajun (Leo) Li

- Adjusted the fullscreen layout so the counter and its progress display fit a larger viewing area.
- Improved fullscreen controls and colors so staff could switch views during a presentation.

## 0.7.1.1

October 10, 2026

Author: Jiajun (Leo) Li

- Made Live Counter percentages display with consistent precision.

## 0.7.1.0

October 10, 2026 · Counter metrics and fullscreen

Author: Jiajun (Leo) Li

- Added a choice between a clean-plate count and clean percentage. Superadmins could choose which view opened by default and set independent celebration goals for both.
- The percentage view could celebrate a rate from 0.1% to 100%. A school could leave either goal blank to turn off that celebration while keeping the other goal.
- Added fullscreen for larger displays and let the banner insert the current goal in the selected view’s format.
- Teacher imports recognized separate name columns in CSV files and preserved the saved roster when the uploaded file did not pass validation.

## 0.7.0.1

October 10, 2026 · Counter banner and discarded sessions

Author: Jiajun (Leo) Li

- Superadmins could set a celebration banner title, message, and closing line. The message could insert the current milestone automatically, and leaving a field blank restored that field’s default.
- Discarded sessions stopped contributing to the counter. Restoring a session brought its records back into the displayed totals.

## 0.7.0.0

October 10, 2026 · Live Counter and House Scoring

Author: Jiajun (Leo) Li

- Added a school Live Counter that updated as staff recorded clean plates. It included student, faculty, and count-only clean plates for the selected period.
- Admins could set the calendar year, school time zone, and up to three custom date ranges. Both endpoints counted, so a range could cover a full term or a single event day.
- Superadmins could choose the default range and set a school celebration milestone. Guests could enter a school code to see totals from public sessions.
- Added House score settings for superadmins. Schools could give clean plates a reward and choose separate deductions for dirty and very dirty plates, using whole numbers from 0 to 20.
- Point changes recalculated scores in both active and archived sessions. Count-only records and records without a house contributed to plate totals without earning house points.
- Updated the student and faculty roster upload formats so staff could keep the information used for recording and house calculations current.

## 0.6.9.0

October 9, 2026 · Roster replacement and draw safeguards

Author: Jiajun (Leo) Li

- Added a searchable student database preview and a confirmation step before replacing the uploaded roster.
- The preview showed the saved filename and searched across the whole roster. A rejected upload left the existing student list in place.
- Students removed from a replacement roster stopped appearing in roster-based draw paths. Older records remained available.
- Improved how legacy house labels were grouped, and corrected dirty plate rates to use each house’s own total.
- Finalized faculty results survived a restart. Redrawing a finalized student or faculty winner required confirmation, and earlier draw actions stayed in the history.
- Added private email preference links so recipients could opt out of selected notifications and still receive codes they requested.

## 0.6.8.0

October 9, 2026 · Count-only plate records

Author: Jiajun (Leo) Li

- Staff could record a plate even when they did not know the student or faculty member’s name.
- Leaving the identity field blank added one count in the selected category. Unnamed clean and faculty clean plates still counted toward the totals and could be recorded more than once.
- Named entries remained available for tracking an individual. Count-only records did not create a named draw entry or affect a student’s ticket balance.

## 0.6.7.0

October 9, 2026 · School contact email and startup notices

Author: Jiajun (Leo) Li

- School superadmins could set their school’s contact email from the account menu. They received a reminder in the portal if it was missing.
- Account signup alerts, including invite signups, went to the relevant school’s contact when configured.
- Configured website recipients could receive an announcement when the application started. The message reported application startup rather than whether the public site was reachable.

## 0.6.6.1

October 9, 2026

Author: Jiajun (Leo) Li

- Made website alert recipients also receive map submission notices alongside any additional map reviewers.

## 0.6.6.0

October 9, 2026 · Password tools and signup alerts

Author: Jiajun (Leo) Li

- Added My Password for changing a signed-in user’s password and Other Accounts for authorized staff to reset an eligible account. Resetting another account required the administrator to confirm their own password.
- Switched signup verification to a less intrusive CAPTCHA flow.
- Added email alerts when new school registration or account signup requests arrived.

## 0.6.5.2

October 9, 2026

Author: Jiajun (Leo) Li

- Fixed interaction with the CAPTCHA challenge inside the signup dialog.

## 0.6.5.1

July 3, 2026

Author: Jiajun (Leo) Li

- Removed built-in administrator sign-in credentials from production.

## 0.6.5.0

July 3, 2026 · Password storage and account lists

Author: Jiajun (Leo) Li

- Protected stored passwords with hashing, including existing credentials during migration.
- Removed the password field from account management views.

## 0.6.4.3

April 28, 2026

Author: Jiajun (Leo) Li

- Made map approval links report the existing approval if opened again.

## 0.6.4.2

April 28, 2026 · Confirm map approval

Author: Jiajun (Leo) Li

- Quick-approve email links opened a confirmation page showing the action the reviewer was about to take.
- Approval was submitted after confirmation, so simply opening a link did not approve the post.

## 0.6.4.1

April 28, 2026 · Image previews in review emails

Author: Jiajun (Leo) Li

- Improved image attachments in map approval emails and added inline previews where supported.
- Reviewers could see more of the submission before opening it on the site.

## 0.6.4.0

April 27, 2026 · Map review by email

Author: Jiajun (Leo) Li

- Map admins could view and edit the approval email recipient list from the map administration interface.
- The editor showed the active recipient list, whether it came from saved map settings or site configuration, and when the saved list was last changed.
- New submission alerts included submission details and a quick-approve link so a reviewer could act from the email.

## 0.6.3.6

April 27, 2026

Author: Jiajun (Leo) Li

- Added a direct login page for people arriving from the map.
- New submissions awaiting approval could notify configured reviewers by email, so reviewers could learn about a submission without repeatedly checking the queue.

## 0.6.3.5

April 26, 2026

Author: Jiajun (Leo) Li

- Updated the recorder’s Ecological Map link to open the map site.

## 0.6.3.4

April 26, 2026

Author: Jiajun (Leo) Li

- Made the Ecological Map available on its own subdomain and fixed its page routing.

## 0.6.3.3

April 25, 2026 · Mobile portal and map layouts

Author: Jiajun (Leo) Li

- Adjusted the recorder, map, and inter-school administration layouts for smaller screens.
- Improved how login, registration, verification code fields, and dialogs fit on phones.

## 0.6.3.2

April 25, 2026

Author: Jiajun (Leo) Li

- Expanded the lightbox to use most of the browser window, with more space for the photo and its filename and position in the gallery visible above it.
- Made the previous and next buttons larger. Using them or the zoom controls no longer started a drag on the image underneath.

## 0.6.3.1

April 25, 2026 · More map image formats

Author: Jiajun (Leo) Li

- Expanded accepted uploads to formats including AVIF, TIFF, SVG, and camera RAW. Images that needed conversion could be prepared for preview before submission.
- Added previous and next controls and position indicators for browsing featured posts.

## 0.6.3.0

April 25, 2026 · Featured map posts

Author: Jiajun (Leo) Li

- Superadmins could feature approved posts, and visitors could browse the highlighted posts on the map.
- Expanded the contributor display to show the full list of contributors with approved posts.

## 0.6.2.4

April 25, 2026

Author: Jiajun (Leo) Li

- Removed empty pins when only rejected submissions remained attached.

## 0.6.2.3

April 25, 2026

Author: Jiajun (Leo) Li

- Fixed map pins failing to refresh after submissions loaded.

## 0.6.2.2

April 25, 2026 · Map deletion feedback

Author: Jiajun (Leo) Li

- Reviewers could add a comment when deleting a submission.
- The submitter received an email explaining the decision when email delivery was available.

## 0.6.2.1

April 25, 2026

Author: Jiajun (Leo) Li

- Showed multiple image previews and submission statuses in the Ecological Map.

## 0.6.2.0

April 25, 2026 · Multiple images per map post

Author: Jiajun (Leo) Li

- A single Ecological Map submission could include several images.
- Visitors and reviewers could open the gallery in a lightbox and browse the photos without leaving the post.

## 0.6.1.10

April 25, 2026

Author: Jiajun (Leo) Li

- Improved drag-and-drop image handling and let reviewers email submitters before confirming a rejection.

## 0.6.1.9

April 25, 2026 · Upload progress and rejection notices

Author: Jiajun (Leo) Li

- Displayed a progress bar for HEIC photos that distinguished the upload from the decoding step before preview. This also applied when using a HEIC image in the background editor.
- Added email feedback to submitters when a reviewer rejected their post.

## 0.6.1.8

April 25, 2026

Author: Jiajun (Leo) Li

- Improved HEIC and HEIF previews and adjusted map zoom and layout.

## 0.6.1.7

April 25, 2026

Author: Jiajun (Leo) Li

- Added HEIC and HEIF image support and improved map interactions.

## 0.6.1.6

April 25, 2026 · Map navigation gestures

Author: Jiajun (Leo) Li

- Added drag-to-pan and touch pinch gestures. On a desktop, Ctrl or Command plus the mouse wheel zoomed toward the cursor.
- The map kept the point being inspected in view as visitors zoomed.

## 0.6.1.5

April 25, 2026

Author: Jiajun (Leo) Li

- Added zoom controls to the Ecological Map.

## 0.6.1.4

April 25, 2026 · Original-size map backgrounds

Author: Jiajun (Leo) Li

- Let viewers inspect backgrounds at their original size for more detail.
- The background editor offered a larger preview and saved edits as PNG.

## 0.6.1.3

April 24, 2026

Author: Jiajun (Leo) Li

- Cleaned up stale map pins that no longer had submissions.

## 0.6.1.2

April 24, 2026 · Map Background Editor

Author: Jiajun (Leo) Li

- Map admins could pan, zoom, rotate, and crop a background image before saving it, with optional aspect-ratio presets.
- Updated map pins so their labels and selection state were easier to see.

## 0.6.1.1

April 24, 2026 · Selecting a map pin

Author: Jiajun (Leo) Li

- Added a dedicated pin picker to the submission form.
- Inter-school accounts no longer had access to the school moderation tools for the Ecological Map.

## 0.6.1.0

April 24, 2026 · Map pins and contributor details

Author: Jiajun (Leo) Li

- Added pins on a configurable map background. Contributors could select a pin for a post, and visitors could open pins to see associated entries.
- Contributors could choose an existing pin, propose a named location, or select Others for a post without a pin. Visitors could open Others to browse approved posts with no location.
- Expanded submissions to include a title, description, and optional display name. The draft preview showed the text, selected location, and image together before submission.
- Added a contributor leaderboard based on approved posts. An enlarged map view helped with inspecting pins and placing new ones, and superadmins could upload a new map background.

## 0.6.0.4

April 24, 2026 · Ecological Map and saved drafts

Author: Jiajun (Leo) Li

- Renamed the feature Ecological Map and updated its link in the recorder.
- The submission form saved draft text in the browser as contributors worked so they could return to an unfinished post.

## 0.6.0.3

April 24, 2026 · Larger drag-and-drop map uploads

Author: Jiajun (Leo) Li

- Contributors could drag an image onto the submission form or use the file picker.
- Raised the image limit to 50 MB so more photos could be submitted directly.

## 0.6.0.2

April 24, 2026 · Clearer map submission errors

Author: Jiajun (Leo) Li

- The submission form checked image type and size before upload and explained what to change when a file failed validation.
- Loading, verification, and submission errors were separated so users could tell which step had failed.

## 0.6.0.1

April 24, 2026

Author: Jiajun (Leo) Li

- Consolidated Golden Plate Map access under the /map page.

## 0.6.0.0

April 24, 2026 · Golden Plate Map opens

Author: Jiajun (Leo) Li

- Opened Golden Plate Map for browsing approved posts. Visitors could open a separate submission page and preview their text and image before sending it for review.
- Contributors verified their St. Andrew’s school email by code. They could also set a map submission password after verification and use it on later posts.
- The map showed authorized reviewers how many submissions were pending. In Map Approvals, they could read the full submission details before approving or rejecting a post.

## 0.5.6.1

April 24, 2026

Author: Jiajun (Leo) Li

- Added a Golden Plate Map preview page while the map was being prepared.

## 0.5.6.0

April 16, 2026 · Merge and unmerge sessions

Author: Jiajun (Leo) Li

- Admins and superadmins could select a main session and attach another session to it. The extra session’s records counted toward the main session’s draw.
- The session list marked which sessions were extras, and the Draw Center explained why an extra session could not run a separate draw.
- Sessions could not be merged into themselves or into an extra session. The controls reported when a session already had extras that needed to be separated first.
- Admins could unmerge an extra session and manage it separately again.

## 0.5.5.8

January 16, 2026

Author: Jiajun (Leo) Li

- Updated the school registration form to show the actual time a verification code would remain valid.

## 0.5.5.7

January 16, 2026

Author: Jiajun (Leo) Li

- Shortened the school registration verification code lifetime from 15 minutes to 5 minutes.

## 0.5.5.6

January 16, 2026

Author: Jiajun (Leo) Li

- Fixed validation of legacy invites so expired codes were rejected.

## 0.5.5.5

January 14, 2026 · Legacy invites return

Author: Jiajun (Leo) Li

- Restored legacy invite options on the account signup and school registration forms alongside the newer request workflows.
- A staff account invite was entered during member signup, while an invite to start a school was entered in the school registration form.
- Changed the default House Data order to clean-plate count.

## 0.5.5.4

January 14, 2026

Author: Jiajun (Leo) Li

- Fixed a date and time comparison that could prevent a valid school verification code from being accepted.

## 0.5.5.3

January 14, 2026

Author: Jiajun (Leo) Li

- Made school registration verification match email addresses regardless of capitalization and improved error feedback.

## 0.5.5.2

January 14, 2026 · Registration code entry

Author: Jiajun (Leo) Li

- Improved the verification code input and feedback when a school applicant could not verify a code.
- Added a reminder to check junk or spam for the verification email.

## 0.5.5.1

January 14, 2026

Author: Jiajun (Leo) Li

- Improved error reporting when school registration verification emails could not be sent.

## 0.5.5.0

January 14, 2026 · School email verification

Author: Jiajun (Leo) Li

- School applicants had to verify their contact email with a code before submitting registration. The application still needed inter-school approval.
- Once the email was verified, the applicant could provide the school name, an optional school code, and details for the first administrator.
- Inter-school administrators gained a separate action to delete an existing school.

## 0.5.4.1

January 13, 2026 · School registration review queue

Author: Jiajun (Leo) Li

- Added Pending School Registration Requests to the Inter-School Control Center.
- Reviewers could inspect the application details and act on the request without leaving the overview.

## 0.5.4.0

January 13, 2026 · School applications by email

Author: Jiajun (Leo) Li

- Schools could submit a registration request with a contact email. Applicants supplied a school name, an optional school code, and details for the lead administrator.
- Registration went through review by inter-school administrators before the applicant could use the new school portal.

## 0.5.3.0

January 13, 2026 · Account requests by school code

Author: Jiajun (Leo) Li

- Applicants could enter the school code and submit an account request for that school.
- School superadmins could use Account Creation Requests to approve or reject applications before the applicant could sign in.

## 0.5.2.3

January 12, 2026

Author: Jiajun (Leo) Li

- Added a CAPTCHA check to account signup.

## 0.5.2.2

January 12, 2026

Author: Jiajun (Leo) Li

- Showed user IDs in superadmins’ account management lists.

## 0.5.2.1

January 12, 2026 · House Data layout

Author: Jiajun (Leo) Li

- Kept House Data visible next to the export tools so staff could scan it without opening a separate view.
- Prioritized clean rate in the default sort and adjusted the controls and card alignment.

## 0.5.2.0

January 12, 2026 · House Data

Author: Jiajun (Leo) Li

- Added a House Data panel to compare houses within the selected lunch session.
- Each row showed clean and very dirty counts, the clean rate, and the house’s share of all records with house data.
- Staff could sort the rankings and switch between viewing a house’s total count and its percentage of the session’s house records.

## 0.5.1.2

January 12, 2026

Author: Jiajun (Leo) Li

- Preserved more precision when showing a winner’s chance in the Draw Center.

## 0.5.1.1

December 27, 2025 · Draw comments and saved faculty picks

Author: Jiajun (Leo) Li

- Staff could add an optional comment when taking a draw action. The comment appeared with the action in draw history.
- Faculty selections were saved with the session so staff could return to the result later.

## 0.5.1.0

November 27, 2025 · The faculty picker

Author: Shuoyou (Nick) Wang

- Added a separate random faculty picker to the Draw Center, with the result shown alongside the student draw.
- Fixed loading faculty selections when returning to a session. Authorized overrides could include participants recorded in that session.

## 0.5.0.3

November 25, 2025

Author: Shuoyou (Nick) Wang

- Allowed different schools to use the same student ID without an import conflict.

## 0.5.0.2

November 25, 2025 · School and invite lists

Author: Shuoyou (Nick) Wang

- The Inter-School Control Center gained a list of registered schools and an Invite Codes Ledger.
- Two schools could use the same session name without a naming conflict.

## 0.5.0.1

November 25, 2025 · Draw summaries and overrides

Author: Shuoyou (Nick) Wang

- Guests could view the Draw Center summary for sessions they could access.
- Manual winner overrides were recorded using the standard draw workflow.

## 0.5.0.0

November 18, 2025 · Separate portals for each school

Author: Shuoyou (Nick) Wang

- Schools gained their own portals, school codes, accounts, sessions, and rosters. Guests entered the school code to browse that school’s shared results.
- The portal header showed the current school and its code. Staff and guests could open that school’s Session Dashboard without needing to enter the inter-school administration area.
- The Inter-School Control Center let inter-school administrators generate single-use school invites. The invite provisioned a school ID and a slot for its lead administrator, and the administrator could copy both the ID and invite details for onboarding.
- The registration form let an invited school redeem its invite, name its school, and set up the account for its lead administrator.

## 0.4.0.0

October 26, 2025 · The recorder moves to a relational database

Author: Shuoyou (Nick) Wang

- Restored database-backed storage and moved the recorder to separate tables for accounts and invites, student and teacher rosters, lunch sessions, and individual plate records. The default database was SQLite.
- Stored draw actions and ticket changes as separate records so each session’s draw history and a student’s running ticket balance could be saved and retrieved. Session deletion requests also had their own table.
- Included migration tools for bringing existing users, rosters, sessions, plate records, and deletion requests over from the earlier JSON files.
- Restored cumulative student tickets. Students needed a clean plate in the session being drawn, and finalizing the winner reset their balance.
- Fixed session totals, draw finalization, and cleanup of records associated with deleted sessions.
- Updated the Session Dashboard to show session counts and draw information, and removed the startup animation.

## 0.3.1.1

October 21, 2025 · Database and ticket rollback

Author: Shuoyou (Nick) Wang

- Rolled back the first database cutover and returned the recorder to its earlier file-based storage. This also restored the earlier Draw Center behavior until the October 26 update.

## 0.3.1.0

October 20, 2025 · First database cutover and cumulative tickets

Author: Shuoyou (Nick) Wang

- Switched the active recorder from separate JSON files to a database for the first time. Accounts, rosters, sessions, invites, and deletion requests were stored as JSON inside the database. This version used a simpler layout than the relational migration that followed.
- Students could carry tickets across sessions. To enter a draw, a student also needed a clean plate in that session.
- Finalizing a winner reset that student’s ticket balance. The Session Dashboard showed the selected session’s counts and draw outcome.

## 0.3.0.0

October 19, 2025 · The Draw Center

Author: Shuoyou (Nick) Wang

- Added a collapsible Draw Center to the recorder. Staff could inspect the eligible pool, see how many tickets were in play, and open an individual student’s ticket and odds details.
- Authorized staff could start a weighted draw, review the selected candidate and their odds at selection, then finalize or reset the draw. The result showed whether the winner was still awaiting finalization.
- Superadmins could search by student name or ID to override the selected winner. The Draw Center marked an override and kept a history of earlier draw actions and ticket figures.
- Switching sessions refreshed the Draw Center so it showed the selected session’s result and pool. Discard Session excluded that session from draw calculations, and Restore Session brought it back.

## 0.2.7.0

September 27, 2025 · Teacher roster upload

Author: Shuoyou (Nick) Wang

- Admins could upload a teacher list as CSV or TXT and check the saved names in Teacher List Preview.
- The Faculty Clean recorder gained searchable suggestions from that list.

## 0.2.6.1

September 27, 2025 · Search while recording

Author: Shuoyou (Nick) Wang

- Added a searchable student picker to plate recording. Staff could narrow the list by typing part of a student’s name and choose the matching roster entry.
- Suggestions displayed student IDs alongside names, and staff could navigate matches with the keyboard.

## 0.2.6.0

September 27, 2025 · A shared student roster

Author: Shuoyou (Nick) Wang

- Uploaded student rosters became available across sessions, so staff could look up students without uploading a copy for each lunch.
- Admins and superadmins managed uploads and previews. Other staff could still use roster data when recording.

## 0.2.5.1

September 26, 2025

Author: Shuoyou (Nick) Wang

- Corrected the displayed clean-plate ratio.

## 0.2.5.0

September 19, 2025 · Faculty Clean and dirty plate counts

Author: Jiajun (Leo) Li

- Added Faculty Clean as its own recording category, with a faculty name field and a separate tally.
- Staff could add a regular dirty plate as a quick count. The dashboard included faculty clean plates in the overall clean percentage.

## 0.2.4.0

September 16, 2025 · Detailed CSV exports

Author: Jiajun (Leo) Li

- Added a detailed record list alongside the existing session export so staff could review individual entries.
- The detailed CSV included plate category, last and preferred names, grade, advisor, house, and clan. It also showed when each plate was recorded, who recorded it, and whether it was entered manually.
- Improved how roster CSVs were read and displayed. The student database preview and large admin dialogs were easier to browse.

## 0.2.3.0

September 14, 2025 · Deletion review and session navigation

Author: Jiajun (Leo) Li

- Restored session deletion requests. Administrators could review pending requests and see alerts when action was needed.
- Improved how the recorder joined and refreshed sessions, including after deletion.
- Updated dialogs and confirmation prompts to prevent accidental dismissal or clicks through an open dialog.

## 0.2.2.1

September 12, 2025 · Student record privacy

Author: Jiajun (Leo) Li

- Stopped retaining raw student IDs in new plate records as part of the recorder’s privacy changes.
- Updated recorder dialogs and how alerts appeared during recording and other actions.

## 0.2.2.0

September 10, 2025 · Invites and guest access

Author: Shuoyou (Nick) Wang

- Account signup gained a one-time invite code. Administrators could issue codes from the portal.
- Guests could see public sessions, while CSV exports and access to nonpublic session history were restricted.

## 0.2.1.0

September 10, 2025 · Guest mode

Author: Shuoyou (Nick) Wang

- Added a guest entry point so visitors could view school session results without creating an account.
- The sign-in screen offered Continue as Guest. The recorder marked the guest role and reserved plate recording, session creation and deletion, and roster uploads for signed-in staff.

## 0.2.0.8

September 9, 2025

Author: Shuoyou (Nick) Wang

- Fixed session deletion in the deployed recorder interface.

## 0.2.0.7

September 9, 2025

Author: Shuoyou (Nick) Wang

- Limited direct deletion to a session’s owner or an administrator and kept the active session out of the delete controls.

## 0.2.0.6

September 9, 2025 · Switch Session

Author: Shuoyou (Nick) Wang

- Added a Switch Session dialog so staff could select an existing session from the recorder.
- The session list also surfaced deletion controls for eligible sessions.

## 0.2.0.5

September 9, 2025

Author: Shuoyou (Nick) Wang

- Updated the site logo and browser icon.

## 0.2.0.4

September 9, 2025

Author: Shuoyou (Nick) Wang

- Replaced session deletion requests with direct deletion from the session list.

## 0.2.0.3

September 7, 2025

Author: Jiajun (Leo) Li

- Fixed the Create New Session button so staff could open the form from the recorder.

## 0.2.0.2

September 7, 2025

Author: Jiajun (Leo) Li

- Fixed unintended automatic sign-in and improved the flow for creating a session from the empty recorder.

## 0.2.0.1

September 7, 2025 · The recorder without an active session

Author: Jiajun (Leo) Li

- After sign-in, the portal could open with no active session. Staff could choose when to start one from the recorder.
- Expanded the session deletion controls and added an animated opening screen.

## 0.2.0.0

September 7, 2025 · PLATE and shared sessions

Author: Jiajun (Leo) Li

- The portal took the name PLATE, short for Prevention, Logging & Assessment of Tossed Edibles.
- Staff could work from shared sessions and see totals with clean and dirty percentages. Dirty and very dirty plates were combined in the overall dirty figure while remaining separate recording categories.
- Preview Database showed the uploaded student roster, with pages for browsing larger lists and details about the last upload.

## 0.1.2.2

September 7, 2025

Author: Jiajun (Leo) Li

- Renamed the recorder WAFFLE and updated the portal around food-waste tracking.

## 0.1.2.1

September 7, 2025 · Records across restarts

Author: Jiajun (Leo) Li

- Added file-based persistence so users, sessions, and plate records survived a restart. Pending account and session requests were also saved so administrators could return to them.

## 0.1.2.0

September 7, 2025 · Superadmin account controls

Author: Jiajun (Leo) Li

- Superadmins gained controls to change roles and delete accounts from the user list.
- The portal refreshed its account list after administrative changes and reported when role changes or deletion failed.

## 0.1.1.0

September 7, 2025 · Account and deletion requests

Author: Jiajun (Leo) Li

- The Account Management panel gave admins a place to review account status and act on requests.
- Staff could request a session deletion for review. Administrators could see pending requests and decide whether to approve them.

## 0.1.0.0

September 7, 2025 · The first Golden Plate Recorder

Author: Jiajun (Leo) Li

- The first recorder let staff sign in, create a named lunch session, and reopen a saved session when they needed to return to it.
- Staff chose clean, dirty, or very dirty, then entered a student ID or name in the recording dialog. The recorder showed running counts by category and a history of recorded plates.
- Schools could upload a student CSV with Last, First, and Student ID columns so the recorder could look up names. Export Session Records downloaded a CSV of the selected session grouped by plate category.
- The Dashboard showed session activity, and the Admin Panel gave administrators a view of users and saved sessions.
