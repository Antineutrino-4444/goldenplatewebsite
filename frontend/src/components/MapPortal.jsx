import React, { useEffect, useMemo, useRef, useState } from 'react'
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
  Image as ImageIcon,
  LogOut,
  Mail,
  MapPin as MapPinIcon,
  MapPinned,
  Plus,
  RefreshCcw,
  Send,
  ShieldCheck,
  Trash2,
  Trophy,
  Upload,
  X,
  XCircle,
  ZoomIn
} from 'lucide-react'

const API_BASE = '/api'
const RECAPTCHA_SITE_KEY = import.meta.env.VITE_RECAPTCHA_SITE_KEY || ''
const MAP_MAX_IMAGE_BYTES = 50 * 1024 * 1024
const MAP_ALLOWED_IMAGE_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/gif'])

async function readApiResponse(response) {
  const raw = await response.text()
  let data = {}
  if (raw) {
    try {
      data = JSON.parse(raw)
    } catch {
      data = {
        error: `Server returned a non-JSON response (${response.status})`,
        detail: raw.slice(0, 180),
        non_json: true
      }
    }
  }
  return { ok: response.ok, status: response.status, data, raw }
}

function buildApiErrorMessage(result, fallbackCode, fallbackMessage) {
  const status = result?.status
  const data = result?.data || {}
  const code = data.code || fallbackCode || `HTTP_${status || 'UNKNOWN'}`
  const message = data.error || fallbackMessage
  const detail = data.detail ? ` (${data.detail})` : ''
  return `[${code}] ${message}${detail}`
}

function buildNetworkErrorMessage(code, message, error) {
  const detail = error?.message ? ` (${error.message})` : ''
  return `[${code}] ${message}${detail}`
}

function normalizeMapPath() {
  const path = window.location.pathname.replace(/\/+$/, '') || '/'
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

/**
 * Ecological map graphic. Pin coords are percentages (0-100 on each axis).
 * Props:
 *   pins: [{id,name,x,y,...}]
 *   submissionsByPin: { pinId|'others': count }
 *   selectedPinId: id | 'others' | null
 *   onSelectPin: (id) => void
 *   backgroundUrl: string | null
 *   pendingPoint: {x,y} | null  (ghost pin while picking a location)
 *   onMapClick: (x,y) => void   (when not null, map is clickable to place)
 *   className: extra classes
 */
function EcologicalMapGraphic({
  pins = [],
  submissionsByPin = {},
  selectedPinId = null,
  onSelectPin,
  backgroundUrl = null,
  pendingPoint = null,
  onMapClick = null,
  className = ''
}) {
  const svgRef = useRef(null)

  const handleClick = (event) => {
    if (!onMapClick) return
    const svg = svgRef.current
    if (!svg) return
    const rect = svg.getBoundingClientRect()
    const x = ((event.clientX - rect.left) / rect.width) * 100
    const y = ((event.clientY - rect.top) / rect.height) * 100
    onMapClick(Math.max(0, Math.min(100, x)), Math.max(0, Math.min(100, y)))
  }

  const gridLines = []
  for (let i = 1; i < 10; i++) {
    gridLines.push(<line key={`h-${i}`} x1="0" y1={i * 10} x2="100" y2={i * 10} stroke="#cbd5e1" strokeWidth="0.15" strokeDasharray="0.6 0.6" />)
    gridLines.push(<line key={`v-${i}`} x1={i * 10} y1="0" x2={i * 10} y2="100" stroke="#cbd5e1" strokeWidth="0.15" strokeDasharray="0.6 0.6" />)
  }

  return (
    <div className={`relative overflow-hidden rounded-md border bg-white shadow-sm ${className}`}>
      <svg
        ref={svgRef}
        viewBox="0 0 100 100"
        role="img"
        aria-label="Ecological Map"
        preserveAspectRatio="none"
        className={`block h-full min-h-[22rem] w-full ${onMapClick ? 'cursor-crosshair' : ''}`}
        onClick={handleClick}
      >
        <defs>
          <linearGradient id="eco-map-fill" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor="#ecfdf5" />
            <stop offset="100%" stopColor="#dbeafe" />
          </linearGradient>
        </defs>
        {backgroundUrl ? (
          <image href={backgroundUrl} x="0" y="0" width="100" height="100" preserveAspectRatio="xMidYMid slice" />
        ) : (
          <rect x="0" y="0" width="100" height="100" fill="url(#eco-map-fill)" />
        )}
        <g pointerEvents="none">{gridLines}</g>
        {pins.map((pin) => {
          const count = submissionsByPin[pin.id] || 0
          const selected = selectedPinId === pin.id
          return (
            <g
              key={pin.id}
              onClick={(event) => {
                event.stopPropagation()
                if (onSelectPin) onSelectPin(pin.id)
              }}
              style={{ cursor: 'pointer' }}
            >
              <circle cx={pin.x} cy={pin.y} r={3.4} fill="#f97316" opacity="0.18" />
              <circle
                cx={pin.x}
                cy={pin.y}
                r={selected ? 1.8 : 1.4}
                fill={selected ? '#dc2626' : '#f97316'}
                stroke="#ffffff"
                strokeWidth="0.3"
              />
              <text
                x={pin.x}
                y={pin.y - 2.6}
                textAnchor="middle"
                fontSize="2"
                fontWeight="600"
                fill="#0f172a"
                style={{ paintOrder: 'stroke', stroke: '#ffffff', strokeWidth: 0.5 }}
              >
                {pin.name}{count ? ` (${count})` : ''}
              </text>
            </g>
          )
        })}
        {pendingPoint && (
          <g pointerEvents="none">
            <circle cx={pendingPoint.x} cy={pendingPoint.y} r={3} fill="#0ea5e9" opacity="0.25" />
            <circle cx={pendingPoint.x} cy={pendingPoint.y} r={1.4} fill="#0ea5e9" stroke="#ffffff" strokeWidth="0.3" />
          </g>
        )}
      </svg>
      {/* Others tag (bottom-right) */}
      <button
        type="button"
        onClick={() => onSelectPin && onSelectPin('others')}
        className={`absolute bottom-3 right-3 rounded-full border px-3 py-1 text-xs font-semibold shadow-sm transition ${
          selectedPinId === 'others' ? 'bg-slate-900 text-white' : 'bg-white/90 text-slate-700 hover:bg-slate-100'
        }`}
      >
        Others ({submissionsByPin.others || 0})
      </button>
    </div>
  )
}

function SubmissionDetails({ submission, admin = false, canDelete = false, actionLoading = false, onApprove, onReject, onDelete }) {
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
        {submission.title && (
          <h3 className="text-lg font-semibold text-slate-900">{submission.title}</h3>
        )}
        <p className="whitespace-pre-wrap text-sm leading-6 text-slate-800">{submission.text}</p>
        <div className="grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
          {submission.submission_display_name && (
            <div className="sm:col-span-2 font-medium text-slate-700">
              By: {submission.submission_display_name}
            </div>
          )}
          <div>Email: {submission.email}</div>
          <div>Image: {submission.image_filename || 'None'}</div>
          <div>Image size: {formatBytes(submission.image_size)}</div>
          <div>
            Account: {submission.submitted_by?.display_name || 'Unknown'} (@{submission.submitted_by?.username || 'unknown'})
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
        <div className="flex flex-wrap gap-2 pt-2">
          {admin && submission.status === 'pending' && (
            <>
              <Button onClick={() => onApprove(submission.id)} disabled={actionLoading} className="bg-emerald-600 hover:bg-emerald-700">
                <CheckCircle className="mr-2 h-4 w-4" />
                Approve
              </Button>
              <Button onClick={() => onReject(submission.id)} disabled={actionLoading} variant="outline">
                <XCircle className="mr-2 h-4 w-4" />
                Reject
              </Button>
            </>
          )}
          {canDelete && (
            <Button onClick={() => onDelete(submission.id)} disabled={actionLoading} variant="destructive">
              <Trash2 className="mr-2 h-4 w-4" />
              Delete
            </Button>
          )}
        </div>
      </div>
      <SubmissionImage submission={submission} className="max-h-80" />
    </div>
  )
}

