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
  ChevronLeft,
  ChevronRight,
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
const MAP_HEIC_MIMES = new Set(['image/heic', 'image/heif'])

function isHeicFile(file) {
  if (!file) return false
  const t = (file.type || '').toLowerCase()
  if (MAP_HEIC_MIMES.has(t)) return true
  const n = (file.name || '').toLowerCase()
  return n.endsWith('.heic') || n.endsWith('.heif')
}

async function convertHeicViaServer(file, onProgress) {
  const lowerName = (file.name || '').toLowerCase()
  const formData = new FormData()
  formData.append('image', file, file.name || 'image.heic')

  // Use XHR so we can report upload progress + indeterminate "decoding" stage.
  const xhrPromise = new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/map/convert-heic')
    xhr.responseType = 'blob'
    if (xhr.upload && typeof onProgress === 'function') {
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          // Map upload to 0..70% of total progress.
          const pct = Math.round((event.loaded / event.total) * 70)
          onProgress({ phase: 'uploading', percent: pct })
        }
      }
      xhr.upload.onload = () => onProgress({ phase: 'decoding', percent: 75 })
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        if (typeof onProgress === 'function') onProgress({ phase: 'done', percent: 100 })
        resolve(xhr.response)
      } else {
        let msg = `HEIC conversion failed (HTTP ${xhr.status})`
        try {
          // Best-effort: try to read JSON error from the blob.
          const reader = new FileReader()
          reader.onload = () => {
            try {
              const data = JSON.parse(reader.result)
              msg = data?.error || data?.code || msg
            } catch { /* ignore */ }
            reject(new Error(msg))
          }
          reader.onerror = () => reject(new Error(msg))
          reader.readAsText(xhr.response)
        } catch {
          reject(new Error(msg))
        }
      }
    }
    xhr.onerror = () => reject(new Error('Network error during HEIC conversion'))
    xhr.send(formData)
  })

  const blob = await xhrPromise
  const mime = blob.type || 'image/png'
  const ext = mime === 'image/png' ? '.png' : (mime === 'image/jpeg' ? '.jpg' : '.png')
  const baseName = (lowerName.replace(/\.(heic|heif)$/i, '') || 'image') + ext
  return new File([blob], baseName, { type: mime })
}

const MAP_ALLOWED_IMAGE_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/heic', 'image/heif'])

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
  const images = (submission?.images && submission.images.length > 0)
    ? submission.images
    : (submission?.image_url ? [{ id: 'primary', url: submission.image_url, filename: submission.image_filename }] : [])
  const [lightboxIndex, setLightboxIndex] = useState(null)

  if (images.length === 0) {
    return (
      <div className={`flex min-h-44 items-center justify-center rounded-md border border-dashed bg-slate-50 text-sm text-slate-500 ${className}`}>
        No image attached
      </div>
    )
  }

  return (
    <>
      {images.length === 1 ? (
        <button
          type="button"
          onClick={() => setLightboxIndex(0)}
          className={`group relative block w-full overflow-hidden rounded-md border ${className}`}
          aria-label="View image"
        >
          <img
            src={images[0].url}
            alt={images[0].filename || 'Map submission'}
            className="w-full object-cover transition-transform group-hover:scale-[1.01]"
          />
          <span className="pointer-events-none absolute right-2 top-2 inline-flex items-center gap-1 rounded-full bg-black/55 px-2 py-1 text-[11px] font-medium text-white opacity-0 transition-opacity group-hover:opacity-100">
            <ZoomIn className="h-3 w-3" /> Click to enlarge
          </span>
        </button>
      ) : (
        <div className={`space-y-2 ${className}`}>
          <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
            {images.map((img, idx) => (
              <button
                key={img.id || idx}
                type="button"
                onClick={() => setLightboxIndex(idx)}
                className="group relative aspect-square overflow-hidden rounded-md border bg-slate-100"
                aria-label={`View image ${idx + 1} of ${images.length}`}
              >
                <img
                  src={img.url}
                  alt={img.filename || `Image ${idx + 1}`}
                  className="h-full w-full object-cover transition-transform group-hover:scale-105"
                />
                <span className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/0 text-white opacity-0 transition-all group-hover:bg-black/30 group-hover:opacity-100">
                  <ZoomIn className="h-5 w-5" />
                </span>
              </button>
            ))}
          </div>
          <div className="text-xs text-slate-500">{images.length} images — click any to enlarge</div>
        </div>
      )}
      {lightboxIndex !== null && (
        <ImageLightbox
          images={images}
          startIndex={lightboxIndex}
          onClose={() => setLightboxIndex(null)}
        />
      )}
    </>
  )
}

function ImageLightbox({ images, startIndex = 0, onClose }) {
  const [index, setIndex] = useState(startIndex)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const draggingRef = useRef(false)
  const lastPointerRef = useRef(null)
  const pointersRef = useRef(new Map())
  const pinchRef = useRef(null)
  const containerRef = useRef(null)
  const minZoom = 1
  const maxZoom = 8

  const current = images[index]

  // Reset zoom/pan when switching images.
  useEffect(() => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
  }, [index])

  // Keyboard navigation.
  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'Escape') onClose()
      else if (event.key === 'ArrowRight') setIndex((i) => Math.min(images.length - 1, i + 1))
      else if (event.key === 'ArrowLeft') setIndex((i) => Math.max(0, i - 1))
      else if (event.key === '+' || event.key === '=') setZoom((z) => Math.min(maxZoom, z * 1.25))
      else if (event.key === '-') setZoom((z) => Math.max(minZoom, z / 1.25))
      else if (event.key === '0') { setZoom(1); setPan({ x: 0, y: 0 }) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [images.length, onClose])

  const clampPan = (next, z) => {
    const node = containerRef.current
    if (!node) return next
    const rect = node.getBoundingClientRect()
    const overshootX = Math.max(0, (rect.width * (z - 1)) / 2)
    const overshootY = Math.max(0, (rect.height * (z - 1)) / 2)
    return {
      x: Math.max(-overshootX, Math.min(overshootX, next.x)),
      y: Math.max(-overshootY, Math.min(overshootY, next.y)),
    }
  }

  const onWheel = (event) => {
    event.preventDefault()
    const factor = event.deltaY < 0 ? 1.15 : 1 / 1.15
    setZoom((z) => {
      const next = Math.max(minZoom, Math.min(maxZoom, z * factor))
      if (next === 1) setPan({ x: 0, y: 0 })
      return next
    })
  }

  const onPointerDown = (event) => {
    pointersRef.current.set(event.pointerId, { x: event.clientX, y: event.clientY })
    if (pointersRef.current.size === 1) {
      draggingRef.current = true
      lastPointerRef.current = { x: event.clientX, y: event.clientY }
    } else if (pointersRef.current.size === 2) {
      const [a, b] = Array.from(pointersRef.current.values())
      pinchRef.current = {
        startDist: Math.hypot(a.x - b.x, a.y - b.y),
        startZoom: zoom,
      }
    }
    event.currentTarget.setPointerCapture?.(event.pointerId)
  }

  const onPointerMove = (event) => {
    if (!pointersRef.current.has(event.pointerId)) return
    pointersRef.current.set(event.pointerId, { x: event.clientX, y: event.clientY })
    if (pointersRef.current.size === 2 && pinchRef.current) {
      const [a, b] = Array.from(pointersRef.current.values())
      const dist = Math.hypot(a.x - b.x, a.y - b.y)
      if (pinchRef.current.startDist > 0) {
        const ratio = dist / pinchRef.current.startDist
        const next = Math.max(minZoom, Math.min(maxZoom, pinchRef.current.startZoom * Math.pow(ratio, 1.4)))
        setZoom(next)
        if (next === 1) setPan({ x: 0, y: 0 })
      }
      return
    }
    if (draggingRef.current && zoom > 1 && lastPointerRef.current) {
      const dx = event.clientX - lastPointerRef.current.x
      const dy = event.clientY - lastPointerRef.current.y
      lastPointerRef.current = { x: event.clientX, y: event.clientY }
      setPan((p) => clampPan({ x: p.x + dx, y: p.y + dy }, zoom))
    }
  }

  const onPointerUp = (event) => {
    pointersRef.current.delete(event.pointerId)
    if (pointersRef.current.size < 2) pinchRef.current = null
    if (pointersRef.current.size === 0) {
      draggingRef.current = false
      lastPointerRef.current = null
    }
  }

  const onDoubleClick = () => {
    if (zoom > 1) { setZoom(1); setPan({ x: 0, y: 0 }) }
    else setZoom(2)
  }

  return (
    <Dialog open onOpenChange={(next) => { if (!next) onClose() }}>
      <DialogContent className="w-full max-w-[95vw] max-h-[95vh] p-0 bg-black/95 border-slate-800">
        <DialogHeader className="px-4 pt-3 pb-2 text-white">
          <DialogTitle className="truncate text-sm font-medium text-white">
            {current?.filename || `Image ${index + 1}`} ({index + 1} / {images.length})
          </DialogTitle>
          <DialogDescription className="text-xs text-slate-400">
            Scroll / pinch to zoom • drag to pan • double-click to reset • ←/→ to navigate
          </DialogDescription>
        </DialogHeader>
        <div
          ref={containerRef}
          className="relative flex h-[78vh] w-full select-none items-center justify-center overflow-hidden bg-black touch-none"
          onWheel={onWheel}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          onDoubleClick={onDoubleClick}
          style={{ cursor: zoom > 1 ? 'grab' : 'zoom-in' }}
        >
          <img
            src={current?.url}
            alt={current?.filename || `Image ${index + 1}`}
            draggable={false}
            className="max-h-full max-w-full"
            style={{
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
              transformOrigin: 'center center',
              transition: draggingRef.current || pinchRef.current ? 'none' : 'transform 120ms ease-out',
              willChange: 'transform',
            }}
          />
          {images.length > 1 && (
            <>
              <button
                type="button"
                onClick={() => setIndex((i) => Math.max(0, i - 1))}
                disabled={index === 0}
                aria-label="Previous image"
                className="absolute left-3 top-1/2 -translate-y-1/2 rounded-full bg-black/60 p-2 text-white hover:bg-black/80 disabled:opacity-30"
              >
                <ChevronLeft className="h-5 w-5" />
              </button>
              <button
                type="button"
                onClick={() => setIndex((i) => Math.min(images.length - 1, i + 1))}
                disabled={index === images.length - 1}
                aria-label="Next image"
                className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full bg-black/60 p-2 text-white hover:bg-black/80 disabled:opacity-30"
              >
                <ChevronRight className="h-5 w-5" />
              </button>
            </>
          )}
          <div className="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-full bg-black/70 px-3 py-1.5 text-xs text-white">
            <button type="button" onClick={() => { setZoom((z) => Math.max(minZoom, z / 1.25)) }} className="rounded px-1 hover:bg-white/10" aria-label="Zoom out">−</button>
            <span className="tabular-nums">{Math.round(zoom * 100)}%</span>
            <button type="button" onClick={() => { setZoom((z) => Math.min(maxZoom, z * 1.25)) }} className="rounded px-1 hover:bg-white/10" aria-label="Zoom in">+</button>
            <span className="mx-1 h-3 w-px bg-white/30" />
            <button type="button" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }) }} className="rounded px-2 hover:bg-white/10">Reset</button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

