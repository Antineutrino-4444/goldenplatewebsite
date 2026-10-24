const example = {
  schoolEmail: 'school@example.org', schoolName: 'Example School', schoolCode: 'EXAMPLE',
  schoolAdminDisplayName: 'School Admin', schoolAdminUsername: 'example_admin', schoolAdminPassword: 'ExamplePass!2026',
};
const empty = { schoolEmail: '', schoolName: '', schoolCode: '', schoolAdminDisplayName: '', schoolAdminUsername: '', schoolAdminPassword: '', emailVerificationCode: '', emailVerified: false, verificationSent: false, verificationLoading: false, isLoading: false };
const named = { ...empty, schoolEmail: example.schoolEmail, emailVerified: true, verificationSent: true };
const targets = {
  register: { selector: '.public-header a.gp-button[href="/register"]' },
  method: { role: 'button', name: 'Email Verification', exact: true },
  email: { selector: '#school-email' }, send: { role: 'button', name: 'Send Code', exact: true },
  code1: { selector: '[aria-label="Verification code digit 1"]' }, code6: { selector: '[aria-label="Verification code digit 6"]' },
  codeGroup: { union: ['code1', 'code6'] },
  verify: { role: 'button', name: 'Verify Code', exact: true },
  schoolName: { selector: '#school-name' }, schoolCode: { selector: '#school-code' },
  adminName: { selector: '#admin-display-name' }, adminUsername: { selector: '#admin-username' }, adminPassword: { selector: '#admin-password' },
  submit: { role: 'button', name: 'Submit Registration Request', exact: true },
  username: { selector: '#username' }, password: { selector: '#password' }, login: { role: 'button', name: 'Login', exact: true },
};
export default {
  id: 'school-registration', title: 'Register your school', fps: 60, width: 3840, height: 2160, transition: 0.5,
  example, targets,
  scenes: [
    { id: 'opening', kind: 'title', duration: 3, title: 'Register your school.\nMake your first login.', subtitle: 'A guided start to PLATE', caption: 'Register a new school, then make your first login.' },
    { id: 'register', page: 'home', duration: 5, label: 'REGISTER A SCHOOL', title: 'Start here.', instruction: 'One person registers\neach new school.', caption: 'Choose Register a school on the Golden Plate website.', highlights: ['register'], camera: { fullPage: true }, leader: 'above', state: empty,
      actions: [{ type: 'click', target: 'register', at: 3.7, set: { acknowledged: 'register' } }] },
    { id: 'method', page: 'register', duration: 4.5, label: 'REGISTER A SCHOOL', title: 'Use email\nverification.', instruction: 'The standard route for\na new school.', caption: 'Choose Email Verification. The school’s contact email is verified first.', highlights: ['method'], camera: { card: true }, state: empty,
      actions: [{ type: 'click', target: 'method', at: 2.7, set: { schoolSignupMode: 'request' } }] },
    { id: 'email', page: 'register', duration: 8, label: 'REGISTER A SCHOOL', title: 'Use an email\nyou can access.', instruction: 'Enter your school contact\nemail, then send the code.', caption: 'Enter the contact email and select Send Code. Check that inbox for the message.', highlights: ['email', 'send'], camera: { card: true }, state: empty,
      actions: [{ type: 'type', target: 'email', field: 'schoolEmail', value: example.schoolEmail, at: 1.5, duration: 2.6 }, { type: 'click', target: 'send', at: 5.8, after: 0.3, set: { verificationLoading: true } }] },
    { id: 'code', page: 'register', duration: 7, label: 'REGISTER A SCHOOL', title: 'Verify your\nemail address.', instruction: 'Use the six-digit code\nfrom your own email.', caption: 'Enter the six-digit code, then choose Verify Code. Check spam if the email is missing.', highlights: ['codeGroup', 'verify'], camera: { targets: ['email', 'code1', 'code6', 'verify'], padding: 85, topAnchor: '.school-registration h3', topPadding: 20 }, state: { ...empty, schoolEmail: example.schoolEmail, verificationSent: true },
      actions: [{ type: 'type', target: 'code1', field: 'emailVerificationCode', value: '123456', at: 1.3, duration: 2.1 }, { type: 'click', target: 'verify', at: 5, set: { verificationLoading: true } }] },
    { id: 'school', page: 'register', duration: 8, label: 'SCHOOL DETAILS', title: 'Identify\nyour school.', instruction: 'Use the full school name.\nA school code is optional.', caption: 'Add your school name. Choose a shareable code, or leave it blank to generate one.', highlights: ['schoolName', 'schoolCode'], camera: { targets: ['schoolName', 'schoolCode', 'adminName', 'submit'], padding: 75 }, state: named,
      actions: [{ type: 'type', target: 'schoolName', field: 'schoolName', value: example.schoolName, at: 1.3, duration: 2.1 }, { type: 'type', target: 'schoolCode', field: 'schoolCode', value: example.schoolCode, at: 4.7, duration: 1.1 }] },
    { id: 'admin', page: 'register', duration: 10, label: 'PRIMARY ADMINISTRATOR', title: 'Create the\nlead account.', instruction: 'Display name, username,\nand a strong password.', caption: 'Set the primary administrator’s details. Keep the username and password for login.', highlights: ['adminName', 'adminUsername', 'adminPassword'], camera: { targets: ['schoolName', 'adminName', 'adminPassword', 'submit'], padding: 70 }, state: { ...named, schoolName: example.schoolName, schoolCode: example.schoolCode },
      actions: [{ type: 'type', target: 'adminName', field: 'schoolAdminDisplayName', value: example.schoolAdminDisplayName, at: 1.3, duration: 1.6 }, { type: 'type', target: 'adminUsername', field: 'schoolAdminUsername', value: example.schoolAdminUsername, at: 3.8, duration: 1.8 }, { type: 'type', target: 'adminPassword', field: 'schoolAdminPassword', value: example.schoolAdminPassword, at: 6.6, duration: 1.7 }] },
    { id: 'submit', page: 'register', duration: 4.5, label: 'SEND YOUR REQUEST', title: 'Ready to\nsubmit?', instruction: 'Review the details, then\nsubmit your registration.', caption: 'Select Submit Registration Request.', highlights: ['submit'], camera: { targets: ['schoolName', 'adminName', 'adminPassword', 'submit'], padding: 70 }, leader: 'below', state: { ...named, ...example },
      actions: [{ type: 'click', target: 'submit', at: 2.6, set: { isLoading: true } }] },
    { id: 'approval', kind: 'approval', duration: 6, title: 'Request sent.\nApproval comes next.', subtitle: 'The PLATE administrator reviews your registration.', caption: 'Email verification does not approve the school. Wait for PLATE approval before logging in.' },
    { id: 'login', page: 'login', duration: 9, label: 'AFTER APPROVAL', title: 'Make your\nfirst login.', instruction: 'Use the administrator\nusername and password\nyou just created.', caption: 'Once approved, return to Log in and sign in with your new administrator account.', highlights: ['username', 'password', 'login'], camera: { card: true, minWidth: 780, topAnchor: '.auth-intro p', topPadding: 4 }, state: { ...empty, loginUsername: '', loginPassword: '' },
      actions: [{ type: 'type', target: 'username', field: 'loginUsername', value: example.schoolAdminUsername, at: 1.3, duration: 1.9 }, { type: 'type', target: 'password', field: 'loginPassword', value: example.schoolAdminPassword, at: 4, duration: 1.9 }, { type: 'click', target: 'login', at: 7.5, after: 0.4, set: { isLoading: true } }] },
    { id: 'closing', kind: 'closing', duration: 9.5, subtitle: 'UP NEXT / THE SCHOOL GUIDE', title: 'Getting started in\nyour school account.', description: 'A short orientation after your first login.', caption: 'Next in the school guide: getting started in your school account.' },
  ],
};