function LeaderboardCard({ leaders = [], loading = false, onRefresh }) {
  return (
    <Card className="rounded-md">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Trophy className="h-5 w-5 text-amber-600" />
            <CardTitle className="text-lg">Leaderboard</CardTitle>
          </div>
          <Button onClick={onRefresh} variant="outline" size="sm" disabled={loading}>
            <RefreshCcw className="mr-2 h-3.5 w-3.5" />
            Refresh
          </Button>
        </div>
        <CardDescription>Top contributors (approved submissions)</CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="text-center text-sm text-slate-500">Loading…</div>
        ) : leaders.length === 0 ? (
          <div className="text-center text-sm text-slate-500">No approved submissions yet</div>
        ) : (
          <ol className="space-y-2">
            {leaders.slice(0, 10).map((leader, index) => (
              <li
                key={leader.email}
                className={`flex items-center justify-between rounded-md border px-3 py-2 text-sm ${
                  index === 0 ? 'border-amber-300 bg-amber-50' : 'bg-white'
                }`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className={`flex h-7 w-7 flex-none items-center justify-center rounded-full text-xs font-bold ${
                    index === 0 ? 'bg-amber-500 text-white' : index === 1 ? 'bg-slate-400 text-white' : index === 2 ? 'bg-orange-700 text-white' : 'bg-slate-200 text-slate-700'
                  }`}>
                    {index + 1}
                  </span>
                  <div className="min-w-0">
                    <div className="truncate font-medium text-slate-900">
                      {leader.display_name || leader.email}
                    </div>
                    <div className="truncate text-xs text-slate-500">{leader.email}</div>
                  </div>
                </div>
                <Badge variant="secondary">{leader.count}</Badge>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
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

  const [pins, setPins] = useState([])
  const [selectedPinId, setSelectedPinId] = useState(null)
  const [showEnlarge, setShowEnlarge] = useState(false)
  const [showPinPickerEnlarged, setShowPinPickerEnlarged] = useState(false)

  const [leaders, setLeaders] = useState([])
  const [leadersLoading, setLeadersLoading] = useState(false)

  const [backgroundUrl, setBackgroundUrl] = useState(null)
  const [backgroundUploading, setBackgroundUploading] = useState(false)
  const backgroundInputRef = useRef(null)

  const SUBMISSION_DRAFT_KEY = 'mapSubmissionDraft.v2'
  const initialDraft = (() => {
    if (typeof window === 'undefined') return {}
    try {
      const raw = window.localStorage.getItem(SUBMISSION_DRAFT_KEY)
      return raw ? JSON.parse(raw) : {}
    } catch {
      return {}
    }
  })()

  const [email, setEmail] = useState(initialDraft.email || '')
  const [authMethod, setAuthMethod] = useState(initialDraft.authMethod || 'email')
  const [password, setPassword] = useState('')
  const [shortcutPassword, setShortcutPassword] = useState('')
  const [verificationCode, setVerificationCode] = useState(initialDraft.verificationCode || '')
  const [verificationSent, setVerificationSent] = useState(Boolean(initialDraft.verificationSent))
  const [emailVerified, setEmailVerified] = useState(false)
  const [verificationLoading, setVerificationLoading] = useState(false)
  const [hasShortcutPassword, setHasShortcutPassword] = useState(false)
  const [title, setTitle] = useState(initialDraft.title || '')
  const [text, setText] = useState(initialDraft.text || '')
  const [displayName, setDisplayName] = useState(initialDraft.displayName || '')

  // Pin selection for submission: 'others' | <existingPinId> | 'new'
  const [pinChoice, setPinChoice] = useState(initialDraft.pinChoice || 'others')
  const [newPinName, setNewPinName] = useState('')
  const [newPinPoint, setNewPinPoint] = useState(null)

  const [imageFile, setImageFile] = useState(null)
  const [imagePreviewUrl, setImagePreviewUrl] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [isDraggingImage, setIsDraggingImage] = useState(false)
  const fileInputRef = useRef(null)

  const mapPath = normalizeMapPath()
  const isSubmissionPage = mapPath === '/map/submission'
  const isAdmin = ['admin', 'superadmin'].includes(user?.role)
  const isSuperadmin = user?.role === 'superadmin'
  const roleLabel = formatRole(user?.role)

  const submissionsByPin = useMemo(() => {
    const result = { others: 0 }
    for (const submission of approvedSubmissions) {
      const key = submission.pin_id || 'others'
      result[key] = (result[key] || 0) + 1
    }
    return result
  }, [approvedSubmissions])

  const selectedSubmissions = useMemo(() => {
    if (!selectedPinId) return []
    if (selectedPinId === 'others') {
      return approvedSubmissions.filter((submission) => !submission.pin_id)
    }
    return approvedSubmissions.filter((submission) => submission.pin_id === selectedPinId)
  }, [approvedSubmissions, selectedPinId])

  const selectedPinName = useMemo(() => {
    if (!selectedPinId) return ''
    if (selectedPinId === 'others') return 'Others (no pin selected)'
    const pin = pins.find((candidate) => candidate.id === selectedPinId)
    return pin ? pin.name : 'Selected pin'
  }, [pins, selectedPinId])

  const loadApprovedSubmissions = async () => {
    setApprovedLoading(true)
    try {
      const response = await fetch(`${API_BASE}/map/submissions`)
      const result = await readApiResponse(response)
      const data = result.data
      if (result.ok) {
        setApprovedSubmissions(Array.isArray(data.submissions) ? data.submissions : [])
      } else {
        showMessage(buildApiErrorMessage(result, 'MAP_LOAD_APPROVED_FAILED', 'Failed to load map submissions'), 'error')
      }
    } catch (error) {
      showMessage(buildNetworkErrorMessage('MAP_LOAD_APPROVED_NETWORK', 'Failed to load map submissions', error), 'error')
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
      const result = await readApiResponse(response)
      const data = result.data
      if (result.ok) {
        setPendingSubmissions(Array.isArray(data.submissions) ? data.submissions : [])
      } else {
        showMessage(buildApiErrorMessage(result, 'MAP_LOAD_PENDING_FAILED', 'Failed to load pending map submissions'), 'error')
      }
    } catch (error) {
      showMessage(buildNetworkErrorMessage('MAP_LOAD_PENDING_NETWORK', 'Failed to load pending map submissions', error), 'error')
    } finally {
      setPendingLoading(false)
    }
  }

  const loadPins = async () => {
    try {
      const response = await fetch(`${API_BASE}/map/pins`)
      const result = await readApiResponse(response)
      if (result.ok) {
        setPins(Array.isArray(result.data.pins) ? result.data.pins : [])
      }
    } catch {
      // non-fatal
    }
  }

  const loadLeaders = async () => {
    setLeadersLoading(true)
    try {
      const response = await fetch(`${API_BASE}/map/leaderboard`)
      const result = await readApiResponse(response)
      if (result.ok) {
        setLeaders(Array.isArray(result.data.leaderboard) ? result.data.leaderboard : [])
      }
    } catch {
      // non-fatal
    } finally {
      setLeadersLoading(false)
    }
  }

  const loadBackground = async () => {
    try {
      const response = await fetch(`${API_BASE}/map/background/info`)
      const result = await readApiResponse(response)
      if (result.ok && result.data.has_background) {
        // cache-bust on uploaded_at
        const bust = result.data.uploaded_at ? `?t=${encodeURIComponent(result.data.uploaded_at)}` : ''
        setBackgroundUrl(`${API_BASE}/map/background${bust}`)
      } else {
        setBackgroundUrl(null)
      }
    } catch {
      setBackgroundUrl(null)
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
      const result = await readApiResponse(response)
      setHasShortcutPassword(Boolean(result.ok && result.data.has_password))
    } catch {
      setHasShortcutPassword(false)
    }
  }

  useEffect(() => {
    const originalTitle = document.title
    document.title = isSubmissionPage ? 'Ecological Map Submission' : 'Ecological Map'
    return () => {
      document.title = originalTitle
    }
  }, [isSubmissionPage])

  useEffect(() => {
    loadApprovedSubmissions()
    loadPendingSubmissions()
    loadPins()
    loadLeaders()
    loadBackground()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.role])

  useEffect(() => {
    if (!isSubmissionPage) return
    if (typeof window === 'undefined') return
    try {
      const draft = { email, authMethod, title, text, displayName, verificationCode, verificationSent, pinChoice }
      window.localStorage.setItem(SUBMISSION_DRAFT_KEY, JSON.stringify(draft))
    } catch {
      // localStorage may be unavailable - non-fatal
    }
  }, [isSubmissionPage, email, authMethod, title, text, displayName, verificationCode, verificationSent, pinChoice])

  useEffect(() => {
    if (!imageFile) {
      setImagePreviewUrl('')
      return
    }
    const url = URL.createObjectURL(imageFile)
    setImagePreviewUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [imageFile])

  useEffect(() => {
    if (!isSubmissionPage) {
      return
    }
    const handlePaste = (event) => {
      const items = event.clipboardData?.items
      if (!items || items.length === 0) {
        return
      }
      for (const item of items) {
        if (item.kind === 'file' && item.type.startsWith('image/')) {
          const file = item.getAsFile()
          if (file) {
            event.preventDefault()
            handleImageChange(file)
            return
          }
        }
      }
    }
    window.addEventListener('paste', handlePaste)
    return () => window.removeEventListener('paste', handlePaste)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSubmissionPage])

  const getRecaptchaToken = () => {
    if (!RECAPTCHA_SITE_KEY) {
      return null
    }
    const token = recaptchaRef.current?.getValue()
    if (!token) {
      showMessage('[MAP_RECAPTCHA_REQUIRED_CLIENT] Please complete the reCAPTCHA verification', 'error')
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
      showMessage('[MAP_EMAIL_DOMAIN_DENIED_CLIENT] Use an @sac.on.ca email address', 'error')
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
      const result = await readApiResponse(response)
      if (result.ok) {
        setVerificationSent(true)
        showMessage('Verification code sent', 'success')
      } else {
        showMessage(buildApiErrorMessage(result, 'MAP_VERIFICATION_SEND_FAILED', 'Failed to send verification code'), 'error')
      }
    } catch (error) {
      showMessage(buildNetworkErrorMessage('MAP_VERIFICATION_SEND_NETWORK', 'Failed to send verification code', error), 'error')
    } finally {
      resetRecaptcha()
      setVerificationLoading(false)
    }
  }

  const verifyEmailCode = async () => {
    const trimmedEmail = email.trim().toLowerCase()
    const trimmedCode = verificationCode.trim()

    if (trimmedCode.length !== 6 || !/^\d+$/.test(trimmedCode)) {
      showMessage('[MAP_VERIFICATION_CODE_INVALID_CLIENT] Verification code must be 6 digits', 'error')
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
      const result = await readApiResponse(response)
      const data = result.data
      if (result.ok && data.verified) {
        setEmailVerified(true)
        showMessage('Email verified', 'success')
      } else {
        showMessage(buildApiErrorMessage(result, 'MAP_VERIFICATION_CHECK_FAILED', 'Invalid verification code'), 'error')
      }
    } catch (error) {
      showMessage(buildNetworkErrorMessage('MAP_VERIFICATION_CHECK_NETWORK', 'Failed to verify code', error), 'error')
    } finally {
      setVerificationLoading(false)
    }
  }

  const resetSubmissionForm = () => {
    setTitle('')
    setText('')
    setDisplayName('')
    setPinChoice('others')
    setNewPinName('')
    setNewPinPoint(null)
    setImageFile(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
    setPassword('')
    setShortcutPassword('')
    setVerificationCode('')
    setVerificationSent(false)
    setEmailVerified(false)
    if (typeof window !== 'undefined') {
      try {
        window.localStorage.removeItem(SUBMISSION_DRAFT_KEY)
      } catch {
        // ignore
      }
    }
  }

  const handleImageChange = (file) => {
    if (!file) {
      setImageFile(null)
      return
    }

    if (!MAP_ALLOWED_IMAGE_TYPES.has(file.type)) {
      showMessage('[MAP_IMAGE_TYPE_UNSUPPORTED_CLIENT] Image must be a JPG, PNG, WebP, or GIF file', 'error')
      setImageFile(null)
      return
    }

    if (file.size > MAP_MAX_IMAGE_BYTES) {
      showMessage('[MAP_IMAGE_TOO_LARGE_CLIENT] Image must be 50 MB or smaller', 'error')
      setImageFile(null)
      return
    }

    setImageFile(file)
  }

  const handleRemoveImage = () => {
    setImageFile(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleImageDrop = (event) => {
    event.preventDefault()
    setIsDraggingImage(false)
    const file = event.dataTransfer?.files?.[0]
    if (file) {
      handleImageChange(file)
    }
  }

  const handleImageDragOver = (event) => {
    event.preventDefault()
    if (event.dataTransfer) {
      event.dataTransfer.dropEffect = 'copy'
    }
    if (!isDraggingImage) {
      setIsDraggingImage(true)
    }
  }

  const handleImageDragLeave = (event) => {
    event.preventDefault()
    setIsDraggingImage(false)
  }

  const handleSubmissionMapClick = (x, y) => {
    if (pinChoice !== 'new') return
    setNewPinPoint({ x, y })
  }

  const submitMapEntry = async () => {
    const trimmedEmail = email.trim().toLowerCase()
    if (!trimmedEmail.endsWith('@sac.on.ca')) {
      showMessage('[MAP_EMAIL_DOMAIN_DENIED_CLIENT] Use an @sac.on.ca email address', 'error')
      return
    }

    if (!title.trim()) {
      showMessage('[MAP_SUBMISSION_TITLE_REQUIRED_CLIENT] Enter a title', 'error')
      return
    }

    if (!text.trim()) {
      showMessage('[MAP_SUBMISSION_TEXT_REQUIRED_CLIENT] Enter a description', 'error')
      return
    }

    if (authMethod === 'email' && !emailVerified) {
      showMessage('[MAP_EMAIL_NOT_VERIFIED_CLIENT] Verify your SAC email before submitting', 'error')
      return
    }

    if (authMethod === 'password' && !password) {
      showMessage('[MAP_PASSWORD_REQUIRED_CLIENT] Enter your map submission password', 'error')
      return
    }

    if (pinChoice === 'new') {
      if (!newPinName.trim()) {
        showMessage('[MAP_PIN_NAME_REQUIRED_CLIENT] Name your new pin', 'error')
        return
      }
      if (!newPinPoint) {
        showMessage('[MAP_PIN_LOCATION_REQUIRED_CLIENT] Click on the map to place your pin', 'error')
        return
      }
    }

    if (imageFile) {
      if (!MAP_ALLOWED_IMAGE_TYPES.has(imageFile.type)) {
        showMessage('[MAP_IMAGE_TYPE_UNSUPPORTED_CLIENT] Image must be a JPG, PNG, WebP, or GIF file', 'error')
        return
      }
      if (imageFile.size > MAP_MAX_IMAGE_BYTES) {
        showMessage('[MAP_IMAGE_TOO_LARGE_CLIENT] Image must be 50 MB or smaller', 'error')
        return
      }
    }

    const recaptchaToken = getRecaptchaToken()
    if (recaptchaToken === undefined) {
      return
    }

    setSubmitting(true)
    try {
      // If pin is 'new', create the pin first
      let resolvedPinId = ''
      if (pinChoice === 'new') {
        const pinResponse = await fetch(`${API_BASE}/map/pins`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: newPinName.trim(),
            x: newPinPoint.x,
            y: newPinPoint.y,
            email: trimmedEmail
          })
        })
        const pinResult = await readApiResponse(pinResponse)
        if (!pinResult.ok) {
          showMessage(buildApiErrorMessage(pinResult, 'MAP_PIN_CREATE_FAILED', 'Failed to create pin'), 'error')
          setSubmitting(false)
          return
        }
        resolvedPinId = pinResult.data.pin?.id || ''
        await loadPins()
      } else if (pinChoice !== 'others') {
        resolvedPinId = pinChoice
      }

      const formData = new FormData()
      formData.append('email', trimmedEmail)
      formData.append('title', title.trim())
      formData.append('text', text.trim())
      if (displayName.trim()) {
        formData.append('submission_display_name', displayName.trim())
      }
      if (resolvedPinId) {
        formData.append('pin_id', resolvedPinId)
      }
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

      const response = await fetch(`${API_BASE}/map/submissions`, {
        method: 'POST',
        body: formData
      })
      const result = await readApiResponse(response)
      const data = result.data
      if (result.ok) {
        showMessage(
          data.password_created
            ? 'Submission sent and shortcut password saved'
            : 'Submission sent for approval',
          'success'
        )
        resetSubmissionForm()
        await loadApprovedSubmissions()
        await loadPendingSubmissions()
        await loadPins()
      } else {
        showMessage(buildApiErrorMessage(result, 'MAP_SUBMIT_FAILED', 'Failed to submit map entry'), 'error')
        console.error('Map submission failed:', { status: result.status, data: result.data, raw: result.raw })
      }
    } catch (error) {
      showMessage(buildNetworkErrorMessage('MAP_SUBMIT_NETWORK', 'Failed to submit map entry', error), 'error')
      console.error('Map submission network/parse failure:', error)
    } finally {
      resetRecaptcha()
      setSubmitting(false)
    }
  }

  const approveSubmission = async (submissionId) => {
    setActionLoading(true)
    try {
      const response = await fetch(`${API_BASE}/map/submissions/${submissionId}/approve`, { method: 'POST' })
      const result = await readApiResponse(response)
      if (result.ok) {
        showMessage('Map submission approved', 'success')
        await loadApprovedSubmissions()
        await loadPendingSubmissions()
        await loadLeaders()
      } else {
        showMessage(buildApiErrorMessage(result, 'MAP_APPROVE_FAILED', 'Failed to approve submission'), 'error')
      }
    } catch (error) {
      showMessage(buildNetworkErrorMessage('MAP_APPROVE_NETWORK', 'Failed to approve submission', error), 'error')
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
      const result = await readApiResponse(response)
      if (result.ok) {
        showMessage('Map submission rejected', 'success')
        await loadPendingSubmissions()
      } else {
        showMessage(buildApiErrorMessage(result, 'MAP_REJECT_FAILED', 'Failed to reject submission'), 'error')
      }
    } catch (error) {
      showMessage(buildNetworkErrorMessage('MAP_REJECT_NETWORK', 'Failed to reject submission', error), 'error')
    } finally {
      setActionLoading(false)
    }
  }

  const deleteSubmission = async (submissionId) => {
    if (typeof window !== 'undefined' && !window.confirm('Permanently delete this submission?')) {
      return
    }
    setActionLoading(true)
    try {
      const response = await fetch(`${API_BASE}/map/submissions/${submissionId}`, { method: 'DELETE' })
      const result = await readApiResponse(response)
      if (result.ok) {
        showMessage('Submission deleted', 'success')
        await loadApprovedSubmissions()
        await loadPendingSubmissions()
        await loadLeaders()
      } else {
        showMessage(buildApiErrorMessage(result, 'MAP_SUBMISSION_DELETE_FAILED', 'Failed to delete submission'), 'error')
      }
    } catch (error) {
      showMessage(buildNetworkErrorMessage('MAP_SUBMISSION_DELETE_NETWORK', 'Failed to delete submission', error), 'error')
    } finally {
      setActionLoading(false)
    }
  }

  const handleBackgroundUpload = async (file) => {
    if (!file) return
    if (!MAP_ALLOWED_IMAGE_TYPES.has(file.type)) {
      showMessage('[MAP_BACKGROUND_TYPE_UNSUPPORTED_CLIENT] Image must be a JPG, PNG, WebP, or GIF file', 'error')
      return
    }
    if (file.size > MAP_MAX_IMAGE_BYTES) {
      showMessage('[MAP_BACKGROUND_TOO_LARGE_CLIENT] Image must be 50 MB or smaller', 'error')
      return
    }

    setBackgroundUploading(true)
    try {
      const formData = new FormData()
      formData.append('image', file)
      const response = await fetch(`${API_BASE}/map/background`, { method: 'POST', body: formData })
      const result = await readApiResponse(response)
      if (result.ok) {
        showMessage('Map background updated', 'success')
        await loadBackground()
      } else {
        showMessage(buildApiErrorMessage(result, 'MAP_BACKGROUND_UPLOAD_FAILED', 'Failed to upload background'), 'error')
      }
    } catch (error) {
      showMessage(buildNetworkErrorMessage('MAP_BACKGROUND_UPLOAD_NETWORK', 'Failed to upload background', error), 'error')
    } finally {
      setBackgroundUploading(false)
      if (backgroundInputRef.current) {
        backgroundInputRef.current.value = ''
      }
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <a
            href="/map"
            className="flex items-center gap-3 no-underline text-inherit hover:opacity-90"
          >
            <div className="flex h-11 w-11 items-center justify-center rounded-md bg-teal-700 text-white">
              <MapPinned className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-950">Ecological Map</h1>
              <p className="text-sm text-slate-500">
                Brought to you by SAC Environmental Council. Check out{' '}
                <a
                  href="https://goldenplate.ca"
                  onClick={(event) => event.stopPropagation()}
                  className="underline hover:text-slate-700"
                >
                  Golden Plate
                </a>
              </p>
            </div>
          </a>
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
            {user ? (
              <Button onClick={logout} variant="outline" size="sm">
                <LogOut className="mr-2 h-4 w-4" />
                Logout
              </Button>
            ) : (
              <Button asChild variant="outline" size="sm">
                <a href="/">Login</a>
              </Button>
            )}
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
            <div className="flex flex-wrap gap-2">
              <Button onClick={loadPendingSubmissions} variant="outline" size="sm" disabled={pendingLoading}>
                <RefreshCcw className="mr-2 h-4 w-4" />
                Refresh
              </Button>
              <Button onClick={() => setShowApprovals(true)} size="sm" className="bg-amber-700 hover:bg-amber-800">
                Open Approvals
              </Button>
              {isSuperadmin && (
                <>
                  <input
                    ref={backgroundInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/gif"
                    className="sr-only"
                    onChange={(event) => handleBackgroundUpload(event.target.files?.[0] || null)}
                  />
                  <Button
                    onClick={() => backgroundInputRef.current?.click()}
                    size="sm"
                    variant="outline"
                    disabled={backgroundUploading}
                  >
                    <ImageIcon className="mr-2 h-4 w-4" />
                    {backgroundUploading ? 'Uploading…' : 'Upload Map Background'}
                  </Button>
                </>
              )}
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
              <h2 className="text-4xl font-bold tracking-normal text-slate-950">Ecological Map</h2>
              <p className="mt-3 max-w-xl text-base leading-7 text-slate-600">
                Approved submissions appear here after review. Click a pin to see its submissions, or click <span className="font-semibold">Others</span> to view submissions without a pin.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-md border bg-slate-50 p-3">
                <div className="text-xs font-semibold uppercase text-slate-500">Pins</div>
                <div className="mt-1 text-lg font-bold">{pins.length}</div>
              </div>
              <div className="rounded-md border bg-slate-50 p-3">
                <div className="text-xs font-semibold uppercase text-slate-500">Approved</div>
                <div className="mt-1 text-lg font-bold">{approvedSubmissions.length}</div>
              </div>
              <div className="rounded-md border bg-slate-50 p-3">
                <div className="text-xs font-semibold uppercase text-slate-500">Username</div>
                <div className="mt-1 truncate text-lg font-bold">@{user?.username || 'guest'}</div>
              </div>
            </div>
            <Button onClick={() => setShowEnlarge(true)} variant="outline" size="sm" className="w-fit">
              <ZoomIn className="mr-2 h-4 w-4" />
              Enlarge map
            </Button>
          </div>
          <EcologicalMapGraphic
            pins={pins}
            submissionsByPin={submissionsByPin}
            selectedPinId={selectedPinId}
            onSelectPin={setSelectedPinId}
            backgroundUrl={backgroundUrl}
          />
        </section>

        {selectedPinId && (
          <section className="space-y-3">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <h3 className="text-xl font-bold text-slate-950">
                {selectedPinName}{' '}
                <span className="ml-1 text-sm font-medium text-slate-500">
                  ({selectedSubmissions.length} {selectedSubmissions.length === 1 ? 'submission' : 'submissions'})
                </span>
              </h3>
              <Button onClick={() => setSelectedPinId(null)} variant="ghost" size="sm">
                <X className="mr-2 h-4 w-4" />
                Close
              </Button>
            </div>
            {selectedSubmissions.length === 0 ? (
              <div className="rounded-md border bg-white p-6 text-center text-sm text-slate-500">
                No approved submissions here yet
              </div>
            ) : (
              <div className="space-y-4">
                {selectedSubmissions.map((submission) => (
                  <SubmissionDetails
                    key={submission.id}
                    submission={submission}
                    canDelete={isSuperadmin}
                    actionLoading={actionLoading}
                    onDelete={deleteSubmission}
                  />
                ))}
              </div>
            )}
          </section>
        )}

        {isSubmissionPage ? (
          <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(22rem,0.7fr)]">
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
                  <Label htmlFor="map-title">Title</Label>
                  <Input
                    id="map-title"
                    placeholder="Short title for your submission"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    maxLength={200}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="map-text">Description</Label>
                  <Textarea
                    id="map-text"
                    placeholder="Describe your submission"
                    rows={6}
                    value={text}
                    onChange={(event) => setText(event.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="map-display-name">Display name (optional)</Label>
                  <Input
                    id="map-display-name"
                    placeholder="Name to show with your submission"
                    value={displayName}
                    onChange={(event) => setDisplayName(event.target.value)}
                    maxLength={80}
                  />
                </div>

                <div className="space-y-2">
                  <Label>Pin location</Label>
                  <div className="grid gap-2 sm:grid-cols-3">
                    <button
                      type="button"
                      onClick={() => { setPinChoice('others'); setNewPinPoint(null) }}
                      className={`rounded-md border px-3 py-2 text-sm font-medium ${pinChoice === 'others' ? 'border-teal-700 bg-teal-700 text-white' : 'bg-white text-slate-700 hover:bg-slate-50'}`}
                    >
                      Others (no pin)
                    </button>
                    <button
                      type="button"
                      onClick={() => { setPinChoice('existing'); setNewPinPoint(null) }}
                      className={`rounded-md border px-3 py-2 text-sm font-medium ${pinChoice !== 'others' && pinChoice !== 'new' ? 'border-teal-700 bg-teal-700 text-white' : 'bg-white text-slate-700 hover:bg-slate-50'}`}
                      disabled={pins.length === 0}
                    >
                      Existing pin
                    </button>
                    <button
                      type="button"
                      onClick={() => { setPinChoice('new') }}
                      className={`rounded-md border px-3 py-2 text-sm font-medium ${pinChoice === 'new' ? 'border-teal-700 bg-teal-700 text-white' : 'bg-white text-slate-700 hover:bg-slate-50'}`}
                    >
                      <Plus className="mr-1 inline h-3.5 w-3.5" />
                      New pin
                    </button>
                  </div>

                  {pinChoice !== 'others' && pinChoice !== 'new' && (
                    <select
                      value={pins.find((pin) => pin.id === pinChoice) ? pinChoice : ''}
                      onChange={(event) => setPinChoice(event.target.value || 'others')}
                      className="mt-2 w-full rounded-md border bg-white px-3 py-2 text-sm"
                    >
                      <option value="">Select a pin…</option>
                      {pins.map((pin) => (
                        <option key={pin.id} value={pin.id}>
                          {pin.name}
                        </option>
                      ))}
                    </select>
                  )}

                  {pinChoice === 'new' && (
                    <div className="mt-2 space-y-2 rounded-md border bg-slate-50 p-3">
                      <Input
                        placeholder="Pin name"
                        value={newPinName}
                        onChange={(event) => setNewPinName(event.target.value)}
                        maxLength={80}
                      />
                      <div className="flex items-center justify-between">
                        <p className="text-xs text-slate-500">
                          Click anywhere on the map to place your pin.
                        </p>
                        <Button
                          type="button"
                          onClick={() => setShowPinPickerEnlarged(true)}
                          variant="outline"
                          size="sm"
                        >
                          <ZoomIn className="mr-2 h-3.5 w-3.5" />
                          Enlarge for precise placement
                        </Button>
                      </div>
                      <EcologicalMapGraphic
                        pins={pins}
                        submissionsByPin={submissionsByPin}
                        backgroundUrl={backgroundUrl}
                        pendingPoint={newPinPoint}
                        onMapClick={handleSubmissionMapClick}
                        className="min-h-[18rem]"
                      />
                      {newPinPoint && (
                        <div className="text-xs text-slate-600">
                          <MapPinIcon className="mr-1 inline h-3.5 w-3.5 text-sky-600" />
                          Placed at ({newPinPoint.x.toFixed(1)}, {newPinPoint.y.toFixed(1)})
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div className="space-y-3">
                  <Label htmlFor="map-image">Image</Label>
                  <label
                    htmlFor="map-image"
                    onDragOver={handleImageDragOver}
                    onDragEnter={handleImageDragOver}
                    onDragLeave={handleImageDragLeave}
                    onDrop={handleImageDrop}
                    className={`flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-md border border-dashed p-4 text-center transition-colors ${
                      isDraggingImage
                        ? 'border-teal-500 bg-teal-50'
                        : 'bg-slate-50 hover:bg-slate-100'
                    }`}
                  >
                    <Upload className="mb-2 h-6 w-6 text-slate-500" />
                    <span className="text-sm font-medium text-slate-700">
                      {imageFile ? imageFile.name : 'Choose image, drag & drop, or paste (Ctrl/Cmd+V)'}
                    </span>
                    <span className="text-xs text-slate-500">JPG, PNG, WebP, or GIF up to 50 MB</span>
                    <input
                      ref={fileInputRef}
                      id="map-image"
                      type="file"
                      accept="image/jpeg,image/png,image/webp,image/gif"
                      className="sr-only"
                      onChange={(event) => handleImageChange(event.target.files?.[0] || null)}
                    />
                  </label>
                  {imagePreviewUrl && (
                    <div className="relative">
                      <img src={imagePreviewUrl} alt="Selected preview" className="max-h-72 w-full rounded-md border object-cover" />
                      <button
                        type="button"
                        onClick={handleRemoveImage}
                        aria-label="Remove image"
                        className="absolute right-2 top-2 inline-flex h-8 w-8 items-center justify-center rounded-full bg-black/60 text-white shadow hover:bg-black/80 focus:outline-none focus:ring-2 focus:ring-white"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
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

            <div className="space-y-6">
              <Card className="rounded-md">
                <CardHeader>
                  <CardTitle>Preview</CardTitle>
                  <CardDescription>Current draft</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="rounded-md border bg-slate-50 p-4">
                    <div className="text-xs font-semibold uppercase text-slate-500">Title</div>
                    <div className="mt-1 break-words text-sm font-semibold">{title || 'No title entered'}</div>
                  </div>
                  <div className="rounded-md border bg-slate-50 p-4">
                    <div className="text-xs font-semibold uppercase text-slate-500">Description</div>
                    <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{text || 'No description entered'}</p>
                  </div>
                  <div className="rounded-md border bg-slate-50 p-4">
                    <div className="text-xs font-semibold uppercase text-slate-500">Display name</div>
                    <div className="mt-1 break-words text-sm">{displayName || '— (will fall back to email)'}</div>
                  </div>
                  <div className="rounded-md border bg-slate-50 p-4">
                    <div className="text-xs font-semibold uppercase text-slate-500">Pin</div>
                    <div className="mt-1 break-words text-sm">
                      {pinChoice === 'others'
                        ? 'Others (no pin)'
                        : pinChoice === 'new'
                        ? `New pin: ${newPinName || '(no name)'}${newPinPoint ? ` @ (${newPinPoint.x.toFixed(1)}, ${newPinPoint.y.toFixed(1)})` : ' — pick a location'}`
                        : pins.find((pin) => pin.id === pinChoice)?.name || 'Choose a pin'}
                    </div>
                  </div>
                  {imagePreviewUrl ? (
                    <img src={imagePreviewUrl} alt="Draft preview" className="max-h-80 w-full rounded-md border object-cover" />
                  ) : (
                    <div className="flex min-h-48 items-center justify-center rounded-md border border-dashed bg-slate-50 text-sm text-slate-500">
                      <ImageIcon className="mr-2 h-4 w-4" />
                      No image selected
                    </div>
                  )}
                </CardContent>
              </Card>

              <LeaderboardCard leaders={leaders} loading={leadersLoading} onRefresh={loadLeaders} />
            </div>
          </section>
        ) : (
          <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(22rem,0.55fr)]">
            <div className="space-y-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-2xl font-bold text-slate-950">All approved submissions</h2>
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
                    <SubmissionDetails
                      key={submission.id}
                      submission={submission}
                      canDelete={isSuperadmin}
                      actionLoading={actionLoading}
                      onDelete={deleteSubmission}
                    />
                  ))}
                </div>
              )}
            </div>
            <LeaderboardCard leaders={leaders} loading={leadersLoading} onRefresh={loadLeaders} />
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
                  canDelete={isSuperadmin}
                  actionLoading={actionLoading}
                  onApprove={approveSubmission}
                  onReject={rejectSubmission}
                  onDelete={deleteSubmission}
                />
              ))
            )}
          </div>
          <Button onClick={() => setShowApprovals(false)} className="w-full">
            Close
          </Button>
        </DialogContent>
      </Dialog>

      <Dialog open={showEnlarge} onOpenChange={setShowEnlarge}>
        <DialogContent className="w-full sm:max-w-5xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Ecological Map (enlarged)</DialogTitle>
            <DialogDescription>Click pins for details. Use this larger view for more precise placement.</DialogDescription>
          </DialogHeader>
          <div className="aspect-[4/3] w-full">
            <EcologicalMapGraphic
              pins={pins}
              submissionsByPin={submissionsByPin}
              selectedPinId={selectedPinId}
              onSelectPin={(id) => { setSelectedPinId(id); setShowEnlarge(false) }}
              backgroundUrl={backgroundUrl}
              className="h-full"
            />
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showPinPickerEnlarged} onOpenChange={setShowPinPickerEnlarged}>
        <DialogContent className="w-full sm:max-w-5xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Place your pin (enlarged)</DialogTitle>
            <DialogDescription>
              Click anywhere on the map to set your pin location. Use this larger view for more precise placement.
            </DialogDescription>
          </DialogHeader>
          <div className="aspect-[4/3] w-full">
            <EcologicalMapGraphic
              pins={pins}
              submissionsByPin={submissionsByPin}
              backgroundUrl={backgroundUrl}
              pendingPoint={newPinPoint}
              onMapClick={handleSubmissionMapClick}
              className="h-full"
            />
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-sm text-slate-600">
              {newPinPoint ? (
                <>
                  <MapPinIcon className="mr-1 inline h-4 w-4 text-sky-600" />
                  Placed at ({newPinPoint.x.toFixed(1)}, {newPinPoint.y.toFixed(1)})
                </>
              ) : (
                'No location set yet'
              )}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setNewPinPoint(null)} disabled={!newPinPoint}>
                Clear
              </Button>
              <Button onClick={() => setShowPinPickerEnlarged(false)}>Done</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default MapPortal