/**
 * Ecological map graphic. Pin coords are percentages (0-100 on each axis,
 * relative to the displayed background image's full extent).
 *
 * The container's aspect ratio matches the background image (or 4:3 default),
 * so circles/labels never get stretched. Pins/labels are HTML overlays
 * positioned by percentage so they remain perfectly round at any size.
 */
function EcologicalMapGraphic({
  pins = [],
  submissionsByPin = {},
  selectedPinId = null,
  onSelectPin,
  backgroundUrl = null,
  pendingPoint = null,
  onMapClick = null,
  imageAspect = null,
  naturalSize = null, // {w,h} — if provided, render at this exact pixel size
  fillContainer = false, // if true, ignore aspectRatio and fill the parent's height
  className = ''
}) {
  const containerRef = useRef(null)
  const aspect = imageAspect && imageAspect > 0 ? imageAspect : 4 / 3

  const handleClick = (event) => {
    if (onMapClick) {
      const node = containerRef.current
      if (!node) return
      const rect = node.getBoundingClientRect()
      if (rect.width <= 0 || rect.height <= 0) return
      const x = ((event.clientX - rect.left) / rect.width) * 100
      const y = ((event.clientY - rect.top) / rect.height) * 100
      if (x < 0 || x > 100 || y < 0 || y > 100) return
      onMapClick(Math.max(0, Math.min(100, x)), Math.max(0, Math.min(100, y)))
      return
    }
    // Not in placement mode: clicking the map background deselects any pin.
    if (onSelectPin && selectedPinId !== null && selectedPinId !== undefined) {
      onSelectPin(null)
    }
  }

  const containerStyle = naturalSize
    ? { width: naturalSize.w, height: naturalSize.h }
    : (fillContainer ? { height: '100%' } : { aspectRatio: `${aspect}` })

  return (
    <div className={`relative ${naturalSize ? '' : (fillContainer ? 'h-full w-full' : 'w-full')} ${className}`}>
      <div
        ref={containerRef}
        onClick={handleClick}
        className={`relative overflow-hidden rounded-md border bg-white shadow-sm ${naturalSize ? '' : (fillContainer ? 'h-full w-full' : 'w-full')} ${onMapClick ? 'cursor-crosshair' : ''}`}
        style={containerStyle}
      >
        {backgroundUrl ? (
          <img
            src={backgroundUrl}
            alt="Ecological Map background"
            className="absolute inset-0 h-full w-full select-none object-fill"
            draggable={false}
          />
        ) : (
          <div
            className="absolute inset-0"
            style={{ background: 'linear-gradient(135deg, #ecfdf5 0%, #dbeafe 100%)' }}
          />
        )}
        {/* Grid overlay */}
        <svg
          className="pointer-events-none absolute inset-0 h-full w-full"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          {Array.from({ length: 9 }, (_, i) => i + 1).map((i) => (
            <g key={i}>
              <line x1="0" y1={i * 10} x2="100" y2={i * 10} stroke="#cbd5e1" strokeWidth="0.15" strokeDasharray="0.6 0.6" vectorEffect="non-scaling-stroke" />
              <line x1={i * 10} y1="0" x2={i * 10} y2="100" stroke="#cbd5e1" strokeWidth="0.15" strokeDasharray="0.6 0.6" vectorEffect="non-scaling-stroke" />
            </g>
          ))}
        </svg>

        {/* Pin markers (HTML, always round) */}
        {pins.map((pin) => {
          const count = submissionsByPin[pin.id] || 0
          const selected = selectedPinId === pin.id
          return (
            <button
              key={pin.id}
              type="button"
              onClick={(event) => {
                event.stopPropagation()
                if (onSelectPin) onSelectPin(pin.id)
              }}
              className="group absolute -translate-x-1/2 -translate-y-1/2 focus:outline-none"
              style={{ left: `${pin.x}%`, top: `${pin.y}%` }}
              title={pin.name}
            >
              <span className={`absolute left-1/2 top-1/2 block h-7 w-7 -translate-x-1/2 -translate-y-1/2 rounded-full ${selected ? 'bg-red-500/30' : 'bg-orange-400/25'}`} />
              <span className={`relative block rounded-full border-2 border-white shadow ${selected ? 'h-4 w-4 bg-red-600' : 'h-3 w-3 bg-orange-500 group-hover:bg-orange-600'}`} />
              <span
                className="pointer-events-none absolute left-1/2 top-0 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded bg-white/90 px-1.5 py-0.5 text-[10px] font-semibold text-slate-900 shadow-sm"
              >
                {pin.name}{count ? ` (${count})` : ''}
              </span>
            </button>
          )
        })}

        {/* Pending point (during placement) */}
        {pendingPoint && (
          <div
            className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2"
            style={{ left: `${pendingPoint.x}%`, top: `${pendingPoint.y}%` }}
          >
            <span className="absolute left-1/2 top-1/2 block h-7 w-7 -translate-x-1/2 -translate-y-1/2 rounded-full bg-sky-400/30" />
            <span className="relative block h-3 w-3 rounded-full border-2 border-white bg-sky-500 shadow" />
          </div>
        )}
      </div>
      {/* Others tag (bottom-right) — hidden in placement mode */}
      {!onMapClick && (
        <button
          type="button"
          onClick={() => onSelectPin && onSelectPin('others')}
          className={`absolute bottom-3 right-3 rounded-full border px-3 py-1 text-xs font-semibold shadow-sm transition ${
            selectedPinId === 'others' ? 'bg-slate-900 text-white' : 'bg-white/90 text-slate-700 hover:bg-slate-100'
          }`}
        >
          Others ({submissionsByPin.others || 0})
        </button>
      )}
    </div>
  )
}

