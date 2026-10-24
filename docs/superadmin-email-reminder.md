# Superadmin account email

School registration requires email verification before a request can be submitted.
When an inter-school administrator approves the request, the school contact email
and the new superadmin account email both receive that signup address. The account
address is already verified; no second verification is required.

After the approval transaction commits, the applicant receives an approval email
with the school name and username, inviting them to sign in using their chosen
password. The email never includes the password, its hash, or verification codes.
It is a transactional confirmation sent only to the applicant, independently of
website update recipients and their notification preferences. Failure leaves the
school and account active, logs the failure, and reports it in the approval result.
An already processed request cannot send another approval email.

On the new superadmin's first login, a pop-up displays the saved account email and
asks whether to keep or change it. Keeping it closes the pop-up. Changing it opens
the existing verification form; a new address must be verified before it is saved.
Closing the pop-up dismisses it for that login in the current browser tab, including
after reloads and route changes. Later logins do not repeat the signup confirmation.
The account menu continues to provide manual access to email settings.

Superadmins without a verified account email still receive the optional existing
verification reminder. When a school contact email is missing, its separate reminder
appears first. Other roles do not receive either superadmin reminder. An invite-only
school registration without a verified signup address does not mark an account
email verified.

Validation (October 24, 2026): related backend tests cover approval delivery,
recipient isolation, password secrecy, duplicate approvals, delivery failures,
verified account email and the first versus subsequent login. Delivery is mocked.
Frontend reminder tests, component lint and the production build pass. A browser
preview confirms that the signup address is displayed, Keep this email dismisses
the pop-up, and Change email opens the verification form.
