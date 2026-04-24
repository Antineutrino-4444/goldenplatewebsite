import React, { useEffect, useRef, useState } from 'react'
import ReCAPTCHA from 'react-google-recaptcha'
import { Badge } from '@/components/ui/badge.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Textarea } from '@/components/ui/textarea.jsx'
import VerificationCodeInput from '@/components/VerificationCodeInput.jsx'
import {
  ArrowLeft,
  CheckCircle,
  ClipboardCheck,
  Image,
  LogOut,
  Mail,
  MapPinned,
  RefreshCcw,
  Send,
  ShieldCheck,
  Upload,
  XCircle
} from 'lucide-react'

const API_BASE = '/api'
const RECAPTCHA_SITE_KEY = import.meta.env.VITE_RECAPTCHA_SITE_KEY || ''

function normalizeMapPath() {
  const path = window.location.pathname.replace(/\/+$/, '') || '/map'
  if (path.startsWith('/maps')) {
    return path.replace(/^\/maps/, '/map') || '/map'
  }
  return path
}

function formatRole(role) {
  const labels = {
    superadmin: 'Super Admin',
    admin: 'Admin',
    user: 'User',
    guest: 'Guest',
    inter_school: 'Inter-school'
  }
  return labels[role] || role || 'User'
}

function formatBytes(value) {
  if (!value) return '0 B'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

function SubmissionImage({ submission, className = '' }) {
  if (!submission?.image_url) {
    return (
      <div className={`flex min-h-44 items-center justify-center rounded-md border border-dashed bg-slate-50 text-sm text-slate-500 ${className}`}>
        No image attached
      </div>
    )
  }

  return (
    <img
      src={submission.image_url}
      alt={submission.image_filename || 'Map submission'}
      className={`w-full rounded-md border object-cover ${className}`}
    />
  )
}

function ChinaMapGraphic({ approvedCount }) {
  return (
    <div className="relative overflow-hidden rounded-md border bg-white p-4 shadow-sm">
      <svg viewBox="0 0 720 520" role="img" aria-label="Map of China" className="h-full min-h-[22rem] w-full">
        <defs>
          <linearGradient id="china-map-fill" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor="#ecfdf5" />
            <stop offset="100%" stopColor="#dbeafe" />
          </linearGradient>
          <filter id="map-soft-shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="14" stdDeviation="18" floodColor="#0f172a" floodOpacity="0.15" />
          </filter>
        </defs>
        <rect x="0" y="0" width="720" height="520" rx="18" fill="#f8fafc" />
        <path
          d="M395 36 L456 55 L507 89 L555 96 L585 136 L631 156 L609 197 L646 235 L615 280 L630 328 L579 354 L544 406 L490 386 L452 438 L395 426 L356 469 L301 447 L252 464 L221 422 L168 402 L158 355 L99 328 L123 280 L79 246 L119 205 L110 156 L166 134 L205 91 L263 110 L317 69 Z"
          fill="url(#china-map-fill)"
          stroke="#0f766e"
          strokeWidth="4"
          filter="url(#map-soft-shadow)"
        />
        <path d="M205 91 L238 175 L221 422" fill="none" stroke="#94a3b8" strokeWidth="2" strokeDasharray="8 10" />
        <path d="M317 69 L346 154 L395 426" fill="none" stroke="#94a3b8" strokeWidth="2" strokeDasharray="8 10" />
        <path d="M456 55 L429 156 L452 438" fill="none" stroke="#94a3b8" strokeWidth="2" strokeDasharray="8 10" />
        <path d="M555 96 L508 195 L544 406" fill="none" stroke="#94a3b8" strokeWidth="2" strokeDasharray="8 10" />
        <path d="M119 205 L285 220 L646 235" fill="none" stroke="#94a3b8" strokeWidth="2" strokeDasharray="8 10" />
        <path d="M99 328 L288 328 L630 328" fill="none" stroke="#94a3b8" strokeWidth="2" strokeDasharray="8 10" />
        {[
          [438, 150],
          [504, 225],
          [374, 300],
          [470, 342],
          [303, 250],
          [565, 293]
        ].map(([cx, cy], index) => (
          <g key={`${cx}-${cy}`}>
            <circle cx={cx} cy={cy} r={15} fill="#f97316" opacity="0.14" />
            <circle cx={cx} cy={cy} r={6} fill={index < approvedCount ? '#f97316' : '#0f766e'} />
          </g>
        ))}
        <ellipse cx="528" cy="444" rx="18" ry="10" fill="#dbeafe" stroke="#0f766e" strokeWidth="3" />
        <ellipse cx="596" cy="390" rx="10" ry="18" fill="#dbeafe" stroke="#0f766e" strokeWidth="3" />
      </svg>
      <div className="absolute left-5 top-5 rounded-md border bg-white/90 px-3 py-2 shadow-sm backdrop-blur">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Approved pins</div>
        <div className="text-2xl font-bold text-teal-700">{approvedCount}</div>
      </div>
    </div>
  )
}

function SubmissionDetails({ submission, admin = false, actionLoading = false, onApprove, onReject }) {
  return (
    <div className="grid gap-4 rounded-md border bg-white p-4 md:grid-cols-[minmax(0,1.15fr)_minmax(16rem,0.85fr)]">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={submission.status === 'approved' ? 'default' : submission.status === 'pending' ? 'outline' : 'destructive'}>
            {submission.status}
          </Badge>
          <span className="text-sm text-slate-500">
            {submission.submitted_at ? new Date(submission.submitted_at).toLocaleString() : 'No timestamp'}
          </span>
        </div>
        <p className="whitespace-pre-wrap text-sm leading-6 text-slate-800">{submission.text}</p>
        <div className="grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
          <div>Email: {submission.email}</div>
          <div>Image: {submission.image_filename || 'None'}</div>
          <div>Image size: {formatBytes(submission.image_size)}</div>
          <div>
            Submitted by: {submission.submitted_by?.display_name || 'Unknown'} (@{submission.submitted_by?.username || 'unknown'})
          </div>
          <div>Submitter role: {formatRole(submission.submitted_by?.role)}</div>
          {submission.reviewed_by && (
            <div>
              Reviewed by: {submission.reviewed_by.display_name} (@{submission.reviewed_by.username})
            </div>
          )}
          {submission.reviewed_at && (
            <div>Reviewed: {new Date(submission.reviewed_at).toLocaleString()}</div>
          )}
          {submission.rejection_reason && (
            <div>Reason: {submission.rejection_reason}</div>
          )}
        </div>
        {admin && submission.status === 'pending' && (
          <div className="flex flex-wrap gap-2 pt-2">
            <Button onClick={() => onApprove(submission.id)} disabled={actionLoading} className="bg-emerald-600 hover:bg-emerald-700">
              <CheckCircle className="mr-2 h-4 w-4" />
              Approve
            </Button>
            <Button onClick={() => onReject(submission.id)} disabled={actionLoading} variant="outline">
              <XCircle className="mr-2 h-4 w-4" />
              Reject
            </Button>
          </div>
        )}
      </div>
      <SubmissionImage submission={submission} className="max-h-80" />
    </div>
  )
}

function MapPortal({ app }) {
  const {
    user,
    logout,
    showMessage
  } = app

  const recaptchaRef = useRef(null)
  const [approvedSubmissions, setApprovedSubmissions] = useState([])
  const [pendingSubmissions, setPendingSubmissions] = useState([])
  const [approvedLoading, setApprovedLoading] = useState(false)
  const [pendingLoading, setPendingLoading] = useState(false)
  const [showApprovals, setShowApprovals] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)

  const [email, setEmail] = useState('')
  const [authMethod, setAuthMethod] = useState('email')
  const [password, setPassword] = useState('')
  const [shortcutPassword, setShortcutPassword] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [verificationSent, setVerificationSent] = useState(false)
  const [emailVerified, setEmailVerified] = useState(false)
  const [verificationLoading, setVerificationLoading] = useState(false)
  const [hasShortcutPassword, setHasShortcutPassword] = useState(false)
  const [text, setText] = useState('')
  const [imageFile, setImageFile] = useState(null)
  const [imagePreviewUrl, setImagePreviewUrl] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const mapPath = normalizeMapPath()
  const isSubmissionPage = mapPath === '/map/submission'
  const isAdmin = ['admin', 'superadmin'].includes(user?.role)
  const roleLabel = formatRole(user?.role)

  const loadApprovedSubmissions = async () => {
    setApprovedLoading(true)
    try {
      const response = await fetch(`${API_BASE}/map/submissions`)
      const data = await response.json()
      if (response.ok) {
        setApprovedSubmissions(Array.isArray(data.submissions) ? data.submissions : [])
      } else {
        showMessage(data.error || 'Failed to load map submissions', 'error')
      }
    } catch (error) {
      showMessage('Failed to load map submissions', 'error')
    } finally {
      setApprovedLoading(false)
    }
  }

  const loadPendingSubmissions = async () => {
    if (!isAdmin) {
      setPendingSubmissions([])
      return
    }

    setPendingLoading(true)
    try {
      const response = await fetch(`${API_BASE}/map/submissions/pending`)
      const data = await response.json()
      if (response.ok) {
        setPendingSubmissions(Array.isArray(data.submissions) ? data.submissions : [])
      } else {
        showMessage(data.error || 'Failed to load pending map submissions', 'error')
      }
    } catch (error) {
      showMessage('Failed to load pending map submissions', 'error')
    } finally {
      setPendingLoading(false)
    }
  }

  const loadShortcutStatus = async (nextEmail) => {
    const trimmed = nextEmail.trim().toLowerCase()
    if (!trimmed.endsWith('@sac.on.ca')) {
      setHasShortcutPassword(false)
      return
    }

    try {
      const response = await fetch(`${API_BASE}/map/submitter-account/status?email=${encodeURIComponent(trimmed)}`)
      const data = await response.json()
      setHasShortcutPassword(Boolean(response.ok && data.has_password))
    } catch (error) {
      setHasShortcutPassword(false)
    }
  }

  useEffect(() => {
    const originalTitle = document.title
    document.title = isSubmissionPage ? 'Golden Plate Map Submission' : 'Golden Plate Map'
    return () => {
      document.title = originalTitle
    }
  }, [isSubmissionPage])

  useEffect(() => {
    loadApprovedSubmissions()
    loadPendingSubmissions()
  }, [user?.role])

  useEffect(() => {
    if (!imageFile) {
      setImagePreviewUrl('')
      return
    }
    const url = URL.createObjectURL(imageFile)
    setImagePreviewUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [imageFile])

  const getRecaptchaToken = () => {
    if (!RECAPTCHA_SITE_KEY) {
      return null
    }
    const token = recaptchaRef.current?.getValue()
    if (!token) {
      showMessage('Please complete the reCAPTCHA verification', 'error')
      return undefined
    }
    return token
  }

  const resetRecaptcha = () => {
    if (recaptchaRef.current) {
      recaptchaRef.current.reset()
    }
  }

  const updateEmail = (value) => {
    setEmail(value)
    setEmailVerified(false)
    setVerificationSent(false)
    setVerificationCode('')
    loadShortcutStatus(value)
  }

  const sendVerificationCode = async () => {
    const trimmedEmail = email.trim().toLowerCase()
    if (!trimmedEmail.endsWith('@sac.on.ca')) {
      showMessage('Use an @sac.on.ca email address', 'error')
      return
    }

    const recaptchaToken = getRecaptchaToken()
    if (recaptchaToken === undefined) {
      return
    }

    setVerificationLoading(true)
    try {
      const response = await fetch(`${API_BASE}/map/send-verification-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: trimmedEmail,
          recaptcha_token: recaptchaToken
        })
      })
      const data = await response.json()
      if (response.ok) {
        setVerificationSent(true)
        showMessage('Verification code sent', 'success')
      } else {
        showMessage(data.detail ? `${data.error} (${data.detail})` : data.error || 'Failed to send verification code', 'error')
      }
    } catch (error) {
      showMessage('Failed to send verification code', 'error')
    } finally {
      resetRecaptcha()
      setVerificationLoading(false)
    }
  }

  const verifyEmailCode = async () => {
    const trimmedEmail = email.trim().toLowerCase()
    const trimmedCode = verificationCode.trim()

    if (trimmedCode.length !== 6 || !/^\d+$/.test(trimmedCode)) {
      showMessage('Verification code must be 6 digits', 'error')
      return
    }

    setVerificationLoading(true)
    try {
      const response = await fetch(`${API_BASE}/map/verify-email-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: trimmedEmail,
          code: trimmedCode
        })
      })
      const data = await response.json()
      if (response.ok && data.verified) {
        setEmailVerified(true)
        showMessage('Email verified', 'success')
      } else {
        showMessage(data.error || 'Invalid verification code', 'error')
      }
    } catch (error) {
      showMessage('Failed to verify code', 'error')
    } finally {
      setVerificationLoading(false)
    }
  }

  const resetSubmissionForm = () => {
    setText('')
    setImageFile(null)
    setPassword('')
    setShortcutPassword('')
    setVerificationCode('')
    setVerificationSent(false)
    setEmailVerified(false)
  }

  const submitMapEntry = async () => {
    const trimmedEmail = email.trim().toLowerCase()
    if (!trimmedEmail.endsWith('@sac.on.ca')) {
      showMessage('Use an @sac.on.ca email address', 'error')
      return
    }

    if (!text.trim()) {
      showMessage('Enter submission text', 'error')
      return
    }

    if (authMethod === 'email' && !emailVerified) {
      showMessage('Verify your SAC email before submitting', 'error')
      return
    }

    if (authMethod === 'password' && !password) {
      showMessage('Enter your map submission password', 'error')
      return
    }

    const recaptchaToken = getRecaptchaToken()
    if (recaptchaToken === undefined) {
      return
    }

    const formData = new FormData()
    formData.append('email', trimmedEmail)
    formData.append('text', text.trim())
    formData.append('auth_method', authMethod)
    formData.append('recaptcha_token', recaptchaToken || '')
    if (authMethod === 'email') {
      formData.append('verification_code', verificationCode.trim())
      if (shortcutPassword) {
        formData.append('shortcut_password', shortcutPassword)
      }
    } else {
      formData.append('password', password)
    }
    if (imageFile) {
      formData.append('image', imageFile)
    }

    setSubmitting(true)
    try {
      const response = await fetch(`${API_BASE}/map/submissions`, {
        method: 'POST',
        body: formData
      })
      const data = await response.json()
      if (response.ok) {
        showMessage(
          data.password_created
            ? 'Submission sent and shortcut password saved'
            : 'Submission sent for approval',
          'success'
        )
        resetSubmissionForm()
        await loadApprovedSubmissions()
        await loadPendingSubmissions()
      } else {
        showMessage(data.error || 'Failed to submit map entry', 'error')
      }
    } catch (error) {
      showMessage('Failed to submit map entry', 'error')
    } finally {
      resetRecaptcha()
      setSubmitting(false)
    }
  }

  const approveSubmission = async (submissionId) => {
    setActionLoading(true)
    try {
      const response = await fetch(`${API_BASE}/map/submissions/${submissionId}/approve`, { method: 'POST' })
      const data = await response.json()
      if (response.ok) {
        showMessage('Map submission approved', 'success')
        await loadApprovedSubmissions()
        await loadPendingSubmissions()
      } else {
        showMessage(data.error || 'Failed to approve submission', 'error')
      }
    } catch (error) {
      showMessage('Failed to approve submission', 'error')
    } finally {
      setActionLoading(false)
    }
  }

  const rejectSubmission = async (submissionId) => {
    setActionLoading(true)
    try {
      const response = await fetch(`${API_BASE}/map/submissions/${submissionId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: '' })
      })
      const data = await response.json()
      if (response.ok) {
        showMessage('Map submission rejected', 'success')
        await loadPendingSubmissions()
      } else {
        showMessage(data.error || 'Failed to reject submission', 'error')
      }
    } catch (error) {
      showMessage('Failed to reject submission', 'error')
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-md bg-teal-700 text-white">
              <MapPinned className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-950">Golden Plate Map</h1>
              <p className="text-sm text-slate-500">China submission board</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="bg-teal-50 text-teal-800">
              {roleLabel}: @{user?.username || 'guest'}
            </Badge>
            <Badge variant="secondary">{user?.name || 'Guest User'}</Badge>
            <Button asChild variant="outline" size="sm">
              <a href={isSubmissionPage ? '/map' : '/map/submission'}>
                {isSubmissionPage ? (
                  <>
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Map
                  </>
                ) : (
                  <>
                    <Send className="mr-2 h-4 w-4" />
                    Submit
                  </>
                )}
              </a>
            </Button>
            <Button onClick={logout} variant="outline" size="sm">
              <LogOut className="mr-2 h-4 w-4" />
              Logout
            </Button>
          </div>
        </div>
      </header>

      {isAdmin && (
        <section className="border-b bg-amber-50">
          <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
            <div className="flex items-center gap-3 text-sm text-amber-950">
              <ClipboardCheck className="h-5 w-5 text-amber-700" />
              <span className="font-semibold">Map approvals</span>
              <Badge variant={pendingSubmissions.length ? 'destructive' : 'outline'}>
                {pendingSubmissions.length} pending
              </Badge>
            </div>
            <div className="flex gap-2">
              <Button onClick={loadPendingSubmissions} variant="outline" size="sm" disabled={pendingLoading}>
                <RefreshCcw className="mr-2 h-4 w-4" />
                Refresh
              </Button>
              <Button onClick={() => setShowApprovals(true)} size="sm" className="bg-amber-700 hover:bg-amber-800">
                Open Approvals
              </Button>
            </div>
          </div>
        </section>
      )}

      <main className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <section className="grid gap-6 lg:grid-cols-[minmax(0,0.95fr)_minmax(28rem,1.05fr)]">
          <div className="flex flex-col justify-center gap-4 rounded-md border bg-white p-6 shadow-sm">
            <Badge variant="outline" className="w-fit bg-slate-50">
              {roleLabel} access
            </Badge>
            <div>
              <h2 className="text-4xl font-bold tracking-normal text-slate-950">China map</h2>
              <p className="mt-3 max-w-xl text-base leading-7 text-slate-600">
                Approved submissions appear here after review. Your current session is tied to @{user?.username || 'guest'}.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-md border bg-slate-50 p-3">
                <div className="text-xs font-semibold uppercase text-slate-500">Role</div>
                <div className="mt-1 text-lg font-bold">{roleLabel}</div>
              </div>
              <div className="rounded-md border bg-slate-50 p-3">
                <div className="text-xs font-semibold uppercase text-slate-500">Username</div>
                <div className="mt-1 truncate text-lg font-bold">@{user?.username || 'guest'}</div>
              </div>
              <div className="rounded-md border bg-slate-50 p-3">
                <div className="text-xs font-semibold uppercase text-slate-500">Approved</div>
                <div className="mt-1 text-lg font-bold">{approvedSubmissions.length}</div>
              </div>
            </div>
          </div>
          <ChinaMapGraphic approvedCount={approvedSubmissions.length} />
        </section>

        {isSubmissionPage ? (
          <section className="grid gap-6 lg:grid-cols-[minmax(0,0.95fr)_minmax(22rem,0.65fr)]">
            <Card className="rounded-md">
              <CardHeader>
                <CardTitle>Map Submission</CardTitle>
                <CardDescription>Submissions require an @sac.on.ca email address.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="map-email">SAC email</Label>
                  <Input
                    id="map-email"
                    type="email"
                    placeholder="name@sac.on.ca"
                    value={email}
                    onChange={(event) => updateEmail(event.target.value)}
                  />
                  {hasShortcutPassword && (
                    <div className="flex items-center gap-2 text-xs font-medium text-teal-700">
                      <ShieldCheck className="h-3.5 w-3.5" />
                      Password shortcut available
                    </div>
                  )}
                </div>

                <div className="space-y-2">
                  <Label>Verification method</Label>
                  <div className="grid overflow-hidden rounded-md border sm:grid-cols-2">
                    <button
                      type="button"
                      onClick={() => setAuthMethod('email')}
                      className={`px-3 py-2 text-sm font-medium ${authMethod === 'email' ? 'bg-teal-700 text-white' : 'bg-white text-slate-700 hover:bg-slate-50'}`}
                    >
                      Email code
                    </button>
                    <button
                      type="button"
                      onClick={() => setAuthMethod('password')}
                      className={`px-3 py-2 text-sm font-medium ${authMethod === 'password' ? 'bg-teal-700 text-white' : 'bg-white text-slate-700 hover:bg-slate-50'}`}
                    >
                      Password
                    </button>
                  </div>
                </div>

                {authMethod === 'email' ? (
                  <div className="space-y-4 rounded-md border bg-slate-50 p-4">
                    <div className="flex flex-col gap-2 sm:flex-row">
                      <Button onClick={sendVerificationCode} disabled={verificationLoading || !email.trim()} variant="outline">
                        <Mail className="mr-2 h-4 w-4" />
                        {verificationSent ? 'Resend Code' : 'Send Code'}
                      </Button>
                      {emailVerified && (
                        <Badge className="w-fit bg-emerald-600">
                          <CheckCircle className="mr-1 h-3.5 w-3.5" />
                          Verified
                        </Badge>
                      )}
                    </div>
                    {verificationSent && !emailVerified && (
                      <div className="space-y-3">
                        <VerificationCodeInput
                          value={verificationCode}
                          onChange={setVerificationCode}
                          disabled={verificationLoading}
                        />
                        <Button onClick={verifyEmailCode} disabled={verificationLoading || verificationCode.length !== 6}>
                          Verify Code
                        </Button>
                      </div>
                    )}
                    {emailVerified && (
                      <div className="space-y-2">
                        <Label htmlFor="shortcut-password">Create password for next time</Label>
                        <Input
                          id="shortcut-password"
                          type="password"
                          placeholder="Optional password"
                          value={shortcutPassword}
                          onChange={(event) => setShortcutPassword(event.target.value)}
                        />
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="space-y-2 rounded-md border bg-slate-50 p-4">
                    <Label htmlFor="map-password">Map submission password</Label>
                    <Input
                      id="map-password"
                      type="password"
                      placeholder="Password"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                    />
                  </div>
                )}

                <div className="space-y-2">
                  <Label htmlFor="map-text">Submission text</Label>
                  <Textarea
                    id="map-text"
                    placeholder="Enter submission details"
                    rows={6}
                    value={text}
                    onChange={(event) => setText(event.target.value)}
                  />
                </div>

                <div className="space-y-3">
                  <Label htmlFor="map-image">Image</Label>
                  <label
                    htmlFor="map-image"
                    className="flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-md border border-dashed bg-slate-50 p-4 text-center hover:bg-slate-100"
                  >
                    <Upload className="mb-2 h-6 w-6 text-slate-500" />
                    <span className="text-sm font-medium text-slate-700">
                      {imageFile ? imageFile.name : 'Choose image'}
                    </span>
                    <span className="text-xs text-slate-500">JPG, PNG, WebP, or GIF up to 5 MB</span>
                    <Input
                      id="map-image"
                      type="file"
                      accept="image/jpeg,image/png,image/webp,image/gif"
                      className="sr-only"
                      onChange={(event) => setImageFile(event.target.files?.[0] || null)}
                    />
                  </label>
                  {imagePreviewUrl && (
                    <img src={imagePreviewUrl} alt="Selected preview" className="max-h-72 w-full rounded-md border object-cover" />
                  )}
                </div>

                {RECAPTCHA_SITE_KEY && (
                  <div className="flex justify-center">
                    <ReCAPTCHA ref={recaptchaRef} sitekey={RECAPTCHA_SITE_KEY} theme="light" />
                  </div>
                )}

                <Button onClick={submitMapEntry} disabled={submitting} className="w-full bg-teal-700 hover:bg-teal-800">
                  <Send className="mr-2 h-4 w-4" />
                  {submitting ? 'Submitting...' : 'Submit for Approval'}
                </Button>
              </CardContent>
            </Card>

            <Card className="rounded-md">
              <CardHeader>
                <CardTitle>Preview</CardTitle>
                <CardDescription>Current draft</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-md border bg-slate-50 p-4">
                  <div className="text-xs font-semibold uppercase text-slate-500">Email</div>
                  <div className="mt-1 break-all text-sm">{email || 'No email entered'}</div>
                </div>
                <div className="rounded-md border bg-slate-50 p-4">
                  <div className="text-xs font-semibold uppercase text-slate-500">Text</div>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{text || 'No text entered'}</p>
                </div>
                {imagePreviewUrl ? (
                  <img src={imagePreviewUrl} alt="Draft preview" className="max-h-80 w-full rounded-md border object-cover" />
                ) : (
                  <div className="flex min-h-48 items-center justify-center rounded-md border border-dashed bg-slate-50 text-sm text-slate-500">
                    <Image className="mr-2 h-4 w-4" />
                    No image selected
                  </div>
                )}
              </CardContent>
            </Card>
          </section>
        ) : (
          <section className="space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-2xl font-bold text-slate-950">Approved submissions</h2>
                <p className="text-sm text-slate-500">Visible to signed-in and guest map users.</p>
              </div>
              <Button onClick={loadApprovedSubmissions} variant="outline" disabled={approvedLoading}>
                <RefreshCcw className="mr-2 h-4 w-4" />
                Refresh
              </Button>
            </div>
            {approvedLoading ? (
              <div className="rounded-md border bg-white p-8 text-center text-slate-500">Loading submissions...</div>
            ) : approvedSubmissions.length === 0 ? (
              <div className="rounded-md border bg-white p-8 text-center text-slate-500">No approved submissions yet</div>
            ) : (
              <div className="space-y-4">
                {approvedSubmissions.map((submission) => (
                  <SubmissionDetails key={submission.id} submission={submission} />
                ))}
              </div>
            )}
          </section>
        )}
      </main>

      <Dialog open={showApprovals} onOpenChange={setShowApprovals}>
        <DialogContent className="w-full sm:max-w-4xl max-h-[85vh] overflow-y-auto" dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle>Map Approval Queue</DialogTitle>
            <DialogDescription>Review pending map submissions with full submission details.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {pendingLoading ? (
              <div className="rounded-md border bg-slate-50 p-8 text-center text-slate-500">Loading approvals...</div>
            ) : pendingSubmissions.length === 0 ? (
              <div className="rounded-md border bg-slate-50 p-8 text-center text-slate-500">No pending map submissions</div>
            ) : (
              pendingSubmissions.map((submission) => (
                <SubmissionDetails
                  key={submission.id}
                  submission={submission}
                  admin
                  actionLoading={actionLoading}
                  onApprove={approveSubmission}
                  onReject={rejectSubmission}
                />
              ))
            )}
          </div>
          <Button onClick={() => setShowApprovals(false)} className="w-full">
            Close
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default MapPortal