function SubmissionDetails({ submission, admin = false, canDelete = false, actionLoading = false, onApprove, onReject, onDelete }) {
  const [showRejectDialog, setShowRejectDialog] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [deleteReason, setDeleteReason] = useState('')
  const submitReject = () => {
    const trimmed = rejectReason.trim()
    if (!trimmed) return
    onReject(submission.id, trimmed)
    setShowRejectDialog(false)
    setRejectReason('')
  }
  const submitDelete = () => {
    const trimmed = deleteReason.trim()
    if (!trimmed) return
    onDelete(submission.id, trimmed)
    setShowDeleteDialog(false)
    setDeleteReason('')
  }
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
              <Button onClick={() => onReject(submission.id, '')} disabled={actionLoading} variant="outline">
                <XCircle className="mr-2 h-4 w-4" />
                Reject
              </Button>
              <Button onClick={() => setShowRejectDialog(true)} disabled={actionLoading} variant="outline" className="border-red-300 text-red-700 hover:bg-red-50">
                <XCircle className="mr-2 h-4 w-4" />
                Reject with comment
              </Button>
            </>
          )}
          {canDelete && (
            <>
              <Button onClick={() => onDelete(submission.id, '')} disabled={actionLoading} variant="destructive">
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </Button>
              <Button onClick={() => setShowDeleteDialog(true)} disabled={actionLoading} variant="destructive" className="bg-red-700 hover:bg-red-800">
                <Trash2 className="mr-2 h-4 w-4" />
                Delete with comment
              </Button>
            </>
          )}
        </div>
      </div>
      <SubmissionImage submission={submission} className="max-h-80" />

      <Dialog open={showRejectDialog} onOpenChange={(next) => { if (!next) { setShowRejectDialog(false); setRejectReason('') } }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Reject with comment</DialogTitle>
            <DialogDescription>
              The comment will be emailed to the submitter at <span className="font-medium">{submission.email}</span>.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Label htmlFor={`reject-reason-${submission.id}`}>Reason</Label>
            <Textarea
              id={`reject-reason-${submission.id}`}
              value={rejectReason}
              onChange={(event) => setRejectReason(event.target.value)}
              placeholder="Explain what should be changed for resubmission…"
              rows={5}
            />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => { setShowRejectDialog(false); setRejectReason('') }} disabled={actionLoading}>Cancel</Button>
              <Button variant="destructive" onClick={submitReject} disabled={actionLoading || !rejectReason.trim()}>
                <XCircle className="mr-2 h-4 w-4" />
                Send rejection
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showDeleteDialog} onOpenChange={(next) => { if (!next) { setShowDeleteDialog(false); setDeleteReason('') } }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Delete with comment</DialogTitle>
            <DialogDescription>
              The submission will be permanently deleted and the comment emailed to <span className="font-medium">{submission.email}</span>.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Label htmlFor={`delete-reason-${submission.id}`}>Reason</Label>
            <Textarea
              id={`delete-reason-${submission.id}`}
              value={deleteReason}
              onChange={(event) => setDeleteReason(event.target.value)}
              placeholder="Explain why this submission is being deleted…"
              rows={5}
            />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => { setShowDeleteDialog(false); setDeleteReason('') }} disabled={actionLoading}>Cancel</Button>
              <Button variant="destructive" onClick={submitDelete} disabled={actionLoading || !deleteReason.trim()} className="bg-red-700 hover:bg-red-800">
                <Trash2 className="mr-2 h-4 w-4" />
                Delete and notify
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
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

const ASPECT_PRESETS = [
  { label: 'Free', value: null },
  { label: '1:1', value: 1 },
  { label: '4:3', value: 4 / 3 },
  { label: '3:4', value: 3 / 4 },
  { label: '3:2', value: 3 / 2 },
  { label: '2:3', value: 2 / 3 },
  { label: '16:9', value: 16 / 9 },
  { label: '9:16', value: 9 / 16 },
]

/**
 * Mini image editor: load file, pan, zoom, rotate, with crop rectangle that
 * supports common aspect-ratio presets. Output is a Blob (PNG by default).
 */
