import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { flushSync } from 'react-dom';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from 'next-themes';
import SchoolRegistration from '@/components/SchoolRegistration.jsx';
import LoginView from '@/components/LoginView.jsx';
import PublicHeader from '@/components/PublicHeader.jsx';
import LandingPage from '@/components/LandingPage.jsx';
import '@/App.css';
import '@/theme.css';
import './demo.css';

const seed = {
  schoolEmail: '', schoolName: '', schoolCode: '', schoolAdminUsername: '', schoolAdminPassword: '', schoolAdminDisplayName: '',
  schoolSignupMode: 'request', schoolInviteCode: '', schoolInviteSchoolId: '', emailVerificationCode: '', emailVerified: false,
  verificationSent: false, verificationLoading: false, verificationExpiryMinutes: 5, isLoading: false,
  loginUsername: '', loginPassword: '', signupUsername: '', signupPassword: '', signupName: '', signupEmail: '', signupVerificationCode: '',
  signupCodeSent: false, signupCodeLoading: false, signupCodeExpiryMinutes: 5, signupSchoolCode: '', signupInviteCode: '', signupMode: 'school',
  showSignupDialog: false, showGuestSchoolDialog: false, guestSchoolCode: '',
};
let control;
const audit = [];
function Demo() {
  const [page, setPage] = useState('home');
  const [state, setState] = useState(seed);
  const setter = key => value => setState(previous => ({ ...previous, [key]: value }));
  const dispatch = name => {
    audit.push({ action: name, state: { ...state, schoolAdminPassword: '[masked]', loginPassword: '[masked]' } });
    if (name === 'sendCode') { if (!/^.+@.+\..+$/.test(state.schoolEmail)) return false; setState(s => ({ ...s, verificationSent: true })); }
    if (name === 'verifyCode') { if (state.emailVerificationCode !== '123456') return false; setState(s => ({ ...s, emailVerified: true })); }
    if (name === 'register') { if (!state.emailVerified || !state.schoolName || !state.schoolAdminUsername || state.schoolAdminPassword.length < 6) return false; setState(s => ({ ...s, isLoading: true })); }
    if (name === 'login') { if (!state.loginUsername || !state.loginPassword) return false; setState(s => ({ ...s, isLoading: true })); }
    return true;
  };
  const app = { ...state };
  for (const field of Object.keys(seed)) app[`set${field[0].toUpperCase()}${field.slice(1)}`] = setter(field);
  Object.assign(app, {
    sendVerificationCode: async () => dispatch('sendCode'), verifyEmailCode: async () => dispatch('verifyCode'),
    registerSchool: async () => dispatch('register'), login: async () => dispatch('login'),
    guestLogin: async () => false, signup: async () => false, sendSignupVerificationCode: async () => false,
    setShowSchoolRegistration: open => setPage(open ? 'register' : 'login'), resetSchoolRegistrationForm: () => setState(seed),
  });
  control = {
    apply(model) {
      flushSync(() => { setPage(model.page); setState({ ...seed, ...model.state }); });
      document.body.dataset.caret = model.caretVisible ? 'on' : 'off';
    },
    current: () => ({ page, state: { ...state, schoolAdminPassword: '[masked]', loginPassword: '[masked]' }, audit: [...audit] }),
  };
  return <ThemeProvider attribute="class" forcedTheme="dark" enableSystem={false}>
    <MemoryRouter key={page} initialEntries={[page === 'home' ? '/' : `/${page}`]}>
      <div className="site-shell"><PublicHeader />
        {page === 'home' ? <LandingPage /> : <div className="auth-page">
          {page === 'login' && <div className="auth-intro"><h1>Welcome back to your school.</h1><p>Sign in to record plates and review your school’s sessions.</p></div>}
          <main id="main-content">{page === 'register' ? <SchoolRegistration app={app} /> : <LoginView app={app} />}</main>
        </div>}
      </div>
    </MemoryRouter>
  </ThemeProvider>;
}
createRoot(document.getElementById('demo-root')).render(<Demo />);
window.__demo = {
  apply(model) { control.apply(model); }, current: () => control.current(), ready: () => Boolean(control),
  audit: () => ({ events: [...audit], network: [...window.__tutorialRequests] }),
};