function MapBackgroundEditor({ open, onClose, onUpload, uploading = false }) {
  const fileInputRef = useRef(null)
  const stageRef = useRef(null)
  const [image, setImage] = useState(null) // HTMLImageElement
  const [originalFile, setOriginalFile] = useState(null)
  const [filename, setFilename] = useState('map-background.png')
  const [heicProgress, setHeicProgress] = useState(null) // {phase, percent} | null
  // image transform (rendered into stage)
  const [scale, setScale] = useState(1)
  const [rotation, setRotation] = useState(0)
  const [translate, setTranslate] = useState({ x: 0, y: 0 })
  // crop rectangle (in stage pixel coords)
  const [aspectRatio, setAspectRatio] = useState(null)
  const [crop, setCrop] = useState({ x: 0, y: 0, w: 0, h: 0 })
  const [stageSize, setStageSize] = useState({ w: 600, h: 400 })

  // drag state
  const dragRef = useRef(null)

  useEffect(() => {
    if (!open) {
      setImage(null)
      setOriginalFile(null)
      setScale(1)
      setRotation(0)
      setTranslate({ x: 0, y: 0 })
      setAspectRatio(null)
      setCrop({ x: 0, y: 0, w: 0, h: 0 })
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }, [open])

  // measure stage on mount/resize
  useEffect(() => {
    if (!open) return
    const node = stageRef.current
    if (!node) return
    const update = () => {
      const rect = node.getBoundingClientRect()
      setStageSize({ w: rect.width, h: rect.height })
    }
    update()
    const ro = new ResizeObserver(update)
    ro.observe(node)
    return () => ro.disconnect()
  }, [open, image])

  // when the image or stage changes, fit it
  useEffect(() => {
    if (!image || stageSize.w === 0 || stageSize.h === 0) return
    const fit = Math.min(stageSize.w / image.naturalWidth, stageSize.h / image.naturalHeight)
    setScale(fit)
    setTranslate({ x: 0, y: 0 })
    setRotation(0)
    // initial crop = inner 80% with current aspect
    initCrop(stageSize.w, stageSize.h, aspectRatio)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [image, stageSize.w, stageSize.h])

  const initCrop = (sw, sh, ar) => {
    // Default crop covers the displayed image exactly (centered),
    // so clicking Apply with no edits yields the original image.
    let w = sw
    let h = sh
    if (image) {
      const fit = Math.min(sw / image.naturalWidth, sh / image.naturalHeight)
      w = image.naturalWidth * fit
      h = image.naturalHeight * fit
    }
    if (ar && ar > 0) {
      if (w / h > ar) w = h * ar
      else h = w / ar
    }
    setCrop({ x: (sw - w) / 2, y: (sh - h) / 2, w, h })
  }

  const handleFile = async (file) => {
    if (!file) return
    const heic = isHeicFile(file)
    if (file.type && !MAP_ALLOWED_IMAGE_TYPES.has(file.type) && !heic) return
    let working = file
    if (heic) {
      setHeicProgress({ phase: 'uploading', percent: 0 })
      try {
        working = await convertHeicViaServer(file, (p) => setHeicProgress(p))
      } catch (err) {
        console.error('Server HEIC conversion failed', err)
        setHeicProgress(null)
        return
      }
      setHeicProgress(null)
    }
    setOriginalFile(working)
    setFilename(working.name || 'map-background.png')
    const reader = new FileReader()
    reader.onload = () => {
      const img = new Image()
      img.onload = () => setImage(img)
      img.src = reader.result
    }
    reader.readAsDataURL(working)
  }

  const onAspectChange = (ar) => {
    setAspectRatio(ar)
    if (stageSize.w > 0 && stageSize.h > 0) initCrop(stageSize.w, stageSize.h, ar)
  }

  // Image pan via drag on stage (when not on crop handle)
  const onStageMouseDown = (event) => {
    if (event.button !== 0) return
    const target = event.target
    if (target && target.dataset && target.dataset.handle) return // crop handle handles itself
    dragRef.current = {
      kind: 'pan',
      startX: event.clientX,
      startY: event.clientY,
      origX: translate.x,
      origY: translate.y,
    }
  }

  const onMouseMove = (event) => {
    const drag = dragRef.current
    if (!drag) return
    const dx = event.clientX - drag.startX
    const dy = event.clientY - drag.startY
    if (drag.kind === 'pan') {
      setTranslate({ x: drag.origX + dx, y: drag.origY + dy })
    } else if (drag.kind === 'crop-move') {
      const nx = Math.max(0, Math.min(stageSize.w - crop.w, drag.origX + dx))
      const ny = Math.max(0, Math.min(stageSize.h - crop.h, drag.origY + dy))
      setCrop({ ...crop, x: nx, y: ny })
    } else if (drag.kind === 'crop-resize') {
      const dir = drag.dir
      let { x, y, w, h } = drag.orig
      if (dir.includes('e')) w = Math.max(20, drag.orig.w + dx)
      if (dir.includes('s')) h = Math.max(20, drag.orig.h + dy)
      if (dir.includes('w')) {
        const newW = Math.max(20, drag.orig.w - dx)
        x = drag.orig.x + (drag.orig.w - newW)
        w = newW
      }
      if (dir.includes('n')) {
        const newH = Math.max(20, drag.orig.h - dy)
        y = drag.orig.y + (drag.orig.h - newH)
        h = newH
      }
      if (aspectRatio) {
        // Lock to aspect: prefer adjusting height from width unless dragging vertical-only
        if (dir === 'n' || dir === 's') {
          w = h * aspectRatio
          if (dir.includes('w')) x = drag.orig.x + (drag.orig.w - w)
          else x = drag.orig.x
        } else {
          h = w / aspectRatio
          if (dir.includes('n')) y = drag.orig.y + (drag.orig.h - h)
          else y = drag.orig.y
        }
      }
      // clamp to stage
      x = Math.max(0, Math.min(stageSize.w - w, x))
      y = Math.max(0, Math.min(stageSize.h - h, y))
      w = Math.min(w, stageSize.w - x)
      h = Math.min(h, stageSize.h - y)
      setCrop({ x, y, w, h })
    }
  }

  const onMouseUp = () => { dragRef.current = null }

  useEffect(() => {
    if (!open) return
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, crop, translate, stageSize, aspectRatio])

  const startCropMove = (event) => {
    event.stopPropagation()
    if (event.button !== 0) return
    dragRef.current = {
      kind: 'crop-move',
      startX: event.clientX,
      startY: event.clientY,
      origX: crop.x,
      origY: crop.y,
    }
  }

  const startCropResize = (dir) => (event) => {
    event.stopPropagation()
    if (event.button !== 0) return
    dragRef.current = {
      kind: 'crop-resize',
      dir,
      startX: event.clientX,
      startY: event.clientY,
      orig: { ...crop },
    }
  }

  const handleApply = async () => {
    if (!image || crop.w <= 0 || crop.h <= 0) return

    // Short-circuit: if the user hasn't transformed or cropped at all, just
    // upload the original file unchanged (no re-encoding, no compression).
    if (originalFile && rotation === 0 && translate.x === 0 && translate.y === 0) {
      const fit = Math.min(stageSize.w / image.naturalWidth, stageSize.h / image.naturalHeight)
      const sameScale = Math.abs(scale - fit) < 0.001
      const fullCropW = image.naturalWidth * fit
      const fullCropH = image.naturalHeight * fit
      const cropMatchesImage =
        Math.abs(crop.w - fullCropW) < 1 &&
        Math.abs(crop.h - fullCropH) < 1 &&
        Math.abs(crop.x - (stageSize.w - fullCropW) / 2) < 1 &&
        Math.abs(crop.y - (stageSize.h - fullCropH) / 2) < 1
      if (sameScale && cropMatchesImage) {
        await onUpload(originalFile, filename)
        return
      }
    }

    // Render at full image resolution so we don't downscale. The image is
    // displayed at `scale` on stage, so 1 stage-pixel == 1/scale image-pixels.
    const outW = Math.max(1, Math.round(crop.w / scale))
    const outH = Math.max(1, Math.round(crop.h / scale))
    const out = document.createElement('canvas')
    out.width = outW
    out.height = outH
    const ctx = out.getContext('2d')
    if (!ctx) return
    ctx.imageSmoothingQuality = 'high'

    // Render the (rotated, translated) image onto a high-resolution stage,
    // then copy the corresponding crop region into the output canvas.
    const stage = document.createElement('canvas')
    stage.width = Math.max(1, Math.round(stageSize.w / scale))
    stage.height = Math.max(1, Math.round(stageSize.h / scale))
    const sctx = stage.getContext('2d')
    if (!sctx) return
    sctx.fillStyle = '#0f172a'
    sctx.fillRect(0, 0, stage.width, stage.height)
    const cx = stage.width / 2 + translate.x / scale
    const cy = stage.height / 2 + translate.y / scale
    sctx.translate(cx, cy)
    sctx.rotate((rotation * Math.PI) / 180)
    sctx.drawImage(image, -image.naturalWidth / 2, -image.naturalHeight / 2)
    sctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.drawImage(
      stage,
      crop.x / scale, crop.y / scale, crop.w / scale, crop.h / scale,
      0, 0, outW, outH,
    )
    // PNG is lossless — no compression artifacts.
    const blob = await new Promise((resolve) => out.toBlob(resolve, 'image/png'))
    if (!blob) return
    const outName = filename.replace(/\.[^.]+$/, '') + '-edited.png'
    await onUpload(blob, outName)
  }

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) onClose() }}>
      <DialogContent className="w-full sm:max-w-5xl max-h-[92vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Map Background Editor</DialogTitle>
          <DialogDescription>
            Pick an image, then pan, zoom, rotate, and crop. Choose an aspect ratio to lock the crop.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              className="sr-only"
              onChange={(event) => handleFile(event.target.files?.[0] || null)}
            />
            <Button onClick={() => fileInputRef.current?.click()} variant="outline" size="sm">
              <Upload className="mr-2 h-4 w-4" />
              {image ? 'Replace image' : 'Choose image'}
            </Button>
            <span className="text-xs text-slate-500">{image ? `${image.naturalWidth}×${image.naturalHeight}` : 'No image loaded'}</span>
          </div>

          {heicProgress && (
            <div className="rounded-md border bg-amber-50 px-3 py-2 text-xs text-amber-900">
              <div className="mb-1 flex items-center justify-between font-medium">
                <span>{heicProgress.phase === 'uploading' ? 'Uploading HEIC…'
                  : heicProgress.phase === 'decoding' ? 'Decoding HEIC on server…'
                  : 'Finishing…'}</span>
                <span className="tabular-nums">{Math.round(heicProgress.percent)}%</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded bg-amber-200">
                <div
                  className="h-full bg-amber-600 transition-all"
                  style={{ width: `${Math.max(2, Math.min(100, heicProgress.percent))}%` }}
                />
              </div>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-1">
            <span className="mr-2 text-xs font-semibold uppercase text-slate-500">Aspect:</span>
            {ASPECT_PRESETS.map((preset) => (
              <button
                key={preset.label}
                type="button"
                onClick={() => onAspectChange(preset.value)}
                className={`rounded-md border px-2 py-1 text-xs font-medium transition ${
                  (aspectRatio === preset.value || (preset.value === null && aspectRatio === null))
                    ? 'border-teal-700 bg-teal-700 text-white'
                    : 'bg-white text-slate-700 hover:bg-slate-50'
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>

          <div
            ref={stageRef}
            onMouseDown={onStageMouseDown}
            className="relative h-[55vh] w-full select-none overflow-hidden rounded-md border bg-slate-900"
            style={{ cursor: image ? 'grab' : 'default' }}
          >
            {image ? (
              <>
                <img
                  src={image.src}
                  alt="Editing"
                  draggable={false}
                  className="pointer-events-none absolute left-1/2 top-1/2"
                  style={{
                    transform: `translate(-50%, -50%) translate(${translate.x}px, ${translate.y}px) rotate(${rotation}deg) scale(${scale})`,
                    transformOrigin: 'center center',
                    maxWidth: 'none',
                  }}
                />
                {/* Dim outside crop with 4 overlay rectangles */}
                <div className="pointer-events-none absolute bg-black/60" style={{ left: 0, top: 0, width: '100%', height: crop.y }} />
                <div className="pointer-events-none absolute bg-black/60" style={{ left: 0, top: crop.y + crop.h, width: '100%', height: Math.max(0, stageSize.h - (crop.y + crop.h)) }} />
                <div className="pointer-events-none absolute bg-black/60" style={{ left: 0, top: crop.y, width: crop.x, height: crop.h }} />
                <div className="pointer-events-none absolute bg-black/60" style={{ left: crop.x + crop.w, top: crop.y, width: Math.max(0, stageSize.w - (crop.x + crop.w)), height: crop.h }} />
                {/* Crop rectangle */}
                <div
                  className="absolute border-2 border-white shadow-[0_0_0_1px_rgba(0,0,0,0.4)]"
                  style={{ left: crop.x, top: crop.y, width: crop.w, height: crop.h, cursor: 'move' }}
                  data-handle="move"
                  onMouseDown={startCropMove}
                >
                  {/* Resize handles */}
                  {['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'].map((dir) => {
                    const styles = {
                      nw: { left: -6, top: -6, cursor: 'nwse-resize' },
                      n: { left: '50%', top: -6, marginLeft: -6, cursor: 'ns-resize' },
                      ne: { right: -6, top: -6, cursor: 'nesw-resize' },
                      e: { right: -6, top: '50%', marginTop: -6, cursor: 'ew-resize' },
                      se: { right: -6, bottom: -6, cursor: 'nwse-resize' },
                      s: { left: '50%', bottom: -6, marginLeft: -6, cursor: 'ns-resize' },
                      sw: { left: -6, bottom: -6, cursor: 'nesw-resize' },
                      w: { left: -6, top: '50%', marginTop: -6, cursor: 'ew-resize' },
                    }[dir]
                    return (
                      <span
                        key={dir}
                        data-handle={dir}
                        onMouseDown={startCropResize(dir)}
                        className="absolute h-3 w-3 rounded-sm border border-slate-700 bg-white"
                        style={styles}
                      />
                    )
                  })}
                  {/* Rule-of-thirds */}
                  <div className="pointer-events-none absolute inset-0">
                    <div className="absolute left-1/3 top-0 h-full w-px bg-white/40" />
                    <div className="absolute left-2/3 top-0 h-full w-px bg-white/40" />
                    <div className="absolute top-1/3 left-0 w-full border-t border-white/40" />
                    <div className="absolute top-2/3 left-0 w-full border-t border-white/40" />
                  </div>
                </div>
              </>
            ) : (
              <div className="flex h-full w-full items-center justify-center text-sm text-slate-300">
                Load an image to begin editing
              </div>
            )}
          </div>

          {image && (
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="flex items-center gap-3 text-sm">
                <span className="w-16 font-medium text-slate-700">Zoom</span>
                <input
                  type="range"
                  min="0.1"
                  max="5"
                  step="0.01"
                  value={scale}
                  onChange={(event) => setScale(parseFloat(event.target.value))}
                  className="flex-1"
                />
                <span className="w-12 text-right text-xs text-slate-500">{(scale * 100).toFixed(0)}%</span>
              </label>
              <label className="flex items-center gap-3 text-sm">
                <span className="w-16 font-medium text-slate-700">Rotate</span>
                <input
                  type="range"
                  min="-180"
                  max="180"
                  step="1"
                  value={rotation}
                  onChange={(event) => setRotation(parseFloat(event.target.value))}
                  className="flex-1"
                />
                <span className="w-12 text-right text-xs text-slate-500">{rotation}°</span>
              </label>
              <div className="flex flex-wrap gap-2 sm:col-span-2">
                <Button size="sm" variant="outline" onClick={() => setRotation((rotation - 90 + 360) % 360 - (rotation < 0 ? 360 : 0))}>
                  Rotate −90°
                </Button>
                <Button size="sm" variant="outline" onClick={() => setRotation((rotation + 90) % 360)}>
                  Rotate +90°
                </Button>
                <Button size="sm" variant="outline" onClick={() => { setScale(1); setRotation(0); setTranslate({ x: 0, y: 0 }) }}>
                  Reset transform
                </Button>
                <Button size="sm" variant="outline" onClick={() => onAspectChange(aspectRatio)}>
                  Reset crop
                </Button>
              </div>
            </div>
          )}

          <div className="flex flex-wrap justify-end gap-2 pt-2">
            <Button variant="outline" onClick={onClose} disabled={uploading}>Cancel</Button>
            <Button onClick={handleApply} disabled={!image || uploading}>
              <Upload className="mr-2 h-4 w-4" />
              {uploading ? 'Uploading…' : 'Apply & Upload'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

/**
 * Wraps a map view in a transform-based pan/zoom viewport.
 *
 * - Wheel: pans the image (vertical + horizontal with shift).
 * - Ctrl/Cmd + wheel: zooms toward the cursor.
 * - Touch: single finger drags to pan; two fingers pinch to zoom.
 * - Mouse drag: pans the image.
 *
 * Children is a render-prop receiving the current pixel size to draw at.
 */
function ZoomableMapView({ naturalSize, imageAspect, children, minZoom = 0.1, maxZoom = 5 }) {
  const viewportRef = useRef(null)
  const [viewport, setViewport] = useState({ w: 0, h: 0 })
  const [fitMode, setFitMode] = useState(true)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })

  // Track viewport size.
  useEffect(() => {
    const node = viewportRef.current
    if (!node) return
    const update = () => {
      const rect = node.getBoundingClientRect()
      setViewport({ w: rect.width, h: rect.height })
    }
    update()
    const ro = new ResizeObserver(update)
    ro.observe(node)
    return () => ro.disconnect()
  }, [])

  const fitZoom = (() => {
    if (!naturalSize || viewport.w === 0 || viewport.h === 0) return 1
    return Math.min(viewport.w / naturalSize.w, viewport.h / naturalSize.h)
  })()
  const effectiveZoom = fitMode ? fitZoom : zoom

  const renderSize = naturalSize
    ? { w: Math.max(1, naturalSize.w * effectiveZoom), h: Math.max(1, naturalSize.h * effectiveZoom) }
    : null

  // When in fit mode (or no manual interaction yet), keep the image centered.
  const centeredPan = renderSize
    ? { x: (viewport.w - renderSize.w) / 2, y: (viewport.h - renderSize.h) / 2 }
    : { x: 0, y: 0 }
  const effectivePan = fitMode ? centeredPan : pan

  // Clamp pan so the image cannot be dragged completely out of view.
  const clampPan = (p, size) => {
    if (!size) return p
    const margin = 40
    const minX = Math.min(0, viewport.w - size.w) - margin
    const maxX = margin
    const minY = Math.min(0, viewport.h - size.h) - margin
    const maxY = margin
    // If image smaller than viewport in a dimension, lock to centered.
    const x = size.w <= viewport.w ? (viewport.w - size.w) / 2 : Math.min(maxX, Math.max(minX, p.x))
    const y = size.h <= viewport.h ? (viewport.h - size.h) / 2 : Math.min(maxY, Math.max(minY, p.y))
    return { x, y }
  }

  const applyZoomAt = (newZoomRaw, focusX, focusY) => {
    const newZoom = Math.min(maxZoom, Math.max(minZoom, newZoomRaw))
    if (!naturalSize) {
      setFitMode(false)
      setZoom(newZoom)
      return
    }
    const currentZoom = effectiveZoom
    const currentPan = effectivePan
    // Image-space coordinate under focus point: imgPt = (focus - pan) / currentZoom
    // Want new pan such that newPan = focus - imgPt * newZoom
    const imgX = (focusX - currentPan.x) / currentZoom
    const imgY = (focusY - currentPan.y) / currentZoom
    const newPan = {
      x: focusX - imgX * newZoom,
      y: focusY - imgY * newZoom,
    }
    const nextSize = { w: naturalSize.w * newZoom, h: naturalSize.h * newZoom }
    setFitMode(false)
    setZoom(newZoom)
    setPan(clampPan(newPan, nextSize))
  }

  // Switch from fit mode to manual mode without changing the visible zoom or position.
  // Returns the snapshotted (zoom, pan) the caller should base its delta on.
  const enterManualMode = () => {
    if (!fitMode) return { z: zoom, p: pan }
    const z = effectiveZoom
    const p = effectivePan
    setZoom(z)
    setPan(p)
    setFitMode(false)
    return { z, p }
  }

  // Wheel: ctrl/meta -> zoom at cursor; otherwise pan.
  const onWheel = (event) => {
    event.preventDefault()
    const node = viewportRef.current
    if (!node) return
    const rect = node.getBoundingClientRect()
    const focusX = event.clientX - rect.left
    const focusY = event.clientY - rect.top
    if (event.ctrlKey || event.metaKey) {
      const delta = -event.deltaY
      const factor = Math.exp(delta * 0.0015)
      applyZoomAt(effectiveZoom * factor, focusX, focusY)
    } else {
      // Pan: shift+wheel swaps to horizontal scroll.
      const dx = event.shiftKey ? event.deltaY : event.deltaX
      const dy = event.shiftKey ? 0 : event.deltaY
      const base = enterManualMode()
      setPan(clampPan(
        { x: base.p.x - dx, y: base.p.y - dy },
        renderSize,
      ))
    }
  }

  // Attach wheel listener as non-passive so preventDefault works.
  useEffect(() => {
    const node = viewportRef.current
    if (!node) return
    const handler = (event) => onWheel(event)
    node.addEventListener('wheel', handler, { passive: false })
    return () => node.removeEventListener('wheel', handler)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveZoom, effectivePan.x, effectivePan.y, viewport.w, viewport.h, naturalSize?.w, naturalSize?.h, fitMode])

  // Pointer-based pan + pinch zoom.
  const pointersRef = useRef(new Map())
  const pinchRef = useRef(null)
  const dragStartRef = useRef(null)
  const draggingRef = useRef(false)
  const justDraggedRef = useRef(false)

  const onPointerDown = (event) => {
    const node = viewportRef.current
    if (!node) return
    pointersRef.current.set(event.pointerId, { x: event.clientX, y: event.clientY })
    if (pointersRef.current.size === 1) {
      dragStartRef.current = { id: event.pointerId, x: event.clientX, y: event.clientY }
      draggingRef.current = false
    }
    if (pointersRef.current.size === 2) {
      const pts = Array.from(pointersRef.current.values())
      const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y)
      pinchRef.current = { startDist: dist, startZoom: effectiveZoom, lastMid: midpoint(pts), startPan: effectivePan }
      setFitMode(false)
      // Capture both pointers so pinch tracks even outside viewport.
      try { node.setPointerCapture?.(event.pointerId) } catch { /* ignore */ }
      pointersRef.current.forEach((_, id) => {
        try { node.setPointerCapture?.(id) } catch { /* ignore */ }
      })
      // Pinch counts as drag — suppress click.
      draggingRef.current = true
    }
  }

  const midpoint = (pts) => ({ x: (pts[0].x + pts[1].x) / 2, y: (pts[0].y + pts[1].y) / 2 })

  const onPointerMove = (event) => {
    const ptr = pointersRef.current.get(event.pointerId)
    if (!ptr) return
    const prev = { ...ptr }
    ptr.x = event.clientX
    ptr.y = event.clientY

    if (pointersRef.current.size === 2 && pinchRef.current) {
      const node = viewportRef.current
      if (!node) return
      const rect = node.getBoundingClientRect()
      const pts = Array.from(pointersRef.current.values())
      const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y)
      const rawRatio = dist / Math.max(1, pinchRef.current.startDist)
      // Boost sensitivity: small finger spread → larger zoom change.
      const ratio = rawRatio >= 1
        ? Math.pow(rawRatio, 6.0)
        : 1 / Math.pow(1 / rawRatio, 6.0)
      const newZoom = Math.min(maxZoom, Math.max(minZoom, pinchRef.current.startZoom * ratio))
      const mid = midpoint(pts)
      const focusX = mid.x - rect.left
      const focusY = mid.y - rect.top
      applyZoomAt(newZoom, focusX, focusY)
    } else if (pointersRef.current.size === 1) {
      // Defer turning into a drag until movement crosses a threshold,
      // so a simple click still propagates to the inner map.
      if (!draggingRef.current) {
        const start = dragStartRef.current
        if (!start || start.id !== event.pointerId) return
        if (Math.hypot(event.clientX - start.x, event.clientY - start.y) < 6) return
        draggingRef.current = true
        const node = viewportRef.current
        try { node?.setPointerCapture?.(event.pointerId) } catch { /* ignore */ }
      }
      const dx = ptr.x - prev.x
      const dy = ptr.y - prev.y
      const base = enterManualMode()
      setPan(clampPan(
        { x: base.p.x + dx, y: base.p.y + dy },
        renderSize,
      ))
    }
  }

  const onPointerUp = (event) => {
    pointersRef.current.delete(event.pointerId)
    if (draggingRef.current) {
      // Suppress the imminent click event so panning/pinching never drops a pin.
      justDraggedRef.current = true
    }
    if (pointersRef.current.size === 0) {
      draggingRef.current = false
      dragStartRef.current = null
    }
    if (pointersRef.current.size < 2) pinchRef.current = null
  }

  // Capture-phase click handler: blocks click after a drag/pinch so children
  // don't see it (e.g. the pin-placement crosshair).
  const onClickCapture = (event) => {
    if (justDraggedRef.current) {
      justDraggedRef.current = false
      event.stopPropagation()
      event.preventDefault()
    }
  }

  const setManualZoom = (z) => {
    if (!naturalSize) {
      setFitMode(false)
      setZoom(Math.min(maxZoom, Math.max(minZoom, z)))
      return
    }
    // Zoom centered on viewport.
    applyZoomAt(z, viewport.w / 2, viewport.h / 2)
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
        <span className="font-semibold uppercase tracking-wide">Zoom</span>
        <Button size="sm" variant="outline" onClick={() => setManualZoom(effectiveZoom - 0.1)} disabled={effectiveZoom <= minZoom + 0.001}>−</Button>
        <input
          type="range"
          min={minZoom}
          max={maxZoom}
          step="0.01"
          value={Number.isFinite(effectiveZoom) ? effectiveZoom : 1}
          onChange={(event) => setManualZoom(parseFloat(event.target.value))}
          className="flex-1 min-w-[10rem]"
        />
        <Button size="sm" variant="outline" onClick={() => setManualZoom(effectiveZoom + 0.1)} disabled={effectiveZoom >= maxZoom - 0.001}>+</Button>
        <span className="w-14 text-right tabular-nums">{(effectiveZoom * 100).toFixed(0)}%</span>
        <Button size="sm" variant={fitMode ? 'default' : 'outline'} onClick={() => { setFitMode(true); setPan({ x: 0, y: 0 }) }}>Fit</Button>
        <Button size="sm" variant="outline" onClick={() => setManualZoom(1)}>100%</Button>
      </div>
      <div className="text-[10px] text-slate-500">
        Scroll to pan · Ctrl/Cmd + scroll or pinch to zoom · drag to move
      </div>
      <div
        ref={viewportRef}
        className="relative min-h-0 flex-1 w-full overflow-hidden rounded-md border bg-slate-100"
        style={{ touchAction: 'none', cursor: 'grab' }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onClickCapture={onClickCapture}
      >
        {renderSize ? (
          <div
            style={{
              position: 'absolute',
              left: 0,
              top: 0,
              width: renderSize.w,
              height: renderSize.h,
              transform: `translate(${effectivePan.x}px, ${effectivePan.y}px)`,
              transformOrigin: '0 0',
            }}
          >
            {children(renderSize)}
          </div>
        ) : (
          <div className="absolute inset-0 w-full" style={{ aspectRatio: `${imageAspect || 4 / 3}` }}>
            {children(null)}
          </div>
        )}
      </div>
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

  const [pins, setPins] = useState([])
  const [selectedPinId, setSelectedPinId] = useState(null)
  const [showEnlarge, setShowEnlarge] = useState(false)
  const [showPinPickerEnlarged, setShowPinPickerEnlarged] = useState(false)

  const [leaders, setLeaders] = useState([])
  const [leadersLoading, setLeadersLoading] = useState(false)

  const [backgroundUrl, setBackgroundUrl] = useState(null)
  const [backgroundUploading, setBackgroundUploading] = useState(false)
  const [imageAspect, setImageAspect] = useState(null)
  const [imageNaturalSize, setImageNaturalSize] = useState(null)
  const [showBackgroundEditor, setShowBackgroundEditor] = useState(false)
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
  const [newPinName, setNewPinName] = useState(initialDraft.newPinName || '')
  const [newPinPoint, setNewPinPoint] = useState(initialDraft.newPinPoint || null)

  const [imageItems, setImageItems] = useState([]) // [{id, file, name, status, heicProgress?, previewUrl, error?}]
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
        setImageAspect(null)
      }
    } catch {
      setBackgroundUrl(null)
      setImageAspect(null)
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
    if (!backgroundUrl) {
      setImageAspect(null)
      setImageNaturalSize(null)
      return
    }
    const img = new Image()
    img.onload = () => {
      if (img.naturalWidth > 0 && img.naturalHeight > 0) {
        setImageAspect(img.naturalWidth / img.naturalHeight)
        setImageNaturalSize({ w: img.naturalWidth, h: img.naturalHeight })
      }
    }
    img.src = backgroundUrl
  }, [backgroundUrl])

  useEffect(() => {
    if (!isSubmissionPage) return
    if (typeof window === 'undefined') return
    try {
      const draft = { email, authMethod, title, text, displayName, verificationCode, verificationSent, pinChoice, newPinName, newPinPoint }
      window.localStorage.setItem(SUBMISSION_DRAFT_KEY, JSON.stringify(draft))
    } catch {
      // localStorage may be unavailable - non-fatal
    }
  }, [isSubmissionPage, email, authMethod, title, text, displayName, verificationCode, verificationSent, pinChoice, newPinName, newPinPoint])

  useEffect(() => {
    return () => {
      // Revoke any preview URLs when component unmounts.
      setImageItems((prev) => {
        prev.forEach((it) => { if (it.previewUrl) URL.revokeObjectURL(it.previewUrl) })
        return prev
      })
    }
  }, [])

  useEffect(() => {
    if (!isSubmissionPage) {
      return
    }
    const handlePaste = (event) => {
      const items = event.clipboardData?.items
      if (!items || items.length === 0) {
        return
      }
      let pasted = false
      for (const item of items) {
        if (item.kind === 'file' && item.type.startsWith('image/')) {
          const file = item.getAsFile()
          if (file) {
            pasted = true
            enqueueFile(file)
          }
        }
      }
      if (pasted) event.preventDefault()
    }
    window.addEventListener('paste', handlePaste)
    return () => window.removeEventListener('paste', handlePaste)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSubmissionPage])

  // Page-wide drag-and-drop image upload while on the submission page.
  useEffect(() => {
    if (!isSubmissionPage) return
    let dragDepth = 0
    const hasFiles = (event) => {
      const types = event.dataTransfer?.types
      if (!types) return false
      for (let i = 0; i < types.length; i += 1) {
        if (types[i] === 'Files') return true
      }
      return false
    }
    const onDragEnter = (event) => {
      if (!hasFiles(event)) return
      event.preventDefault()
      dragDepth += 1
      setIsDraggingImage(true)
    }
    const onDragOver = (event) => {
      if (!hasFiles(event)) return
      event.preventDefault()
      if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy'
    }
    const onDragLeave = (event) => {
      if (!hasFiles(event)) return
      dragDepth = Math.max(0, dragDepth - 1)
      if (dragDepth === 0) setIsDraggingImage(false)
    }
    const onDrop = (event) => {
      if (!hasFiles(event)) return
      event.preventDefault()
      dragDepth = 0
      setIsDraggingImage(false)
      const files = Array.from(event.dataTransfer?.files || [])
      files.forEach((file) => { enqueueFile(file) })
    }
    window.addEventListener('dragenter', onDragEnter)
    window.addEventListener('dragover', onDragOver)
    window.addEventListener('dragleave', onDragLeave)
    window.addEventListener('drop', onDrop)
    return () => {
      window.removeEventListener('dragenter', onDragEnter)
      window.removeEventListener('dragover', onDragOver)
      window.removeEventListener('dragleave', onDragLeave)
      window.removeEventListener('drop', onDrop)
    }
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
    clearImageItems()
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

  const enqueueFile = async (file) => {
    if (!file) return
    const heic = isHeicFile(file)
    if (!MAP_ALLOWED_IMAGE_TYPES.has(file.type) && !heic) {
      showMessage('[MAP_IMAGE_TYPE_UNSUPPORTED_CLIENT] Image must be a JPG, PNG, WebP, GIF, or HEIC file', 'error')
      return
    }
    if (file.size > MAP_MAX_IMAGE_BYTES) {
      showMessage('[MAP_IMAGE_TOO_LARGE_CLIENT] Image must be 50 MB or smaller', 'error')
      return
    }
    const id = (typeof crypto !== 'undefined' && crypto.randomUUID) ? crypto.randomUUID() : `img-${Date.now()}-${Math.random().toString(36).slice(2)}`
    const initialPreview = heic ? '' : URL.createObjectURL(file)
    setImageItems((prev) => [...prev, {
      id,
      file: heic ? null : file,
      name: file.name,
      status: heic ? 'processing' : 'ready',
      heicProgress: heic ? { phase: 'uploading', percent: 0 } : null,
      previewUrl: initialPreview,
    }])
    if (!heic) return
    let working
    try {
      working = await convertHeicViaServer(file, (p) => {
        setImageItems((prev) => prev.map((it) => it.id === id ? { ...it, heicProgress: p } : it))
      })
    } catch (err) {
      console.error('Server HEIC conversion failed', err)
      showMessage(`[MAP_IMAGE_HEIC_FAILED] Could not decode HEIC image (${file.name})`, 'error')
      setImageItems((prev) => prev.filter((it) => it.id !== id))
      return
    }
    const previewUrl = URL.createObjectURL(working)
    setImageItems((prev) => prev.map((it) => it.id === id
      ? { ...it, file: working, name: working.name, status: 'ready', heicProgress: null, previewUrl }
      : it))
  }

  const handleImageChange = async (file) => {
    await enqueueFile(file)
  }

  const handleRemoveImageById = (id) => {
    setImageItems((prev) => {
      const target = prev.find((it) => it.id === id)
      if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl)
      return prev.filter((it) => it.id !== id)
    })
  }

  const clearImageItems = () => {
    setImageItems((prev) => {
      prev.forEach((it) => { if (it.previewUrl) URL.revokeObjectURL(it.previewUrl) })
      return []
    })
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleImageDrop = (event) => {
    event.preventDefault()
    setIsDraggingImage(false)
    const files = Array.from(event.dataTransfer?.files || [])
    files.forEach((file) => { enqueueFile(file) })
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

    if (imageItems.some((it) => it.status !== 'ready')) {
      showMessage('[MAP_IMAGE_PROCESSING_CLIENT] Wait for images to finish processing before submitting', 'error')
      return
    }
    for (const it of imageItems) {
      if (!it.file) continue
      if (!MAP_ALLOWED_IMAGE_TYPES.has(it.file.type)) {
        showMessage(`[MAP_IMAGE_TYPE_UNSUPPORTED_CLIENT] ${it.name} is not a supported image type`, 'error')
        return
      }
      if (it.file.size > MAP_MAX_IMAGE_BYTES) {
        showMessage(`[MAP_IMAGE_TOO_LARGE_CLIENT] ${it.name} is larger than 50 MB`, 'error')
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
      if (imageItems.length > 0) {
        formData.append('image', imageItems[0].file)
        for (let i = 1; i < imageItems.length; i += 1) {
          formData.append('images', imageItems[i].file)
        }
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

  const rejectSubmission = async (submissionId, reason = '') => {
    setActionLoading(true)
    try {
      const response = await fetch(`${API_BASE}/map/submissions/${submissionId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: reason || '' })
      })
      const result = await readApiResponse(response)
      if (result.ok) {
        const emailStatus = result.data?.notification_email
        if (reason && emailStatus && emailStatus.success === false) {
          showMessage('Submission rejected, but the notification email failed to send', 'warning')
        } else if (reason) {
          showMessage('Submission rejected and email sent to submitter', 'success')
        } else {
          showMessage('Map submission rejected', 'success')
        }
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

  const deleteSubmission = async (submissionId, reason = '') => {
    if (!reason && typeof window !== 'undefined' && !window.confirm('Permanently delete this submission?')) {
      return
    }
    setActionLoading(true)
    try {
      const response = await fetch(`${API_BASE}/map/submissions/${submissionId}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: reason || '' }),
      })
      const result = await readApiResponse(response)
      if (result.ok) {
        const emailStatus = result.data?.notification_email
        if (reason && emailStatus && emailStatus.success === false) {
          showMessage('Submission deleted, but the notification email failed to send', 'warning')
        } else if (reason) {
          showMessage('Submission deleted and email sent to submitter', 'success')
        } else {
          showMessage('Submission deleted', 'success')
        }
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

  const handleBackgroundUpload = async (fileOrBlob, filename = null) => {
    if (!fileOrBlob) return
    const type = fileOrBlob.type || ''
    if (type && !MAP_ALLOWED_IMAGE_TYPES.has(type)) {
      showMessage('[MAP_BACKGROUND_TYPE_UNSUPPORTED_CLIENT] Image must be a JPG, PNG, WebP, or GIF file', 'error')
      return
    }
    if (fileOrBlob.size > MAP_MAX_IMAGE_BYTES) {
      showMessage('[MAP_BACKGROUND_TOO_LARGE_CLIENT] Image must be 50 MB or smaller', 'error')
      return
    }

    setBackgroundUploading(true)
    try {
      const formData = new FormData()
      const name = filename || fileOrBlob.name || 'map-background.png'
      formData.append('image', fileOrBlob, name)
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
      {isSubmissionPage && isDraggingImage && (
        <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center bg-teal-900/40 backdrop-blur-sm">
          <div className="rounded-xl border-2 border-dashed border-white bg-white/90 px-8 py-6 text-center shadow-2xl">
            <Upload className="mx-auto mb-2 h-10 w-10 text-teal-700" />
            <div className="text-lg font-semibold text-slate-900">Drop image to upload</div>
            <div className="text-xs text-slate-500">JPG, PNG, WebP, GIF, or HEIC up to 50 MB</div>
          </div>
        </div>
      )}
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
                <Button
                  onClick={() => setShowBackgroundEditor(true)}
                  size="sm"
                  variant="outline"
                  disabled={backgroundUploading}
                >
                  <ImageIcon className="mr-2 h-4 w-4" />
                  {backgroundUploading ? 'Uploading…' : 'Edit Map Background'}
                </Button>
              )}
            </div>
          </div>
        </section>
      )}

      <main className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <section className="grid gap-6 lg:grid-cols-[minmax(0,0.55fr)_minmax(28rem,1.45fr)]">
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
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-md border bg-slate-50 p-3">
                <div className="text-xs font-semibold uppercase text-slate-500">Pins</div>
                <div className="mt-1 text-lg font-bold">{pins.length}</div>
              </div>
              <div className="rounded-md border bg-slate-50 p-3">
                <div className="text-xs font-semibold uppercase text-slate-500">Approved</div>
                <div className="mt-1 text-lg font-bold">{approvedSubmissions.length}</div>
              </div>
            </div>
            <div className="flex flex-wrap items-baseline gap-2 rounded-md border bg-slate-50 px-3 py-2">
              <span className="text-xs font-semibold uppercase text-slate-500">Username</span>
              <span className="break-all text-base font-bold leading-snug text-slate-800">@{user?.username || 'guest'}</span>
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
            imageAspect={imageAspect}
            fillContainer
            className="h-full min-h-[20rem]"
          />
        </section>

        {selectedPinId && isAdmin && (
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
                    <div className="mt-2 space-y-2">
                      <select
                        value={pins.find((pin) => pin.id === pinChoice) ? pinChoice : ''}
                        onChange={(event) => setPinChoice(event.target.value || 'others')}
                        className="w-full rounded-md border bg-white px-3 py-2 text-sm"
                      >
                        <option value="">Select a pin…</option>
                        {pins.map((pin) => (
                          <option key={pin.id} value={pin.id}>
                            {pin.name}
                          </option>
                        ))}
                      </select>
                      <p className="text-xs text-slate-500">Or click a pin on the map below.</p>
                      <EcologicalMapGraphic
                        pins={pins}
                        submissionsByPin={submissionsByPin}
                        backgroundUrl={backgroundUrl}
                        imageAspect={imageAspect}
                        selectedPinId={pins.find((pin) => pin.id === pinChoice) ? pinChoice : null}
                        onSelectPin={(id) => {
                          if (id && id !== 'others') setPinChoice(id)
                        }}
                      />
                      {pins.find((pin) => pin.id === pinChoice) && (
                        <div className="text-xs text-slate-600">
                          <MapPinIcon className="mr-1 inline h-3.5 w-3.5 text-teal-700" />
                          Selected: <span className="font-medium">{pins.find((pin) => pin.id === pinChoice)?.name}</span>
                        </div>
                      )}
                    </div>
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
                        imageAspect={imageAspect}
                        pendingPoint={newPinPoint}
                        onMapClick={handleSubmissionMapClick}
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
                      {imageItems.length > 0
                        ? `${imageItems.length} file${imageItems.length === 1 ? '' : 's'} selected — drop more to add`
                        : 'Choose images, drag & drop, or paste (Ctrl/Cmd+V)'}
                    </span>
                    <span className="text-xs text-slate-500">JPG, PNG, WebP, GIF, or HEIC up to 50 MB each</span>
                    <input
                      ref={fileInputRef}
                      id="map-image"
                      type="file"
                      multiple
                      accept="image/jpeg,image/png,image/webp,image/gif,image/heic,image/heif,.heic,.heif"
                      className="sr-only"
                      onChange={(event) => {
                        const files = Array.from(event.target.files || [])
                        files.forEach((file) => { enqueueFile(file) })
                        if (fileInputRef.current) fileInputRef.current.value = ''
                      }}
                    />
                  </label>
                  {imageItems.length > 0 && (
                    <div className="grid gap-3 sm:grid-cols-2">
                      {imageItems.map((it) => (
                        <div key={it.id} className="relative rounded-md border bg-white p-2">
                          <div className="relative h-32 w-full overflow-hidden rounded bg-slate-100">
                            {it.previewUrl ? (
                              <img src={it.previewUrl} alt={it.name} className="h-full w-full object-cover" />
                            ) : (
                              <div className="flex h-full w-full items-center justify-center text-xs text-slate-500">
                                Processing…
                              </div>
                            )}
                            <button
                              type="button"
                              onClick={() => handleRemoveImageById(it.id)}
                              aria-label={`Remove ${it.name}`}
                              className="absolute right-1 top-1 inline-flex h-7 w-7 items-center justify-center rounded-full bg-black/60 text-white shadow hover:bg-black/80"
                            >
                              <X className="h-3.5 w-3.5" />
                            </button>
                          </div>
                          <div className="mt-2 truncate text-xs font-medium text-slate-700" title={it.name}>{it.name}</div>
                          {it.heicProgress && (
                            <div className="mt-1">
                              <div className="mb-1 flex items-center justify-between text-[11px] text-amber-900">
                                <span>{it.heicProgress.phase === 'uploading' ? 'Uploading HEIC…'
                                  : it.heicProgress.phase === 'decoding' ? 'Decoding HEIC…'
                                  : 'Finishing…'}</span>
                                <span className="tabular-nums">{Math.round(it.heicProgress.percent)}%</span>
                              </div>
                              <div className="h-1.5 w-full overflow-hidden rounded bg-amber-200">
                                <div
                                  className="h-full bg-amber-600 transition-all"
                                  style={{ width: `${Math.max(2, Math.min(100, it.heicProgress.percent))}%` }}
                                />
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
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
                  {imageItems.length > 0 ? (
                    <div className="space-y-2">
                      <div className="grid gap-2 sm:grid-cols-2">
                        {imageItems.map((it) => (
                          it.previewUrl ? (
                            <img key={it.id} src={it.previewUrl} alt={it.name} className="h-32 w-full rounded-md border object-cover" />
                          ) : (
                            <div key={it.id} className="flex h-32 items-center justify-center rounded-md border bg-slate-100 text-xs text-slate-500">Processing…</div>
                          )
                        ))}
                      </div>
                      <div className="text-xs text-slate-500">{imageItems.length} image{imageItems.length === 1 ? '' : 's'} attached</div>
                    </div>
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
          isAdmin ? (
            <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(22rem,0.55fr)]">
              <div className="space-y-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h2 className="text-2xl font-bold text-slate-950">All approved submissions</h2>
                    <p className="text-sm text-slate-500">Visible to admins and super admins.</p>
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
          ) : (
            <section className="flex justify-center">
              <LeaderboardCard leaders={leaders} loading={leadersLoading} onRefresh={loadLeaders} />
            </section>
          )
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

      <MapBackgroundEditor
        open={showBackgroundEditor}
        onClose={() => setShowBackgroundEditor(false)}
        uploading={backgroundUploading}
        onUpload={async (blob, name) => {
          await handleBackgroundUpload(blob, name)
          setShowBackgroundEditor(false)
        }}
      />

      <Dialog open={showEnlarge} onOpenChange={setShowEnlarge}>
        <DialogContent className="flex w-full sm:max-w-[95vw] h-[95vh] max-h-[95vh] flex-col overflow-hidden">
          <DialogHeader className="shrink-0">
            <DialogTitle>Ecological Map (enlarged)</DialogTitle>
            <DialogDescription>
              Scroll to pan, Ctrl/Cmd + scroll or pinch to zoom, drag to move.
            </DialogDescription>
          </DialogHeader>
          <ZoomableMapView naturalSize={imageNaturalSize} imageAspect={imageAspect}>
            {(size) => (
              <EcologicalMapGraphic
                pins={pins}
                submissionsByPin={submissionsByPin}
                selectedPinId={selectedPinId}
                onSelectPin={(id) => { setSelectedPinId(id); setShowEnlarge(false) }}
                backgroundUrl={backgroundUrl}
                imageAspect={imageAspect}
                naturalSize={size}
              />
            )}
          </ZoomableMapView>
        </DialogContent>
      </Dialog>

      <Dialog open={showPinPickerEnlarged} onOpenChange={setShowPinPickerEnlarged}>
        <DialogContent className="flex w-full sm:max-w-[95vw] h-[95vh] max-h-[95vh] flex-col overflow-hidden">
          <DialogHeader className="shrink-0">
            <DialogTitle>Place your pin (enlarged)</DialogTitle>
            <DialogDescription>
              Click to drop your pin. Scroll to pan, Ctrl/Cmd + scroll or pinch to zoom.
            </DialogDescription>
          </DialogHeader>
          <ZoomableMapView naturalSize={imageNaturalSize} imageAspect={imageAspect}>
            {(size) => (
              <EcologicalMapGraphic
                pins={pins}
                submissionsByPin={submissionsByPin}
                backgroundUrl={backgroundUrl}
                imageAspect={imageAspect}
                pendingPoint={newPinPoint}
                onMapClick={handleSubmissionMapClick}
                naturalSize={size}
              />
            )}
          </ZoomableMapView>
          <div className="flex shrink-0 flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
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
