import React, { useState, useEffect, useMemo } from 'react'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Alert, AlertDescription } from '@/components/ui/alert.jsx'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog.jsx'
import { Switch } from '@/components/ui/switch.jsx'
import { SearchableNameInput } from '@/components/SearchableNameInput.jsx'
import Modal from '@/components/Modal.jsx'
import { createPortal } from 'react-dom'
import { Upload, Scan, Download, FileText, Plus, Users, BarChart3, LogOut, Shield, Settings, Trash2, UserPlus, AlertCircle, XCircle, Trophy, Wand2, CheckCircle, RefreshCcw, ShieldCheck, Ban, Clock, History, ListOrdered, ChevronDown, ChevronUp, Globe2, Building2, School, Search, UserSearch, CircleSlash2 } from 'lucide-react'
import './App.css'

const API_BASE = '/api'
const ADMIN_ROLES = ['admin', 'superadmin', 'school_super_admin', 'global_admin']
const SUPERADMIN_ROLES = ['superadmin', 'school_super_admin', 'global_admin']
const SCHOOL_FEATURES = [
  { key: 'student_directory', label: 'Student Directory Search' },
  { key: 'faculty_module', label: 'Faculty Management Module' },
  { key: 'ticket_draws', label: 'Ticket Draw Center' }
]

const createDefaultSchoolSignupForm = () => ({
  schoolName: '',
  schoolAddress: '',
  publicContact: '',
  inviteCode: '',
  ownerName: '',
  ownerUsername: '',
  ownerPassword: '',
  featureToggles: SCHOOL_FEATURES.reduce((acc, feature) => {
    acc[feature.key] = true
    return acc
  }, {}),
  guestAccessEnabled: true
})

const normalizeName = (value) => (value ?? '').toString().trim()

const makeStudentKey = (preferred, last, studentId = '') => {
  const studentIdNorm = normalizeName(studentId).toLowerCase()
  if (studentIdNorm) {
    return `id:${studentIdNorm}`
  }
  const preferredNorm = normalizeName(preferred).toLowerCase()
  const lastNorm = normalizeName(last).toLowerCase()
  if (!preferredNorm && !lastNorm) {
    return null
  }
  return `${preferredNorm}|${lastNorm}`
}

const sanitizeSelection = (entry) => {
  if (!entry) return null
  const preferred = normalizeName(entry.preferred ?? entry.preferred_name)
  const last = normalizeName(entry.last ?? entry.last_name)
  const studentId = normalizeName(entry.student_id)
  const existingKey = entry.key ? String(entry.key).toLowerCase() : null
  const key = existingKey || makeStudentKey(preferred, last, studentId)
  return {
    ...entry,
    preferred,
    preferred_name: entry.preferred_name ?? preferred,
    last,
    last_name: entry.last_name ?? last,
    student_id: studentId,
    key
  }
}

function App() {
  // Authentication state
  const [user, setUser] = useState(null)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [loginUsername, setLoginUsername] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [showLoginDialog, setShowLoginDialog] = useState(false)
  const [showSignupDialog, setShowSignupDialog] = useState(false)
  const [signupUsername, setSignupUsername] = useState('')
  const [signupPassword, setSignupPassword] = useState('')
  const [signupName, setSignupName] = useState('')
  const [signupInviteCode, setSignupInviteCode] = useState('')
  
  // Session state
  const [sessionId, setSessionId] = useState(null)
  const [sessionName, setSessionName] = useState('')
  const [customSessionName, setCustomSessionName] = useState('')
  const [sessions, setSessions] = useState([])
  const [csvData, setCsvData] = useState(null)
  const [inputValue, setInputValue] = useState('')
  const [scanHistory, setScanHistory] = useState([])
  const [sessionStats, setSessionStats] = useState({
    clean_count: 0,
    dirty_count: 0,
    red_count: 0,
    combined_dirty_count: 0,
    faculty_clean_count: 0,
    total_recorded: 0,
    clean_percentage: 0,
    dirty_percentage: 0,
    is_discarded: false,
    draw_info: null
  })
  const [isLoading, setIsLoading] = useState(false)
  
  // Dialog states
  const [showNewSessionDialog, setShowNewSessionDialog] = useState(false)
  const [showSessionsDialog, setShowSessionsDialog] = useState(false)
  const [showDashboard, setShowDashboard] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [sessionToDelete, setSessionToDelete] = useState(null)
  const [showAdminPanel, setShowAdminPanel] = useState(false)
  const [showAccountManagement, setShowAccountManagement] = useState(false)
  const [showDeleteRequests, setShowDeleteRequests] = useState(false)
  const [showUserDeleteConfirm, setShowUserDeleteConfirm] = useState(false)
  const [userToDelete, setUserToDelete] = useState(null)
  
  // Account management state
  const [allUsers, setAllUsers] = useState([])
  const [deleteRequests, setDeleteRequests] = useState([])
  
  // Popup states for each category
  const [showCleanDialog, setShowCleanDialog] = useState(false)
  const [showDirtyDialog, setShowDirtyDialog] = useState(false)
  const [showRedDialog, setShowRedDialog] = useState(false)
  const [showFacultyDialog, setShowFacultyDialog] = useState(false)
  const [popupInputValue, setPopupInputValue] = useState('')
  
  // Admin panel state
  const [adminUsers, setAdminUsers] = useState([])
  const [adminSessions, setAdminSessions] = useState([])
  
  // CSV preview state
  const [showCsvPreview, setShowCsvPreview] = useState(false)
  const [csvPreviewData, setCsvPreviewData] = useState(null)
  const [csvPreviewPage, setCsvPreviewPage] = useState(1)
  const [csvPreviewLoading, setCsvPreviewLoading] = useState(false)

  // Student names for dropdown
  const [studentNames, setStudentNames] = useState([])

  // Teacher names for dropdown
  const [teacherNames, setTeacherNames] = useState([])
  const [showTeacherPreview, setShowTeacherPreview] = useState(false)
  const [teacherPreviewData, setTeacherPreviewData] = useState(null)
  const [teacherPreviewPage, setTeacherPreviewPage] = useState(1)
  const [teacherPreviewLoading, setTeacherPreviewLoading] = useState(false)
  const [popupSelectedEntry, setPopupSelectedEntry] = useState(null)

  // Draw center state
  const [drawSummary, setDrawSummary] = useState(null)
  const [drawSummaryLoading, setDrawSummaryLoading] = useState(false)
  const [overrideInput, setOverrideInput] = useState('')
  const [overrideCandidate, setOverrideCandidate] = useState(null)
  const [selectedCandidateKey, setSelectedCandidateKey] = useState(null)
  const [drawActionLoading, setDrawActionLoading] = useState(false)
  const [discardLoading, setDiscardLoading] = useState(false)
  const [isDrawCenterCollapsed, setIsDrawCenterCollapsed] = useState(false)

  // Notification and modal states
  const [notification, setNotification] = useState(null)
  const [modal, setModal] = useState(null)
  const [inviteCode, setInviteCode] = useState('')
  const [globalAdminContext, setGlobalAdminContext] = useState(null)
  const [showSchoolSignupDialog, setShowSchoolSignupDialog] = useState(false)
  const [schoolSignupForm, setSchoolSignupForm] = useState(() => createDefaultSchoolSignupForm())
  const [isSubmittingSchoolSignup, setIsSubmittingSchoolSignup] = useState(false)
  const [directorySearchQuery, setDirectorySearchQuery] = useState('')
  const [directorySearchResults, setDirectorySearchResults] = useState([])
  const [directorySearchLoading, setDirectorySearchLoading] = useState(false)

  const isSessionDiscarded = drawSummary?.is_discarded ?? sessionStats.is_discarded
  const currentDrawInfo = drawSummary?.draw_info ?? sessionStats.draw_info
  const isGlobalAdmin = user?.role === 'global_admin'
  const isSuperAdmin = SUPERADMIN_ROLES.includes(user?.role)
  const isAdmin = ADMIN_ROLES.includes(user?.role)
  const canAccessTenantData = !isGlobalAdmin || Boolean(globalAdminContext?.impersonating)
  const canUseTenantAdminFeatures = canAccessTenantData && isAdmin
  const canUseTenantSuperAdminFeatures = canAccessTenantData && isSuperAdmin
  const canManageDraw = canUseTenantAdminFeatures
  const canOverrideWinner = canUseTenantSuperAdminFeatures
  const studentRecordCount = (sessionStats.clean_count ?? 0) + (sessionStats.red_count ?? 0)
  const hasStudentRecords = studentRecordCount > 0
  const showExportCard = user?.role !== 'guest'

  const selectedCandidate = useMemo(() => {
    if (!drawSummary?.candidates?.length) {
      return null
    }
    return drawSummary.candidates.find(candidate => candidate.key === selectedCandidateKey) ?? null
  }, [drawSummary, selectedCandidateKey])

  const overrideOptions = useMemo(() => {
    const combined = new Map()
    if (drawSummary?.candidates?.length) {
      for (const candidate of drawSummary.candidates) {
        combined.set(candidate.key, { ...candidate })
      }
    }
    for (const entry of studentNames) {
      const key = entry.key || makeStudentKey(entry.preferred || entry.preferred_name, entry.last || entry.last_name, entry.student_id)
      if (!key) continue
      if (combined.has(key)) {
        const existing = combined.get(key)
        combined.set(key, {
          ...entry,
          ...existing,
          key,
          display_name: existing.display_name || entry.display_name || `${normalizeName(entry.preferred || entry.preferred_name)} ${normalizeName(entry.last || entry.last_name)}`.trim(),
          preferred_name: existing.preferred_name || entry.preferred || entry.preferred_name || '',
          last_name: existing.last_name || entry.last || entry.last_name || '',
          student_id: existing.student_id || entry.student_id || ''
        })
      } else {
        combined.set(key, {
          ...entry,
          key,
          display_name: entry.display_name || `${normalizeName(entry.preferred || entry.preferred_name)} ${normalizeName(entry.last || entry.last_name)}`.trim(),
          preferred_name: entry.preferred || entry.preferred_name || '',
          last_name: entry.last || entry.last_name || '',
          student_id: entry.student_id || ''
        })
      }
    }
    return Array.from(combined.values())
  }, [drawSummary, studentNames])

  const sessionDashboardStats = useMemo(() => {
    const studentCleanCount = Number(sessionStats.clean_count ?? 0)
    const dirtyCount = Number(sessionStats.dirty_count ?? 0)
    const redCount = Number(sessionStats.red_count ?? 0)
  const combinedDirty = Number(sessionStats.combined_dirty_count ?? (dirtyCount + redCount))
    const facultyCount = Number(sessionStats.faculty_clean_count ?? 0)
    const cleanCount = studentCleanCount + facultyCount
    const totalRecorded = studentCleanCount + dirtyCount + redCount + facultyCount
    const cleanPercentage = totalRecorded ? (cleanCount / totalRecorded) * 100 : 0
    const dirtyPercentage = totalRecorded ? (combinedDirty / totalRecorded) * 100 : 0

    return {
      cleanCount,
      dirtyCount,
      redCount,
      combinedDirty,
      facultyCount,
      totalRecorded,
      cleanPercentage,
      dirtyPercentage
    }
  }, [sessionStats])

  const dashboardWinner = useMemo(() => {
    const drawInfo = drawSummary?.draw_info ?? sessionStats.draw_info ?? null
    if (!drawInfo) {
      return {
        winner: null,
        finalized: false,
        override: false,
        timestamp: null,
        tickets: null,
        probability: null
      }
    }

    return {
      winner: drawInfo.winner ?? null,
      finalized: Boolean(drawInfo.finalized),
      override: Boolean(drawInfo.override),
      timestamp: drawInfo.winner_timestamp ? new Date(drawInfo.winner_timestamp) : null,
      tickets: drawInfo.tickets_at_selection ?? null,
      probability: drawInfo.probability_at_selection ?? null
    }
  }, [drawSummary, sessionStats])

  // Check authentication status on load
  useEffect(() => {
    checkAuthStatus()
  }, [])

  const checkAuthStatus = async (options = {}) => {
    try {
      const response = await fetch(`${API_BASE}/auth/status`)
      if (!response.ok) {
        setIsAuthenticated(false)
        setUser(null)
        setGlobalAdminContext(null)
        return null
      }
      const data = await response.json()
      if (data.authenticated) {
        const context = data.global_admin || null
        setUser(data.user)
        setIsAuthenticated(true)
        setGlobalAdminContext(context)
        if (!options.skipSessionInit) {
          await initializeSession({ authUser: data.user, globalAdminContext: context })
        }
      } else {
        setIsAuthenticated(false)
        setUser(null)
        setGlobalAdminContext(null)
      }
      return data
    } catch (error) {
      console.error('Auth check failed:', error)
      return null
    }
  }

  const login = async () => {
    if (!loginUsername.trim() || !loginPassword.trim()) {
      showMessage('Please enter both username and password', 'error')
      return
    }

    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: loginUsername.trim(),
          password: loginPassword.trim()
        })
      })

      const data = await response.json()
      if (response.ok) {
        setLoginUsername('')
        setLoginPassword('')
        showMessage(`Welcome, ${data.user.name}!`, 'success')
        await checkAuthStatus()
      } else {
        showMessage(data.error || 'Login failed', 'error')
      }
    } catch (error) {
      showMessage('Login failed. Please try again.', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const guestLogin = async () => {
    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/auth/guest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })

      const data = await response.json()
      if (response.ok) {
        showMessage('Welcome, Guest! You can view sessions but cannot create or modify them.', 'info')
        await checkAuthStatus()
      } else {
        showMessage(data.error || 'Guest login failed', 'error')
      }
    } catch (error) {
      showMessage('Guest login failed. Please try again.', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const signup = async () => {
    if (!signupUsername.trim() || !signupPassword.trim() || !signupName.trim() || !signupInviteCode.trim()) {
      showMessage('Please fill in all fields', 'error')
      return
    }

    if (signupUsername.length < 3) {
      showMessage('Username must be at least 3 characters long', 'error')
      return
    }

    if (signupPassword.length < 6) {
      showMessage('Password must be at least 6 characters long', 'error')
      return
    }

    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: signupUsername.trim(),
          password: signupPassword.trim(),
          name: signupName.trim(),
          invite_code: signupInviteCode.trim()
        })
      })

      const data = await response.json()
      if (response.ok) {
        showMessage('Account created successfully! Please login.', 'success')
        setSignupUsername('')
        setSignupPassword('')
        setSignupName('')
        setSignupInviteCode('')
        setShowSignupDialog(false)
      } else {
        showMessage(data.error || 'Signup failed', 'error')
      }
    } catch (error) {
      showMessage('Signup failed. Please try again.', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const logout = async () => {
    try {
      await fetch(`${API_BASE}/auth/logout`, { method: 'POST' })
      setUser(null)
      setIsAuthenticated(false)
      setSessionId(null)
      setSessionName('')
      setSessions([])
      setCsvData(null)
      setInputValue('')
      setScanHistory([])
      setSessionStats({
        clean_count: 0,
        dirty_count: 0,
        red_count: 0,
        faculty_clean_count: 0,
        combined_dirty_count: 0,
        total_recorded: 0,
        clean_percentage: 0,
        dirty_percentage: 0,
        is_discarded: false,
        draw_info: null
      })
      setInviteCode('')
      setModal(null)
      setNotification(null)
      setOverrideInput('')
      setOverrideCandidate(null)
      setSelectedCandidateKey(null)
      setGlobalAdminContext(null)
      setShowSchoolSignupDialog(false)
      setIsSubmittingSchoolSignup(false)
      setSchoolSignupForm(createDefaultSchoolSignupForm())
      setDirectorySearchQuery('')
      setDirectorySearchResults([])
      setDirectorySearchLoading(false)
      showMessage('Logged out successfully', 'info')
    } catch (error) {
      showMessage('Logout failed', 'error')
    }
  }

  const initializeSession = async (options = {}) => {
    const authUser = options.authUser ?? user
    const context = options.globalAdminContext ?? globalAdminContext
    if (authUser?.role === 'global_admin' && !Boolean(context?.impersonating)) {
      setSessionId(null)
      setSessionName('')
      setSessions([])
      setCsvData(null)
      setInputValue('')
      setScanHistory([])
      setSessionStats({
        clean_count: 0,
        dirty_count: 0,
        red_count: 0,
        combined_dirty_count: 0,
        faculty_clean_count: 0,
        total_recorded: 0,
        clean_percentage: 0,
        dirty_percentage: 0,
        is_discarded: false,
        draw_info: null
      })
      setDrawSummary(null)
      setStudentNames([])
      setTeacherNames([])
      setOverrideInput('')
      setOverrideCandidate(null)
      setSelectedCandidateKey(null)
      return
    }

    try {
      const response = await fetch(`${API_BASE}/session/status`)
      if (response.ok) {
        const data = await response.json()
        setSessionId(data.session_id)
        setSessionName(data.session_name)
        setSessionStats({
          clean_count: data.clean_count,
          dirty_count: data.dirty_count,
          red_count: data.red_count,
          combined_dirty_count: data.combined_dirty_count,
          faculty_clean_count: data.faculty_clean_count,
          total_recorded: data.total_recorded,
          clean_percentage: data.clean_percentage,
          dirty_percentage: data.dirty_percentage,
          is_discarded: data.is_discarded ?? false,
          draw_info: data.draw_info ?? null
        })
        // Load scan history for the session
        await loadScanHistory()
        // Load student names for dropdown
        await loadStudentNames()
        // Load teacher names for dropdown
        await loadTeacherNames()
        await loadDrawSummary({ silent: true, sessionIdOverride: data.session_id, sessionNameOverride: data.session_name, isDiscarded: data.is_discarded })
      } else {
        // No active session - try to join an existing one automatically
        const sessions = await loadSessions()
        if (sessions.length > 0) {
          await switchSession(sessions[0].session_id)
        } else {
          setSessionId(null)
          setSessionName('')
          setSessionStats({
            clean_count: 0,
            dirty_count: 0,
            red_count: 0,
            faculty_clean_count: 0,
            combined_dirty_count: 0,
            total_recorded: 0,
            clean_percentage: 0,
            dirty_percentage: 0,
            is_discarded: false,
            draw_info: null
          })
          setScanHistory([])
          setDrawSummary(null)
          setOverrideInput('')
          setOverrideCandidate(null)
          setSelectedCandidateKey(null)
          // Still try to load student names even without a session
          await loadStudentNames()
          // Still try to load teacher names even without a session
          await loadTeacherNames()
        }
      }
    } catch (error) {
      console.error('Session initialization failed:', error)
      // Don't automatically create session on error
      setSessionId(null)
      setSessionName('')
      setSessionStats({
        clean_count: 0,
        dirty_count: 0,
        red_count: 0,
        faculty_clean_count: 0,
        combined_dirty_count: 0,
        total_recorded: 0,
        clean_percentage: 0,
        dirty_percentage: 0
      })
      setScanHistory([])
      setDrawSummary(null)
      setOverrideInput('')
      setOverrideCandidate(null)
      setSelectedCandidateKey(null)
    }
  }

  const createSession = async (customName = '') => {
    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/session/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_name: customName })
      })

      const data = await response.json()
      if (response.ok) {
        setSessionId(data.session_id)
        setSessionName(data.session_name)
        setSessionStats({
          clean_count: 0,
          dirty_count: 0,
          red_count: 0,
          faculty_clean_count: 0,
          combined_dirty_count: 0,
          total_recorded: 0,
          clean_percentage: 0,
          dirty_percentage: 0
        })
        await refreshSessionStatus({
          sessionIdOverride: data.session_id,
          sessionNameOverride: data.session_name,
          isDiscardedOverride: data.is_discarded
        })
        await loadSessions()
        showMessage(`Session "${data.session_name}" created successfully`, 'success')
        setShowNewSessionDialog(false)
        setCustomSessionName('')
      } else {
        showMessage(data.error || 'Failed to create session', 'error')
      }
    } catch (error) {
      showMessage('Failed to create session', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const loadSessions = async () => {
    try {
      const response = await fetch(`${API_BASE}/session/list`)
      if (response.ok) {
        const data = await response.json()
        let sessionList = data.sessions || []
        if (user?.role === 'guest') {
          sessionList = sessionList.filter(s => s.is_public)
        }
        setSessions(sessionList)
        return sessionList
      }
    } catch (error) {
      console.error('Failed to load sessions:', error)
    }
    return []
  }

  const switchSession = async (targetSessionId) => {
    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/session/switch/${targetSessionId}`, {
        method: 'POST'
      })

      const data = await response.json()
      if (response.ok) {
        setSessionId(targetSessionId)
        setSessionName(data.session_name)
        await refreshSessionStatus({
          sessionIdOverride: data.session_id ?? targetSessionId,
          sessionNameOverride: data.session_name,
          isDiscardedOverride: data.is_discarded
        })
        await loadStudentNames()
        await loadTeacherNames()
        showMessage(`Switched to "${data.session_name}"`, 'success')
        setShowSessionsDialog(false)
      } else {
        showMessage(data.error || 'Failed to switch session', 'error')
      }
    } catch (error) {
      showMessage('Failed to switch session', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const deleteSession = async (sessionId) => {
    setIsLoading(true)
    try {
      if (user?.role === 'admin' || user?.role === 'superadmin') {
        const response = await fetch(`${API_BASE}/session/delete/${sessionId}`, {
          method: 'DELETE'
        })
        const data = await response.json()
        if (response.ok) {
          showMessage(data.message, 'success')
          const updated = await loadSessions()
          if (data.deleted_session_id === sessionId) {
            if (updated.length > 0) {
              await switchSession(updated[0].session_id)
            } else {
              setSessionId(null)
              setSessionName('')
            }
          }
        } else {
          showMessage(data.error || 'Failed to delete session', 'error')
        }
      } else {
        await requestDeleteSession(sessionId)
        await loadSessions()
      }
      setShowDeleteConfirm(false)
      setSessionToDelete(null)
    } catch (error) {
      showMessage('Failed to delete session', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const uploadCSV = async (file) => {
    const formData = new FormData()
    formData.append('file', file)

    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/csv/upload`, {
        method: 'POST',
        body: formData
      })

      const data = await response.json()
      if (response.ok) {
        setCsvData(data)
        showMessage(`CSV uploaded successfully! ${data.rows_count} students loaded.`, 'success')
        // Reload student names for dropdown
        await loadStudentNames()
      } else {
        showMessage(data.error || 'Failed to upload CSV', 'error')
      }
    } catch (error) {
      showMessage('Failed to upload CSV', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const uploadTeachers = async (file) => {
    const formData = new FormData()
    formData.append('file', file)

    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/teachers/upload`, {
        method: 'POST',
        body: formData
      })

      const data = await response.json()
      if (response.ok) {
        showMessage(`Teacher list uploaded successfully! ${data.count} teachers loaded.`, 'success')
        // Reload teacher names for dropdown
        await loadTeacherNames()
      } else {
        showMessage(data.error || 'Failed to upload teacher list', 'error')
      }
    } catch (error) {
      showMessage('Failed to upload teacher list', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const previewCSV = async (page = 1) => {
    setCsvPreviewLoading(true)
    try {
      const response = await fetch(`${API_BASE}/csv/preview?page=${page}&per_page=50`)
      const data = await response.json()
      
      if (response.ok) {
        if (data.status === 'no_data') {
          showMessage('No student database uploaded yet', 'info')
          return
        }
        setCsvPreviewData(data)
        setCsvPreviewPage(page)
        setShowCsvPreview(true)
      } else {
        showMessage(data.error || 'Failed to load preview', 'error')
      }
    } catch (error) {
      showMessage('Failed to load preview', 'error')
    } finally {
      setCsvPreviewLoading(false)
    }
  }

  const previewTeachers = async (page = 1) => {
    setTeacherPreviewLoading(true)
    try {
      const response = await fetch(`${API_BASE}/teachers/preview?page=${page}&per_page=50`)
      const data = await response.json()
      
      if (response.ok) {
        if (data.status === 'no_data') {
          showMessage('No teacher list uploaded yet', 'info')
          return
        }
        
        setTeacherPreviewData(data)
        setTeacherPreviewPage(page)
        setShowTeacherPreview(true)
      } else {
        showMessage(data.error || 'Failed to load teacher preview', 'error')
      }
    } catch (error) {
      showMessage('Failed to load teacher preview', 'error')
    } finally {
      setTeacherPreviewLoading(false)
    }
  }

  const recordEntry = async (category, inputValue = '', selectedEntry = null) => {
    const trimmedValue = inputValue.trim()
    const normalizedSelection = selectedEntry || null

    const selectedStudentId = normalizedSelection
      ? normalizeName(normalizedSelection.student_id || normalizedSelection.studentId)
      : ''
    const selectedPreferred = normalizedSelection
      ? normalizeName(normalizedSelection.preferred_name ?? normalizedSelection.preferred)
      : ''
    const selectedLast = normalizedSelection
      ? normalizeName(normalizedSelection.last_name ?? normalizedSelection.last)
      : ''

    if (category !== 'dirty') {
      const hasReference = Boolean(
        trimmedValue || selectedStudentId || (selectedPreferred && selectedLast)
      )
      if (!hasReference) {
        if (category === 'faculty') {
          showMessage('Please enter a faculty name', 'error')
        } else {
          showMessage('Please enter a Student ID or Name', 'error')
        }
        return
      }
    }

    setIsLoading(true)
    try {
      const payload = category === 'dirty' ? {} : { input_value: trimmedValue }

      if (category !== 'dirty' && normalizedSelection) {
        if (selectedStudentId) {
          payload.student_id = selectedStudentId
        }
        if (selectedPreferred) {
          payload.preferred_name = selectedPreferred
        }
        if (selectedLast) {
          payload.last_name = selectedLast
        }
        const derivedKey = normalizedSelection.key || makeStudentKey(selectedPreferred, selectedLast, selectedStudentId)
        if (derivedKey) {
          payload.student_key = derivedKey
        }
      }

      const response = await fetch(`${API_BASE}/record/${category}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      const data = await response.json()
      if (response.ok) {
        if (category === 'dirty') {
          const totalDirty = data.dirty_count ?? 0
          const totalSuffix = totalDirty ? ` (total ${totalDirty})` : ''
          showMessage(`Dirty plate recorded${totalSuffix}`, 'success')
        } else {
          const preferredName = (data.preferred_name ?? data.first_name ?? '').trim()
          const lastName = (data.last_name ?? '').trim()
          const nameParts = [preferredName, lastName].filter(Boolean)
          const displayName = nameParts.join(' ')
          const subjectLabel = category === 'faculty' ? 'Faculty' : 'Student'
          const categoryLabel =
            category === 'faculty' ? 'FACULTY CLEAN' : category === 'red' ? 'VERY DIRTY' : category.toUpperCase()

          showMessage(`${displayName || subjectLabel} recorded as ${categoryLabel}`, 'success')
        }

        // Clear input and close dialog
        setPopupInputValue('')
        setShowCleanDialog(false)
        setShowDirtyDialog(false)
        setShowRedDialog(false)
        setShowFacultyDialog(false)
        setPopupSelectedEntry(null)

        // Refresh session status
        await refreshSessionStatus()
      } else {
        if (data.error === 'duplicate') {
          showMessage(data.message, 'error')
        } else {
          showMessage(data.error || 'Failed to record entry', 'error')
        }
      }
    } catch (error) {
      showMessage('Failed to record entry', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const refreshSessionStatus = async ({
    sessionIdOverride = null,
    sessionNameOverride = null,
    isDiscardedOverride = undefined
  } = {}) => {
    let nextSessionId = sessionIdOverride ?? sessionId
    let nextSessionName = sessionNameOverride ?? sessionName
    let nextIsDiscarded =
      isDiscardedOverride !== undefined ? isDiscardedOverride : sessionStats.is_discarded
    try {
      const response = await fetch(`${API_BASE}/session/status`)
      if (response.ok) {
        const data = await response.json()
        setSessionStats((prev) => ({
          ...prev,
          clean_count: data.clean_count,
          dirty_count: data.dirty_count,
          red_count: data.red_count,
          combined_dirty_count: data.combined_dirty_count,
          faculty_clean_count: data.faculty_clean_count,
          total_recorded: data.total_recorded,
          clean_percentage: data.clean_percentage,
          dirty_percentage: data.dirty_percentage,
          is_discarded: data.is_discarded ?? prev.is_discarded,
          draw_info: data.draw_info ?? prev.draw_info
        }))
        nextSessionId = data.session_id ?? nextSessionId
        nextSessionName = data.session_name ?? nextSessionName
        if (data.is_discarded !== undefined) {
          nextIsDiscarded = data.is_discarded
        }
      }
    } catch (error) {
      console.error('Failed to refresh session status:', error)
    }

    // Also load scan history and student names
    await loadScanHistory()
    await loadStudentNames()
    await loadTeacherNames()
    await loadDrawSummary({
      silent: true,
      sessionIdOverride: nextSessionId,
      sessionNameOverride: nextSessionName,
      isDiscarded: nextIsDiscarded
    })
  }

  const loadScanHistory = async () => {
    try {
      const response = await fetch(`${API_BASE}/session/scan-history`)
      if (response.ok) {
        const data = await response.json()
        setScanHistory(data.scan_history || [])
      }
    } catch (error) {
      console.error('Failed to load scan history:', error)
    }
  }

  const loadStudentNames = async () => {
    try {
      const response = await fetch(`${API_BASE}/csv/student-names`)
      if (response.ok) {
        const data = await response.json()
        if (data.status === 'success') {
          const sanitizedNames = (data.names || []).map((name) => {
            const preferred = normalizeName(name.preferred ?? name.preferred_name)
            const last = normalizeName(name.last ?? name.last_name)
            const studentId = normalizeName(name.student_id)
            const key = (name.key && normalizeName(name.key).toLowerCase()) || makeStudentKey(preferred, last, studentId)
            const displayNameRaw = name.display_name || `${preferred} ${last}`.trim()
            const display_name = displayNameRaw || preferred || last
            return {
              ...name,
              preferred,
              preferred_name: name.preferred_name ?? preferred,
              last,
              last_name: name.last_name ?? last,
              key,
              student_id: studentId,
              display_name
            }
          })
          console.log('Loaded student names:', sanitizedNames.length || 0)
          setStudentNames(sanitizedNames)
        } else {
          console.log('No student names available')
          setStudentNames([])
        }
      }
    } catch (error) {
      console.error('Failed to load student names:', error)
      setStudentNames([])
    }
  }

  const loadTeacherNames = async () => {
    try {
      const response = await fetch(`${API_BASE}/teachers/list`)
      if (response.ok) {
        const data = await response.json()
        if (data.status === 'success') {
          console.log('Loaded teacher names:', data.names?.length || 0)
          setTeacherNames(data.names || [])
        } else {
          console.log('No teacher names available')
          setTeacherNames([])
        }
      }
    } catch (error) {
      console.error('Failed to load teacher names:', error)
      setTeacherNames([])
    }
  }

  const updateDrawSummaryState = (summaryPayload, { resetOverrideInput = false } = {}) => {
    if (!summaryPayload) {
      setDrawSummary(null)
      setSelectedCandidateKey(null)
      setOverrideCandidate(null)
      if (resetOverrideInput) {
        setOverrideInput('')
      }
      return
    }

    setDrawSummary(summaryPayload)
    const candidates = summaryPayload.candidates ?? []
    const winnerKey = summaryPayload.draw_info?.winner?.key

    setSelectedCandidateKey(prevKey => {
      if (prevKey && candidates.some(candidate => candidate.key === prevKey)) {
        return prevKey
      }
      if (winnerKey && candidates.some(candidate => candidate.key === winnerKey)) {
        return winnerKey
      }
      return candidates[0]?.key ?? null
    })

    setOverrideCandidate(prevCandidate => {
      if (!prevCandidate) return null
      const match = candidates.find(candidate => candidate.key === prevCandidate.key)
      if (match) {
        return { ...prevCandidate, ...match }
      }
      return prevCandidate
    })

    if (resetOverrideInput) {
      setOverrideInput('')
    }
  }

  const loadDrawSummary = async ({ silent = false, sessionIdOverride = null, sessionNameOverride = null, isDiscarded = undefined } = {}) => {
    const targetSessionId = sessionIdOverride || sessionId
    if (!targetSessionId) {
      updateDrawSummaryState(null, { resetOverrideInput: true })
      return
    }

    setDrawSummaryLoading(true)
    try {
      const response = await fetch(`${API_BASE}/session/${targetSessionId}/draw/summary`)
      const data = await response.json()
      if (response.ok) {
        const summaryPayload = {
          session_id: data.session_id || targetSessionId,
          session_name: data.session_name || sessionNameOverride || sessionName,
          created_at: data.created_at || null,
          is_discarded: data.is_discarded ?? (isDiscarded ?? sessionStats.is_discarded),
          total_tickets: data.total_tickets ?? 0,
          eligible_count: data.eligible_count ?? 0,
          excluded_records: data.excluded_records ?? 0,
          top_candidates: data.top_candidates ?? [],
          candidates: data.candidates ?? [],
          ticket_snapshot: data.ticket_snapshot ?? {},
          generated_at: data.generated_at ?? new Date().toISOString(),
          draw_info: data.draw_info ?? null,
          history: data.history ?? []
        }
        updateDrawSummaryState(summaryPayload)
        setSessionStats(prev => ({
          ...prev,
          is_discarded: summaryPayload.is_discarded,
          draw_info: summaryPayload.draw_info
        }))
      } else {
        if (!silent) {
          showMessage(data.error || 'Failed to load draw summary', 'error')
        }
      }
    } catch (error) {
      console.error('Failed to load draw summary:', error)
      if (!silent) {
        showMessage('Failed to load draw summary', 'error')
      }
    } finally {
      setDrawSummaryLoading(false)
    }
  }

  const applyDrawResponse = (data, { silent = false } = {}) => {
    if (!data) {
      return
    }

    const summaryData = data.summary
    const nextIsDiscarded = data.discarded ?? summaryData?.is_discarded ?? sessionStats.is_discarded

    if (summaryData) {
      const summaryPayload = {
        session_id: summaryData.session_id || sessionId,
        session_name: summaryData.session_name || drawSummary?.session_name || sessionName,
        created_at: summaryData.created_at || drawSummary?.created_at || null,
        is_discarded: nextIsDiscarded,
        total_tickets: summaryData.total_tickets ?? 0,
        eligible_count: summaryData.eligible_count ?? 0,
        excluded_records: summaryData.excluded_records ?? 0,
        top_candidates: summaryData.top_candidates ?? [],
        candidates: summaryData.candidates ?? [],
        ticket_snapshot: summaryData.tickets_snapshot ?? {},
        generated_at: summaryData.generated_at ?? new Date().toISOString(),
        draw_info: data.draw_info ?? sessionStats.draw_info
      }
      updateDrawSummaryState(summaryPayload)
      setSessionStats(prev => ({
        ...prev,
        is_discarded: summaryPayload.is_discarded,
        draw_info: summaryPayload.draw_info
      }))
    } else {
      if (typeof nextIsDiscarded === 'boolean') {
        setSessionStats(prev => ({ ...prev, is_discarded: nextIsDiscarded }))
      }
      if (data.draw_info) {
        setSessionStats(prev => ({ ...prev, draw_info: data.draw_info }))
      }
      if (!summaryData && !silent && data.error) {
        showMessage(data.error, 'error')
      }
    }
  }

  const startDrawProcess = async () => {
    if (!sessionId) {
      showMessage('Select a session before starting a draw', 'error')
      return
    }
    if (!canManageDraw) {
      showMessage('You do not have permission to start a draw', 'error')
      return
    }
    const studentRecordCount = (sessionStats.clean_count ?? 0) + (sessionStats.red_count ?? 0)
    if (studentRecordCount <= 0) {
      showMessage('Add at least one student record before starting a draw', 'error')
      return
    }
    setDrawActionLoading(true)
    try {
      const response = await fetch(`${API_BASE}/session/${sessionId}/draw/start`, {
        method: 'POST'
      })
      const data = await response.json()
      if (response.ok) {
        applyDrawResponse(data, { silent: true })
        if (data.winner?.display_name) {
          showMessage(`Winner selected: ${data.winner.display_name}`, 'success')
        } else {
          showMessage('Winner selected', 'success')
        }
        await refreshSessionStatus()
      } else {
        showMessage(data.error || 'Failed to start draw', 'error')
      }
    } catch (error) {
      console.error('Failed to start draw:', error)
      showMessage('Failed to start draw', 'error')
    } finally {
      setDrawActionLoading(false)
    }
  }

  const finalizeDrawWinner = async () => {
    if (!sessionId) {
      showMessage('Select a session before finalizing a draw', 'error')
      return
    }
    if (!canManageDraw) {
      showMessage('You do not have permission to finalize this draw', 'error')
      return
    }
    setDrawActionLoading(true)
    try {
      const response = await fetch(`${API_BASE}/session/${sessionId}/draw/finalize`, {
        method: 'POST'
      })
      const data = await response.json()
      if (response.ok) {
        applyDrawResponse(data, { silent: true })
        showMessage('Winner finalized', 'success')
        await refreshSessionStatus()
      } else {
        showMessage(data.error || 'Failed to finalize draw', 'error')
      }
    } catch (error) {
      console.error('Failed to finalize draw:', error)
      showMessage('Failed to finalize draw', 'error')
    } finally {
      setDrawActionLoading(false)
    }
  }

  const resetDrawWinner = async () => {
    if (!sessionId) {
      showMessage('Select a session before resetting the draw', 'error')
      return
    }
    if (!sessionStats.draw_info?.winner) {
      showMessage('There is no winner to reset', 'error')
      return
    }
    if (!canManageDraw) {
      showMessage('You do not have permission to reset this draw', 'error')
      return
    }
    setDrawActionLoading(true)
    try {
      const response = await fetch(`${API_BASE}/session/${sessionId}/draw/reset`, {
        method: 'POST'
      })
      const data = await response.json()
      if (response.ok) {
        applyDrawResponse(data, { silent: true })
        showMessage('Draw reset successfully', 'success')
        await refreshSessionStatus()
      } else {
        showMessage(data.error || 'Failed to reset draw', 'error')
      }
    } catch (error) {
      console.error('Failed to reset draw:', error)
      showMessage('Failed to reset draw', 'error')
    } finally {
      setDrawActionLoading(false)
    }
  }

  const overrideDrawWinner = async () => {
    if (!sessionId) {
      showMessage('Select a session before overriding the draw', 'error')
      return
    }
    if (!canOverrideWinner) {
      showMessage('Only super admins can override the draw winner', 'error')
      return
    }

    const studentRecordCount = (sessionStats.clean_count ?? 0) + (sessionStats.red_count ?? 0)
    if (studentRecordCount <= 0) {
      showMessage('A draw cannot be managed until the session has student records', 'error')
      return
    }

    const trimmedInput = overrideInput.trim()
    if (!trimmedInput) {
      showMessage('Enter a student name or ID to override the winner', 'error')
      return
    }

    const candidatePool = overrideOptions
    let candidate = null
    if (overrideCandidate?.key) {
      candidate = candidatePool.find(entry => entry.key === overrideCandidate.key) || overrideCandidate
    }

    if (!candidate) {
      const normalizedInput = trimmedInput.toLowerCase()
      candidate = candidatePool.find(entry => (entry.display_name || '').toLowerCase() === normalizedInput)
        || candidatePool.find(entry => String(entry.student_id || '').toLowerCase() === normalizedInput)
    }

    const payload = {
      input_value: trimmedInput
    }

    if (candidate?.key) {
      payload.student_key = candidate.key
      if (candidate.student_id) {
        payload.student_id = candidate.student_id
      }
      payload.preferred_name = candidate.preferred_name || candidate.preferred || ''
      payload.last_name = candidate.last_name || candidate.last || ''

      setOverrideCandidate(candidate)
      setOverrideInput(candidate.display_name)

      if (drawSummary?.candidates?.some(entry => entry.key === candidate.key)) {
        setSelectedCandidateKey(candidate.key)
      }
    } else if (/^\d+$/.test(trimmedInput)) {
      payload.student_id = trimmedInput
    } else {
      const parts = trimmedInput.split(/\s+/)
      if (parts.length >= 2) {
        payload.preferred_name = parts.slice(0, -1).join(' ')
        payload.last_name = parts.slice(-1).join(' ')
      }
    }

    setDrawActionLoading(true)
    try {
      const response = await fetch(`${API_BASE}/session/${sessionId}/draw/override`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      const data = await response.json()
      if (response.ok) {
        applyDrawResponse(data, { silent: true })
        showMessage('Winner overridden successfully', 'success')
        await refreshSessionStatus()
      } else {
        showMessage(data.error || 'Failed to override draw', 'error')
      }
    } catch (error) {
      console.error('Failed to override draw:', error)
      showMessage('Failed to override draw', 'error')
    } finally {
      setDrawActionLoading(false)
    }
  }

  const toggleDiscardState = async (nextDiscarded) => {
    if (!sessionId) {
      showMessage('Select a session before toggling discard status', 'error')
      return
    }
    if (!canOverrideWinner) {
      showMessage('Only super admins can change discard status', 'error')
      return
    }
    setDiscardLoading(true)
    try {
      const response = await fetch(`${API_BASE}/session/${sessionId}/draw/discard`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ discarded: nextDiscarded })
      })
      const data = await response.json()
      if (response.ok) {
        applyDrawResponse(data, { silent: true })
        if (typeof data.discarded === 'boolean') {
          showMessage(data.message || (data.discarded ? 'Session removed from draw calculations' : 'Session reinstated for draw calculations'), 'success')
        }
        await refreshSessionStatus()
      } else {
        showMessage(data.error || 'Failed to update discard status', 'error')
      }
    } catch (error) {
      console.error('Failed to toggle discard state:', error)
      showMessage('Failed to update discard status', 'error')
    } finally {
      setDiscardLoading(false)
    }
  }

  const exportCSV = async () => {
    try {
      const response = await fetch(`${API_BASE}/export/csv`)
      if (response.ok) {
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${sessionName}_records.csv`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
        showMessage('Records exported successfully', 'success')
      } else {
        showMessage('Failed to export records', 'error')
      }
    } catch (error) {
      showMessage('Failed to export records', 'error')
    }
  }

  const exportDetailedCSV = async () => {
    try {
      const response = await fetch(`${API_BASE}/export/csv/detailed`)
      if (response.ok) {
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${sessionName}_detailed_records.csv`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
        showMessage('Detailed records exported successfully', 'success')
      } else {
        showMessage('Failed to export detailed records', 'error')
      }
    } catch (error) {
      showMessage('Failed to export detailed records', 'error')
    }
  }

  const loadAdminData = async () => {
    if (!user || !canUseTenantAdminFeatures) return

    try {
      const response = await fetch(`${API_BASE}/admin/overview`)
      if (response.ok) {
        const data = await response.json()
        setAdminUsers(data.users || [])
        setAdminSessions(data.sessions || [])
      }
    } catch (error) {
      console.error('Failed to load admin data:', error)
    }
  }

  const showMessage = (text, type = 'info', size = 'small') => {
    setNotification({ text, type, size })
    if (size === 'small') {
      setTimeout(() => setNotification(null), 3000)
    }
  }

  const handleSchoolSignupDialogChange = (open) => {
    setShowSchoolSignupDialog(open)
    if (!open) {
      setIsSubmittingSchoolSignup(false)
      setSchoolSignupForm(createDefaultSchoolSignupForm())
    }
  }

  const updateSchoolSignupField = (field, value) => {
    setSchoolSignupForm((prev) => ({
      ...prev,
      [field]: value,
    }))
  }

  const toggleSchoolFeature = (feature, value) => {
    setSchoolSignupForm((prev) => ({
      ...prev,
      featureToggles: {
        ...prev.featureToggles,
        [feature]: value,
      }
    }))
  }

  const submitSchoolSignup = async () => {
    const trimmedInvite = schoolSignupForm.inviteCode.trim()
    const trimmedSchoolName = schoolSignupForm.schoolName.trim()
    const ownerName = schoolSignupForm.ownerName.trim()
    const ownerUsername = schoolSignupForm.ownerUsername.trim()
    const ownerPassword = schoolSignupForm.ownerPassword.trim()

    if (!trimmedInvite || !trimmedSchoolName || !ownerName || !ownerUsername || !ownerPassword) {
      showMessage('Please complete all required school and owner fields.', 'error')
      return
    }

    if (ownerUsername.length < 3) {
      showMessage('Owner username must be at least 3 characters long.', 'error')
      return
    }

    if (ownerPassword.length < 6) {
      showMessage('Owner password must be at least 6 characters long.', 'error')
      return
    }

    setIsSubmittingSchoolSignup(true)
    try {
      const payload = {
        invite_code: trimmedInvite,
        school_name: trimmedSchoolName,
        school_address: schoolSignupForm.schoolAddress.trim(),
        public_contact: schoolSignupForm.publicContact.trim(),
        owner: {
          display_name: ownerName,
          username: ownerUsername,
          password: ownerPassword,
        },
        feature_toggles: schoolSignupForm.featureToggles,
        guest_access_enabled: schoolSignupForm.guestAccessEnabled,
      }

      const response = await fetch(`${API_BASE}/auth/school-signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      const data = await response.json()
      if (response.ok) {
        handleSchoolSignupDialogChange(false)
        const credentialsMessage = `School "${data.school.name}" provisioned. Owner credentials — Username: ${data.owner.username}, Temporary Password: ${data.owner.password}.`
        showMessage(credentialsMessage, 'success', 'large')
      } else {
        showMessage(data.error || 'Unable to provision school access.', 'error')
      }
    } catch (error) {
      console.error('School signup failed:', error)
      showMessage('Unable to provision school access.', 'error')
    } finally {
      setIsSubmittingSchoolSignup(false)
    }
  }

  const searchGlobalDirectory = async () => {
    if (!isGlobalAdmin) {
      return
    }
    const query = directorySearchQuery.trim()
    if (!query) {
      setDirectorySearchResults([])
      return
    }
    setDirectorySearchLoading(true)
    try {
      const response = await fetch(`${API_BASE}/auth/global-directory?q=${encodeURIComponent(query)}`)
      if (response.ok) {
        const data = await response.json()
        setDirectorySearchResults(data.results || [])
      } else {
        setDirectorySearchResults([])
      }
    } catch (error) {
      console.error('Directory search failed:', error)
      setDirectorySearchResults([])
    } finally {
      setDirectorySearchLoading(false)
    }
  }

  const impersonateSchool = async (schoolId) => {
    if (!schoolId) {
      return
    }
    try {
      const response = await fetch(`${API_BASE}/auth/impersonate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ school_id: schoolId })
      })
      const data = await response.json()
      if (response.ok) {
        showMessage(`Now impersonating ${data.school.name} (${data.school.code}).`, 'success')
        await checkAuthStatus()
      } else {
        showMessage(data.error || 'Unable to impersonate the selected school.', 'error')
      }
    } catch (error) {
      console.error('Failed to impersonate school:', error)
      showMessage('Unable to impersonate the selected school.', 'error')
    }
  }

  const clearImpersonation = async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/impersonation/clear`, { method: 'POST' })
      if (response.ok) {
        showMessage('Global impersonation cleared.', 'info')
        await checkAuthStatus()
      } else {
        const data = await response.json().catch(() => ({}))
        showMessage(data.error || 'Unable to clear impersonation.', 'error')
      }
    } catch (error) {
      console.error('Failed to clear impersonation:', error)
      showMessage('Unable to clear impersonation.', 'error')
    }
  }

  const renderSchoolSignupDialog = () => (
    <Dialog open={showSchoolSignupDialog} onOpenChange={handleSchoolSignupDialogChange}>
      <DialogContent className="max-w-2xl" dismissOnOverlayClick={false}>
        <DialogHeader>
          <DialogTitle>School Sign-Up / Access Request</DialogTitle>
          <DialogDescription>
            Submit your school details to provision a new tenant and receive onboarding credentials.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-5">
          <Alert className="border-amber-200 bg-amber-50">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription className="text-amber-900">
              Use an official school contact email so our team can verify your request. Instructions and confirmations are sent to the provided contact address.
            </AlertDescription>
          </Alert>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="signup-school-name">School Name</Label>
              <Input
                id="signup-school-name"
                value={schoolSignupForm.schoolName}
                onChange={(e) => updateSchoolSignupField('schoolName', e.target.value)}
                placeholder="North Ridge Academy"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="signup-invite-code">Invite Code</Label>
              <Input
                id="signup-invite-code"
                value={schoolSignupForm.inviteCode}
                onChange={(e) => updateSchoolSignupField('inviteCode', e.target.value)}
                placeholder="Enter provisioning invite"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="signup-school-address">School Address / Region</Label>
              <Input
                id="signup-school-address"
                value={schoolSignupForm.schoolAddress}
                onChange={(e) => updateSchoolSignupField('schoolAddress', e.target.value)}
                placeholder="123 Campus Way, Toronto, ON"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="signup-public-contact">Public Contact Email</Label>
              <Input
                id="signup-public-contact"
                type="email"
                value={schoolSignupForm.publicContact}
                onChange={(e) => updateSchoolSignupField('publicContact', e.target.value)}
                placeholder="admin@school.ca"
              />
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="signup-owner-name">Owner Display Name</Label>
              <Input
                id="signup-owner-name"
                value={schoolSignupForm.ownerName}
                onChange={(e) => updateSchoolSignupField('ownerName', e.target.value)}
                placeholder="Head of School"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="signup-owner-username">Owner Username</Label>
              <Input
                id="signup-owner-username"
                value={schoolSignupForm.ownerUsername}
                onChange={(e) => updateSchoolSignupField('ownerUsername', e.target.value)}
                placeholder="principal"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="signup-owner-password">Owner Password</Label>
              <Input
                id="signup-owner-password"
                type="password"
                value={schoolSignupForm.ownerPassword}
                onChange={(e) => updateSchoolSignupField('ownerPassword', e.target.value)}
                placeholder="Temporary password"
              />
            </div>
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold">Enable Guest Access</p>
                <p className="text-xs text-gray-500">Allow view-only guests for this tenant by default.</p>
              </div>
              <Switch
                checked={schoolSignupForm.guestAccessEnabled}
                onCheckedChange={(checked) => updateSchoolSignupField('guestAccessEnabled', checked)}
              />
            </div>
            <div>
              <p className="text-sm font-semibold mb-2">Feature Toggles</p>
              <div className="space-y-2">
                {SCHOOL_FEATURES.map((feature) => (
                  <div key={feature.key} className="flex items-center justify-between rounded border px-3 py-2">
                    <div>
                      <p className="text-sm font-medium">{feature.label}</p>
                      <p className="text-xs text-gray-500">Configure availability at tenant creation.</p>
                    </div>
                    <Switch
                      checked={Boolean(schoolSignupForm.featureToggles[feature.key])}
                      onCheckedChange={(checked) => toggleSchoolFeature(feature.key, checked)}
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              onClick={() => handleSchoolSignupDialogChange(false)}
              variant="outline"
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              onClick={submitSchoolSignup}
              className="flex-1 bg-amber-600 hover:bg-amber-700"
              disabled={isSubmittingSchoolSignup}
            >
              {isSubmittingSchoolSignup ? 'Submitting...' : 'Submit Request'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )

  const renderGlobalAdminDashboard = () => {
    const schools = globalAdminContext?.schools ?? []
    const impersonatedSchool = globalAdminContext?.impersonated_school
    const activeSchool = globalAdminContext?.active_school
    const impersonating = Boolean(globalAdminContext?.impersonating)

    return (
      <div className="py-10 space-y-6">
        <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-amber-700">
                  <Globe2 className="h-5 w-5" /> Global Administration
                </CardTitle>
                <CardDescription>Manage tenants and impersonation context.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-gray-700">Impersonation State</p>
                    <p className="text-gray-500">
                      {impersonating
                        ? impersonatedSchool
                          ? `Acting as ${impersonatedSchool.name} (${impersonatedSchool.code}).`
                          : 'Acting as selected tenant.'
                        : 'Not impersonating any tenant.'}
                    </p>
                  </div>
                  {impersonating ? (
                    <Button size="sm" variant="outline" onClick={clearImpersonation}>
                      <CircleSlash2 className="h-4 w-4 mr-1" /> Exit
                    </Button>
                  ) : (
                    <Badge variant="outline" className="border-emerald-200 text-emerald-700">
                      Global Scope
                    </Badge>
                  )}
                </div>
                <div>
                  <p className="font-medium text-gray-700">Active School Context</p>
                  <p className="text-gray-500">
                    {activeSchool
                      ? `${activeSchool.name} (${activeSchool.code})`
                      : 'No tenant context selected.'}
                  </p>
                </div>
                <div className="flex items-center justify-between">
                  <p className="font-medium text-gray-700">Registered Schools</p>
                  <Badge variant="outline" className="border-gray-200 text-gray-600">
                    {schools.length}
                  </Badge>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Building2 className="h-5 w-5" /> Quick Actions
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <Button className="w-full" onClick={() => handleSchoolSignupDialogChange(true)}>
                  <Plus className="h-4 w-4 mr-2" /> Provision New School
                </Button>
                <Button
                  className="w-full"
                  variant="outline"
                  onClick={() => checkAuthStatus({ skipSessionInit: false })}
                >
                  <RefreshCcw className="h-4 w-4 mr-2" /> Refresh Status
                </Button>
                {!impersonating && (
                  <Alert className="border-blue-200 bg-blue-50">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription className="text-sm text-blue-800">
                      Select a school from the list to impersonate and access tenant dashboards.
                    </AlertDescription>
                  </Alert>
                )}
              </CardContent>
            </Card>
          </div>
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <School className="h-5 w-5" /> School Directory
                </CardTitle>
                <CardDescription>Launch tenant dashboards by impersonating a school.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {schools.length === 0 ? (
                  <p className="text-sm text-gray-500">No schools registered yet.</p>
                ) : (
                  <div className="space-y-2">
                    {schools.map((school) => (
                      <div key={school.id} className="flex items-center justify-between rounded border px-3 py-2">
                        <div>
                          <p className="font-medium">{school.name}</p>
                          <p className="text-xs text-gray-500">{school.code}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant={school.guest_access_enabled ? 'outline' : 'destructive'}>
                            {school.guest_access_enabled ? 'Guest Access On' : 'Guest Access Off'}
                          </Badge>
                          <Button size="sm" variant="outline" onClick={() => impersonateSchool(school.id)}>
                            {impersonatedSchool?.id === school.id ? 'Viewing' : 'Impersonate'}
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <UserSearch className="h-5 w-5" /> User Directory Search
                </CardTitle>
                <CardDescription>Lookup users across all tenants.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                  <Input
                    value={directorySearchQuery}
                    onChange={(e) => setDirectorySearchQuery(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        searchGlobalDirectory()
                      }
                    }}
                    placeholder="Search by username or display name"
                  />
                  <Button onClick={searchGlobalDirectory} disabled={directorySearchLoading}>
                    <Search className="h-4 w-4 mr-2" /> {directorySearchLoading ? 'Searching...' : 'Search'}
                  </Button>
                </div>
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {directorySearchResults.length === 0 ? (
                    <p className="text-sm text-gray-500">No results yet. Try searching for a username.</p>
                  ) : (
                    directorySearchResults.map((result) => (
                      <div key={`${result.school.id}-${result.username}`} className="rounded border px-3 py-2">
                        <p className="font-medium">{result.display_name}</p>
                        <p className="text-xs text-gray-500">@{result.username} • {result.role} • {result.status}</p>
                        <p className="text-xs text-gray-400">{result.school.name} ({result.school.code})</p>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    )
  }

  const handleCategoryClick = (category) => {
    setPopupInputValue('')
    setPopupSelectedEntry(null)
    if (category === 'clean') setShowCleanDialog(true)
    else if (category === 'dirty') setShowDirtyDialog(true)
    else if (category === 'red') setShowRedDialog(true)
    else if (category === 'faculty') setShowFacultyDialog(true)
  }

  const handlePopupSubmit = (category) => {
    if (category === 'dirty') recordEntry(category)
    else recordEntry(category, popupInputValue, popupSelectedEntry)
  }

  const handleKeyPress = (e, category) => {
    if (e.key === 'Enter') {
      handlePopupSubmit(category)
    }
  }

  // Account management functions
  const loadAllUsers = async () => {
    if (!canUseTenantAdminFeatures) return
    try {
      const response = await fetch(`${API_BASE}/admin/users`)
      if (response.ok) {
        const data = await response.json()
        setAllUsers(data.users || [])
      }
    } catch (error) {
      console.error('Failed to load users:', error)
    }
  }

  const toggleAccountStatus = async (username, currentStatus) => {
    try {
      const newStatus = currentStatus === 'active' ? 'disabled' : 'active'
      const response = await fetch(`${API_BASE}/admin/manage-account-status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, status: newStatus })
      })
      
      if (response.ok) {
        const data = await response.json()
        showMessage(data.message, 'success')
        loadAllUsers() // Refresh the user list
      } else {
        const error = await response.json()
        showMessage(error.error, 'error')
      }
    } catch (error) {
      showMessage('Failed to update account status', 'error')
    }
  }

  // Delete request functions
  const requestDeleteSession = async (sessionId) => {
    try {
      const response = await fetch(`${API_BASE}/session/request-delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId })
      })
      
      if (response.ok) {
        const data = await response.json()
        showMessage(data.message, 'success')
      } else {
        const error = await response.json()
        showMessage(error.error, 'error')
      }
    } catch (error) {
      showMessage('Failed to process delete request', 'error')
    }
  }

  const loadDeleteRequests = async () => {
    try {
      const response = await fetch(`${API_BASE}/admin/delete-requests`)
      if (response.ok) {
        const data = await response.json()
        const pending = (data.requests || []).filter(req => req.status === 'pending')
        setDeleteRequests(pending)
      }
    } catch (error) {
      console.error('Failed to load delete requests:', error)
    }
  }

  const approveDeleteRequest = async (requestId) => {
    try {
      const response = await fetch(`${API_BASE}/admin/approve-delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request_id: requestId })
      })
      
      if (response.ok) {
        const data = await response.json()
        showMessage(data.message, 'success')
        const updated = await loadSessions() // Refresh sessions list
        loadDeleteRequests() // Refresh delete requests
        if (data.deleted_session_id === sessionId) {
          if (updated.length > 0) {
            await switchSession(updated[0].session_id)
          } else {
            setSessionId(null)
            setSessionName('')
          }
        }
      } else {
        const error = await response.json()
        showMessage(error.error, 'error')
      }
    } catch (error) {
      showMessage('Failed to approve delete request', 'error')
    }
  }

  const rejectDeleteRequest = async (requestId) => {
    try {
      const response = await fetch(`${API_BASE}/admin/delete-requests/${requestId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })

      if (response.ok) {
        const data = await response.json()
        showMessage(data.message, 'success')
        loadDeleteRequests()
      } else {
        const error = await response.json()
        showMessage(error.error || 'Failed to reject delete request', 'error')
      }
    } catch (error) {
      showMessage('Failed to reject delete request', 'error')
    }
  }

  useEffect(() => {
    if (canUseTenantAdminFeatures) {
      loadDeleteRequests()
    }
  }, [canUseTenantAdminFeatures])

  const generateInviteCode = async () => {
    try {
      const response = await fetch(`${API_BASE}/admin/invite`, { method: 'POST' })
      const data = await response.json()
      if (response.ok) {
        setInviteCode(data.invite_code)
        setModal({ type: 'invite' })
      } else {
        showMessage(data.error || 'Failed to generate invite code', 'error')
      }
    } catch (error) {
      showMessage('Failed to generate invite code', 'error')
    }
  }

  const copyInviteCode = () => {
    navigator.clipboard.writeText(inviteCode)
    showMessage('Invite code copied', 'success')
  }

  // Super admin functions
  const changeUserRole = async (username, newRole) => {
    try {
      const response = await fetch(`${API_BASE}/superadmin/change-role`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, role: newRole })
      })
      
      if (response.ok) {
        const data = await response.json()
        showMessage(data.message, 'success')
        loadAllUsers() // Refresh users list
      } else {
        const error = await response.json()
        showMessage(error.error, 'error')
      }
    } catch (error) {
      showMessage('Failed to change user role', 'error')
    }
  }

  const deleteUserAccount = async (username) => {
    try {
      const response = await fetch(`${API_BASE}/superadmin/delete-account`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username })
      })
      
      if (response.ok) {
        const data = await response.json()
        showMessage(data.message, 'success')
        loadAllUsers() // Refresh users list
        loadAdminData() // Refresh admin data
      } else {
        const error = await response.json()
        showMessage(error.error, 'error')
      }
    } catch (error) {
      showMessage('Failed to delete user account', 'error')
    }
  }

  // Login Screen
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle className="text-3xl font-bold bg-gradient-to-r from-amber-600 to-yellow-600 bg-clip-text text-transparent">
              PLATE
            </CardTitle>
            <CardDescription className="text-gray-600 mt-2">
              Prevention, Logging & Assessment of Tossed Edibles
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                type="text"
                placeholder="Enter username"
                value={loginUsername}
                onChange={(e) => setLoginUsername(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && login()}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="Enter password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && login()}
              />
            </div>
            <Button 
              onClick={login} 
              className="w-full bg-amber-600 hover:bg-amber-700"
              disabled={isLoading}
            >
              {isLoading ? 'Logging in...' : 'Login'}
            </Button>
            
            <Button 
              onClick={guestLogin} 
              variant="outline"
              className="w-full border-amber-600 text-amber-600 hover:bg-amber-50"
              disabled={isLoading}
            >
              Continue as Guest
            </Button>
            
            <div className="text-center space-y-2">
              <Button
                variant="link"
                onClick={() => setShowSignupDialog(true)}
                className="text-amber-600 hover:text-amber-700"
              >
                Don't have an account? Sign up
              </Button>
              <Button
                variant="link"
                className="text-sm text-gray-600 hover:text-gray-900"
                onClick={() => handleSchoolSignupDialogChange(true)}
              >
                School Sign-Up / Access Request
              </Button>
            </div>

          </CardContent>
        </Card>

        {/* Signup Dialog */}
        <Dialog open={showSignupDialog} onOpenChange={setShowSignupDialog}>
          <DialogContent dismissOnOverlayClick={false}>
            <DialogHeader>
              <DialogTitle>Create Account</DialogTitle>
              <DialogDescription>
                Enter your information to create a new account
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="signup-name">Full Name</Label>
                <Input
                  id="signup-name"
                  type="text"
                  placeholder="Enter your full name"
                  value={signupName}
                  onChange={(e) => setSignupName(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="signup-username">Username</Label>
                <Input
                  id="signup-username"
                  type="text"
                  placeholder="Choose a username (min 3 characters)"
                  value={signupUsername}
                  onChange={(e) => setSignupUsername(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="signup-password">Password</Label>
                <Input
                  id="signup-password"
                  type="password"
                  placeholder="Choose a password (min 6 characters)"
                  value={signupPassword}
                  onChange={(e) => setSignupPassword(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="signup-invite">Invite Code</Label>
                <Input
                  id="signup-invite"
                  type="text"
                  placeholder="Enter invite code"
                  value={signupInviteCode}
                  onChange={(e) => setSignupInviteCode(e.target.value)}
                />
              </div>
              <div className="flex gap-2">
                <Button onClick={() => setShowSignupDialog(false)} variant="outline" className="flex-1">
                  Cancel
                </Button>
                <Button 
                  onClick={signup} 
                  className="flex-1 bg-amber-600 hover:bg-amber-700"
                  disabled={isLoading}
                >
                  {isLoading ? 'Creating...' : 'Create Account'}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {renderSchoolSignupDialog()}
      </div>
    )
  }

  // Main Application
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-amber-600 to-yellow-600 bg-clip-text text-transparent">
                PLATE
              </h1>
              <p className="text-sm text-gray-600">Prevention, Logging & Assessment of Tossed Edibles</p>
            </div>
            <div className="flex items-center gap-4">
              {isGlobalAdmin && (
                <div className="hidden sm:flex flex-col text-right text-xs text-gray-500">
                  <div className="flex items-center gap-1 justify-end text-gray-600">
                    <Globe2 className="h-4 w-4 text-amber-600" />
                    <span>
                      {globalAdminContext?.impersonating
                        ? globalAdminContext?.impersonated_school
                          ? `Impersonating ${globalAdminContext.impersonated_school.name}`
                          : 'Impersonating tenant'
                        : 'Global admin scope'}
                    </span>
                  </div>
                  <span className="text-[11px] text-gray-400">
                    {globalAdminContext?.active_school
                      ? `Active: ${globalAdminContext.active_school.name} (${globalAdminContext.active_school.code})`
                      : 'No tenant selected'}
                  </span>
                </div>
              )}
              <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">
                {user.name} ({user.username})
              </Badge>
              <Button
                onClick={() => window.open('https://github.com/Antineutrino-4444/goldenplatewebsite', '_blank')}
                variant="outline"
                size="sm"
                className="text-gray-600 hover:text-gray-900"
              >
                <svg className="h-4 w-4 mr-2" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                </svg>
                GitHub
              </Button>
              <Button onClick={logout} variant="outline" size="sm">
                <LogOut className="h-4 w-4 mr-2" />
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {isGlobalAdmin && !canAccessTenantData ? (
          renderGlobalAdminDashboard()
        ) : (
          <>
        {/* No Session State */}
        {!sessionId ? (
          <div className="text-center py-16">
            <div className="max-w-md mx-auto">
              <div className="mb-8">
                <div className="text-6xl mb-4">🍽️</div>
                <h2 className="text-2xl font-bold text-gray-900 mb-2">No Active Session</h2>
                <p className="text-gray-600 mb-6">
                  Create a new session to start tracking plate cleanliness and food waste data.
                </p>
              </div>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Button
                  onClick={() => createSession('')}
                  className="bg-amber-600 hover:bg-amber-700 text-white px-8 py-3 text-lg"
                  size="lg"
                  disabled={isLoading}
                >
                  <Plus className="h-5 w-5 mr-2" />
                  {isLoading ? 'Creating...' : 'Create New Session'}
                </Button>
                {canUseTenantAdminFeatures && (
                  <Button
                    onClick={() => {
                      setShowAdminPanel(true)
                      loadAdminData()
                    }}
                    className="relative bg-red-600 hover:bg-red-700 text-white px-8 py-3 text-lg"
                    size="lg"
                    disabled={isLoading}
                  >
                    <Shield className="h-5 w-5 mr-2" />
                    Admin Panel
                    {deleteRequests.length > 0 && (
                      <span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs rounded-full px-2 py-0.5">
                        {deleteRequests.length}
                      </span>
                    )}
                  </Button>
                )}
              </div>
            </div>
          </div>
        ) : (
          <>
            {/* Session Info */}
            <div className="mb-6 text-center">
              <div className="text-lg font-medium text-gray-900">
                Session: {sessionName}
              </div>
              <div className="text-sm text-gray-500">
                Student Total: {sessionStats.clean_count + sessionStats.dirty_count + sessionStats.red_count}
              </div>
              <div className="text-sm text-gray-500">
                Faculty Clean: {sessionStats.faculty_clean_count}
              </div>
              {isSessionDiscarded && (
                <div className="mt-2 flex justify-center">
                  <Badge variant="destructive" className="uppercase tracking-wide">Discarded from draw</Badge>
                </div>
              )}
              <div className="mt-3 text-sm text-gray-600">
                {currentDrawInfo?.winner ? (
                  <div className="space-y-1">
                    <div>
                      Current Winner:{' '}
                      <span className="font-semibold">{currentDrawInfo.winner.display_name}</span>
                      {currentDrawInfo.finalized ? ' (Finalized)' : ' (Pending Finalization)'}
                      {currentDrawInfo.override && (
                        <Badge variant="outline" className="ml-2 text-xs">Superadmin Override</Badge>
                      )}
                    </div>
                    {currentDrawInfo.winner_timestamp && (
                      <div className="text-xs text-gray-500 flex items-center justify-center gap-1">
                        <Clock className="h-3 w-3" />
                        {new Date(currentDrawInfo.winner_timestamp).toLocaleString()}
                      </div>
                    )}
                  </div>
                ) : (
                  <span className="text-gray-500">No winner selected yet.</span>
                )}
              </div>
            </div>

            {/* Navigation Buttons */}
            <div className="flex flex-wrap gap-2 mb-6 justify-center">
              {user?.role !== 'guest' && (
                <Button onClick={() => setShowNewSessionDialog(true)} className="bg-blue-600 hover:bg-blue-700">
                  <Plus className="h-4 w-4 mr-2" />
                  New Session
                </Button>
              )}
              <Button onClick={() => { loadSessions(); setShowSessionsDialog(true) }} className="bg-orange-600 hover:bg-orange-700">
                <Users className="h-4 w-4 mr-2" />
                Switch Session
              </Button>
              {canUseTenantAdminFeatures && (
                <Button onClick={() => { loadAdminData(); setShowDashboard(true) }} className="bg-purple-600 hover:bg-purple-700">
                  <BarChart3 className="h-4 w-4 mr-2" />
                  Dashboard
                </Button>
              )}
              {canUseTenantAdminFeatures && (
                <Button
                  onClick={() => { loadAdminData(); setShowAdminPanel(true) }}
                  className="relative bg-red-600 hover:bg-red-700"
                >
                  <Shield className="h-4 w-4 mr-2" />
                  Admin Panel
                  {deleteRequests.length > 0 && (
                    <span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs rounded-full px-2 py-0.5">
                      {deleteRequests.length}
                    </span>
                  )}
                </Button>
              )}
            </div>

        <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
          {/* Student Database */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Upload className="h-5 w-5" />
                Student Database
              </CardTitle>
              <CardDescription>
                Upload CSV with student data for food waste tracking (Student ID, Last, Preferred, Grade, Advisor, House, Clan)
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!canUseTenantAdminFeatures ? (
                <Alert className="border-blue-200 bg-blue-50">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription className="text-blue-800">
                    CSV upload is restricted to admin and super admin users only.
                  </AlertDescription>
                </Alert>
              ) : (
                <Input
                  type="file"
                  accept=".csv"
                  onChange={(e) => e.target.files[0] && uploadCSV(e.target.files[0])}
                  className="mb-4"
                />
              )}
              {canUseTenantAdminFeatures && (
                <div className="flex gap-2 mb-4">
                  <Button
                    onClick={() => previewCSV(1)} 
                    variant="outline" 
                    className="flex-1"
                    disabled={csvPreviewLoading}
                  >
                    <FileText className="h-4 w-4 mr-2" />
                    {csvPreviewLoading ? 'Loading...' : 'Preview Database'}
                  </Button>
                </div>
              )}
              {csvData && (
                <div className="text-sm text-green-600">
                  ✓ {csvData.rows_count} students loaded
                </div>
              )}
            </CardContent>
          </Card>

          {/* Teacher List Upload */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5" />
                Teacher Database
              </CardTitle>
              <CardDescription>
                Upload teacher list for faculty clean plate tracking (one teacher name per line, e.g., "Smith, J")
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!canUseTenantAdminFeatures ? (
                <Alert className="border-blue-200 bg-blue-50">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription className="text-blue-800">
                    Teacher list upload is restricted to admin and super admin users only.
                  </AlertDescription>
                </Alert>
              ) : (
                <Input
                  type="file"
                  accept=".csv,.txt"
                  onChange={(e) => e.target.files[0] && uploadTeachers(e.target.files[0])}
                  className="mb-4"
                />
              )}
              {canUseTenantAdminFeatures && (
                <div className="flex gap-2 mb-4">
                  <Button
                    onClick={() => previewTeachers(1)} 
                    variant="outline" 
                    className="flex-1"
                    disabled={teacherPreviewLoading}
                  >
                    <FileText className="h-4 w-4 mr-2" />
                    {teacherPreviewLoading ? 'Loading...' : 'Preview Teacher List'}
                  </Button>
                </div>
              )}
              {teacherNames.length > 0 && (
                <div className="text-sm text-green-600">
                  ✓ {teacherNames.length} teachers loaded
                </div>
              )}
            </CardContent>
          </Card>

          {/* Export Records */}
          {showExportCard && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Download className="h-5 w-5" />
                  Export Food Waste Data
                </CardTitle>
                <CardDescription>
                  Download plate cleanliness records by category (Clean, Dirty Count, Very Dirty, Faculty Clean)
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col gap-2">
                  <Button onClick={exportCSV} className="w-full bg-amber-600 hover:bg-amber-700">
                    <Download className="h-4 w-4 mr-2" />
                    Export Food Waste Data
                  </Button>
                  <Button onClick={exportDetailedCSV} variant="outline" className="w-full">
                    <FileText className="h-4 w-4 mr-2" />
                    Export Detailed Record List
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          <Card
            id="draw-center-section"
            className={`${showExportCard ? '' : 'lg:col-span-2'}`}
          >
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <CardTitle className="flex items-center gap-2">
                  <Trophy className="h-5 w-5" />
                  Draw Center
                </CardTitle>
                <div className="flex items-center gap-2">
                  <Button
                    onClick={() => loadDrawSummary({ silent: false })}
                    variant="outline"
                    size="sm"
                    disabled={drawSummaryLoading}
                  >
                    <RefreshCcw className="h-4 w-4 mr-2" />
                    Refresh
                  </Button>
                  <Button
                    onClick={() => setIsDrawCenterCollapsed((prev) => !prev)}
                    variant="outline"
                    size="sm"
                  >
                    {isDrawCenterCollapsed ? (
                      <>
                        <ChevronDown className="h-4 w-4 mr-2" />
                        Expand
                      </>
                    ) : (
                      <>
                        <ChevronUp className="h-4 w-4 mr-2" />
                        Collapse
                      </>
                    )}
                  </Button>
                </div>
              </div>
              {!isDrawCenterCollapsed && (
                <>
                  <CardDescription>
                    Review ticket standings and manage the draw for this session.
                  </CardDescription>
                  {drawSummary?.generated_at && (
                    <div className="text-xs text-gray-500">
                      Updated {new Date(drawSummary.generated_at).toLocaleString()}
                    </div>
                  )}
                </>
              )}
            </CardHeader>
            {!isDrawCenterCollapsed && (
              <CardContent>
              {drawSummaryLoading ? (
                <div className="py-8 text-center text-gray-500">Loading draw summary...</div>
              ) : drawSummary ? (
                <div className="space-y-6">
                  {isSessionDiscarded && (
                    <Alert variant="destructive">
                      <Ban className="h-4 w-4" />
                      <AlertDescription>
                        This session is currently discarded from draw calculations. Restore it to include ticket updates.
                      </AlertDescription>
                    </Alert>
                  )}
                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                      <div className="text-sm text-gray-500">Total tickets</div>
                      <div className="text-2xl font-semibold">
                        {Number(drawSummary.total_tickets ?? 0).toFixed(2)}
                      </div>
                    </div>
                    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                      <div className="text-sm text-gray-500">Eligible students</div>
                      <div className="text-2xl font-semibold">
                        {drawSummary.eligible_count ?? 0}
                      </div>
                    </div>
                    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                      <div className="text-sm text-gray-500">Excluded records</div>
                      <div className="text-2xl font-semibold">
                        {drawSummary.excluded_records ?? 0}
                      </div>
                    </div>
                    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                      <div className="text-sm text-gray-500">Winner status</div>
                      <div className="text-2xl font-semibold">
                        {currentDrawInfo?.finalized ? 'Finalized' : 'Pending'}
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    <Button
                      onClick={startDrawProcess}
                      className="bg-emerald-600 hover:bg-emerald-700"
                      disabled={
                        drawActionLoading ||
                        !canManageDraw ||
                        isSessionDiscarded ||
                        !hasStudentRecords ||
                        (drawSummary?.total_tickets ?? 0) <= 0
                      }
                    >
                      <Wand2 className="h-4 w-4 mr-2" />
                      Start Draw
                    </Button>
                    <Button
                      onClick={finalizeDrawWinner}
                      variant="outline"
                      disabled={drawActionLoading || !canManageDraw || !currentDrawInfo?.winner || currentDrawInfo.finalized}
                    >
                      <CheckCircle className="h-4 w-4 mr-2" />
                      Finalize Winner
                    </Button>
                    <Button
                      onClick={resetDrawWinner}
                      variant="outline"
                      disabled={drawActionLoading || !canManageDraw || !currentDrawInfo?.winner}
                    >
                      <RefreshCcw className="h-4 w-4 mr-2" />
                      Reset Draw
                    </Button>
                  </div>
                  {canOverrideWinner && (
                    <div className="flex w-full flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
                      <div className="w-full sm:max-w-xs">
                        <SearchableNameInput
                          placeholder="Search student (name or ID)"
                          value={overrideInput}
                          onChange={(value, meta) => {
                            setOverrideInput(value)
                            if (!meta || meta.source !== 'selection') {
                              setOverrideCandidate(null)
                            }
                          }}
                          onSelectName={(candidate) => {
                            if (candidate) {
                              const sanitized = sanitizeSelection(candidate)
                              setOverrideCandidate(sanitized)
                              if (sanitized?.key && drawSummary?.candidates?.some(entry => entry.key === sanitized.key)) {
                                setSelectedCandidateKey(sanitized.key)
                              }
                            }
                          }}
                          onKeyPress={(e) => {
                            if (e.key === 'Enter') {
                              e.preventDefault()
                              overrideDrawWinner()
                            }
                          }}
                          names={overrideOptions}
                          className="w-full"
                        />
                      </div>
                      <Button
                        onClick={overrideDrawWinner}
                        variant="outline"
                        disabled={drawActionLoading || !overrideInput.trim() || !hasStudentRecords}
                      >
                        <ShieldCheck className="h-4 w-4 mr-2" />
                        Override Winner
                      </Button>
                      <Button
                        onClick={() => toggleDiscardState(!isSessionDiscarded)}
                        variant={isSessionDiscarded ? 'default' : 'outline'}
                        disabled={discardLoading}
                      >
                        <Ban className="h-4 w-4 mr-2" />
                        {isSessionDiscarded ? 'Restore Session' : 'Discard Session'}
                      </Button>
                    </div>
                  )}
                  <div className="grid gap-4 lg:grid-cols-2">
                    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                      <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                        <Trophy className="h-4 w-4" />
                        Current Winner
                      </div>
                      <div className="mt-3 text-sm">
                        {currentDrawInfo?.winner ? (
                          <div className="space-y-2">
                            <div className="text-lg font-semibold">{currentDrawInfo.winner.display_name}</div>
                            {currentDrawInfo.winner.student_identifier && (
                              <div className="text-xs text-gray-500">Student ID: {currentDrawInfo.winner.student_identifier}</div>
                            )}
                            <div className="flex flex-wrap gap-2 text-xs text-gray-500">
                              {currentDrawInfo.winner.grade && <span>Grade: {currentDrawInfo.winner.grade}</span>}
                              {currentDrawInfo.winner.house && <span>House: {currentDrawInfo.winner.house}</span>}
                              {currentDrawInfo.winner.clan && <span>Clan: {currentDrawInfo.winner.clan}</span>}
                            </div>
                            <div className="flex items-center gap-1 text-xs text-gray-500">
                              <Clock className="h-3 w-3" />
                              {currentDrawInfo.winner_timestamp ? new Date(currentDrawInfo.winner_timestamp).toLocaleString() : 'Time not recorded'}
                            </div>
                            <div className="text-xs text-gray-500">
                              Tickets at selection: {Number(currentDrawInfo.tickets_at_selection ?? 0).toFixed(2)} • Chance: {Number(currentDrawInfo.probability_at_selection ?? 0).toFixed(2)}%
                            </div>
                            <div className="text-xs">
                              Status:{' '}
                              <Badge variant={currentDrawInfo.finalized ? 'default' : 'outline'}>
                                {currentDrawInfo.finalized ? 'Finalized' : 'Awaiting Finalization'}
                              </Badge>
                            </div>
                            {currentDrawInfo.override && (
                              <div className="text-xs text-orange-600">Winner selected by superadmin override.</div>
                            )}
                          </div>
                        ) : (
                          <div className="text-sm text-gray-500">No winner selected yet.</div>
                        )}
                      </div>
                    </div>
                    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                      <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                        <ListOrdered className="h-4 w-4" />
                        Top Candidates
                      </div>
                      <div className="mt-3">
                        {drawSummary.top_candidates && drawSummary.top_candidates.length > 0 ? (
                          <div className="space-y-2">
                            {drawSummary.top_candidates.map((candidate, index) => {
                              const isActive = selectedCandidateKey === candidate.key
                              return (
                                <button
                                  key={candidate.key}
                                  type="button"
                                  onClick={() => setSelectedCandidateKey(candidate.key)}
                                  className={`flex w-full items-center justify-between rounded border px-3 py-2 text-left transition ${
                                    isActive ? 'border-emerald-500 bg-emerald-50' : 'border-gray-200 hover:bg-gray-50'
                                  }`}
                                >
                                  <div>
                                    <div className="font-medium">{candidate.display_name}</div>
                                    <div className="text-xs text-gray-500">
                                      Tickets: {Number(candidate.tickets ?? 0).toFixed(2)} • Chance: {Number(candidate.probability ?? 0).toFixed(2)}%
                                    </div>
                                  </div>
                                  <Badge variant={isActive ? 'default' : 'outline'}>#{index + 1}</Badge>
                                </button>
                              )
                            })}
                          </div>
                        ) : (
                          <div className="text-sm text-gray-500">No eligible students yet.</div>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="grid gap-4 lg:grid-cols-2">
                    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                      <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                        <Users className="h-4 w-4" />
                        Selected Candidate Details
                      </div>
                      <div className="mt-3 text-sm">
                        {selectedCandidate ? (
                          <div className="space-y-3">
                            <div>
                              <div className="text-lg font-semibold">{selectedCandidate.display_name}</div>
                              {selectedCandidate.student_identifier && (
                                <div className="text-xs text-gray-500">Student ID: {selectedCandidate.student_identifier}</div>
                              )}
                            </div>
                            <div className="grid grid-cols-1 gap-1 text-xs text-gray-600 sm:grid-cols-2">
                              {selectedCandidate.grade && <span>Grade: {selectedCandidate.grade}</span>}
                              {selectedCandidate.advisor && <span>Advisor: {selectedCandidate.advisor}</span>}
                              {selectedCandidate.house && <span>House: {selectedCandidate.house}</span>}
                              {selectedCandidate.clan && <span>Clan: {selectedCandidate.clan}</span>}
                            </div>
                            <div className="text-xs text-gray-600">
                              Tickets: {Number(selectedCandidate.tickets ?? 0).toFixed(2)} • Chance: {Number(selectedCandidate.probability ?? 0).toFixed(2)}%
                            </div>
                          </div>
                        ) : (
                          <div className="text-sm text-gray-500">Select a student to see their ticket details and student ID.</div>
                        )}
                      </div>
                    </div>
                    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                      <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                        <History className="h-4 w-4" />
                        Draw History
                      </div>
                      <div className="mt-3 text-sm">
                        {drawSummary?.history && drawSummary.history.length > 0 ? (
                          <div className="max-h-48 space-y-2 overflow-y-auto pr-1 text-xs text-gray-600">
                            {drawSummary.history
                              .slice()
                              .reverse()
                              .map((entry, index) => (
                                <div key={`${entry.timestamp}-${index}`} className="rounded border p-2">
                                  <div className="font-semibold uppercase">{entry.event_type.replace(/_/g, ' ')}</div>
                                  <div>When: {entry.timestamp ? new Date(entry.timestamp).toLocaleString() : 'N/A'}</div>
                                  {entry.student_name && <div>Student: {entry.student_name}</div>}
                                  {entry.tickets !== null && entry.tickets !== undefined && (
                                    <div>Student tickets: {Number(entry.tickets ?? 0).toFixed(2)}</div>
                                  )}
                                  {entry.probability !== null && entry.probability !== undefined && (
                                    <div>Probability: {Number(entry.probability ?? 0).toFixed(2)}%</div>
                                  )}
                                  {entry.pool_size !== null && entry.pool_size !== undefined && (
                                    <div>Eligible pool: {entry.pool_size}</div>
                                  )}
                                  {entry.created_by && <div>By: {entry.created_by}</div>}
                                </div>
                              ))}
                          </div>
                        ) : (
                          <div className="text-sm text-gray-500">No draw activity recorded yet.</div>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                    <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                      <ListOrdered className="h-4 w-4" />
                      Eligible Students
                    </div>
                    <div className="mt-3">
                      {drawSummary.candidates && drawSummary.candidates.length > 0 ? (
                        <div className="max-h-56 space-y-1 overflow-y-auto pr-1">
                          {drawSummary.candidates.map((candidate) => {
                            const isActive = selectedCandidateKey === candidate.key
                            return (
                              <button
                                key={candidate.key}
                                type="button"
                                onClick={() => setSelectedCandidateKey(candidate.key)}
                                className={`flex w-full items-center justify-between rounded border px-3 py-2 text-left transition ${
                                  isActive ? 'border-emerald-500 bg-emerald-50' : 'border-gray-200 hover:bg-gray-50'
                                }`}
                              >
                                <div>
                                  <div className="font-medium">{candidate.display_name}</div>
                                  <div className="flex flex-wrap gap-2 text-xs text-gray-500">
                                    {candidate.student_identifier && <span>ID: {candidate.student_identifier}</span>}
                                    <span>Tickets: {Number(candidate.tickets ?? 0).toFixed(2)}</span>
                                    <span>Chance: {Number(candidate.probability ?? 0).toFixed(2)}%</span>
                                  </div>
                                </div>
                                {candidate.key === currentDrawInfo?.winner?.key && (
                                  <Badge variant="outline" className="text-xs">Winner</Badge>
                                )}
                              </button>
                            )
                          })}
                        </div>
                      ) : (
                        <div className="text-sm text-gray-500">No eligible students yet.</div>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="py-8 text-center text-gray-500">
                  No draw data available yet. Record plate data to generate tickets.
                </div>
              )}
              </CardContent>
            )}
          </Card>
        </div>

        {/* Category Recording Buttons */}
        <div className="mt-8 space-y-4">
          {user?.role === 'guest' && (
            <Alert className="border-blue-200 bg-blue-50">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription className="text-blue-800">
                You are viewing as a guest. Recording is not available. Please sign up to record plate data.
              </AlertDescription>
            </Alert>
          )}
          
          <Button
            onClick={() => handleCategoryClick('clean')}
            className="w-full h-20 text-xl font-semibold bg-yellow-500 hover:bg-yellow-600 text-white shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={isLoading || user?.role === 'guest'}
          >
            🥇 CLEAN PLATE
            <br />
            <span className="text-sm opacity-90">({sessionStats.clean_count} recorded)</span>
          </Button>

          <Button
            onClick={() => handleCategoryClick('faculty')}
            className="w-full h-20 text-xl font-semibold bg-green-500 hover:bg-green-600 text-white shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={isLoading || user?.role === 'guest'}
          >
            🧑‍🏫 FACULTY CLEAN
            <br />
            <span className="text-sm opacity-90">({sessionStats.faculty_clean_count} recorded)</span>
          </Button>

          <Button
            onClick={() => handleCategoryClick('dirty')}
            className="w-full h-20 text-xl font-semibold bg-orange-500 hover:bg-orange-600 text-white shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={isLoading || user?.role === 'guest'}
          >
            🍽️ DIRTY PLATE COUNT
            <br />
            <span className="text-sm opacity-90">({sessionStats.dirty_count} total)</span>
          </Button>

          <Button
            onClick={() => handleCategoryClick('red')}
            className="w-full h-20 text-xl font-semibold bg-red-500 hover:bg-red-600 text-white shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={isLoading || user?.role === 'guest'}
          >
            🍝 VERY DIRTY PLATE
            <br />
            <span className="text-sm opacity-90">({sessionStats.red_count} recorded)</span>
          </Button>
        </div>

        {/* Scan History */}
        <div className="mt-8">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Plate Tracking History
              </CardTitle>
              <CardDescription>
                Recent plate cleanliness entries for this session
              </CardDescription>
            </CardHeader>
            <CardContent>
              {scanHistory.length > 0 ? (
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {scanHistory.map((record, index) => (
                    <div key={index} className="flex items-center justify-between p-2 border rounded-lg text-sm">
                      <div className="flex items-center gap-4">
                        <div className="text-gray-500">
                          {new Date(record.timestamp).toLocaleTimeString()}
                        </div>
                        <div className="font-medium">
                          {record.name}
                        </div>
                      </div>
                      <div className={`px-2 py-1 rounded text-xs font-medium ${
                        record.category === 'CLEAN' ? 'bg-yellow-100 text-yellow-800' :
                        record.category === 'DIRTY' ? 'bg-orange-100 text-orange-800' :
                        record.category === 'FACULTY' ? 'bg-green-100 text-green-800' :
                        'bg-red-100 text-red-800'
                      }`}>
                        {record.category === 'CLEAN' ? '🥇 CLEAN' :
                         record.category === 'DIRTY' ? '🍽️ DIRTY' :
                         record.category === 'FACULTY' ? '🧑‍🏫 FACULTY CLEAN' :
                         '🍝 VERY DIRTY'}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center text-gray-500 py-4">
                  No plate entries recorded yet
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Category Recording Dialogs */}
        <Dialog open={showCleanDialog} onOpenChange={setShowCleanDialog}>
          <DialogContent dismissOnOverlayClick={false}>
            <DialogHeader>
              <DialogTitle className="text-yellow-600">🥇 Record as CLEAN PLATE</DialogTitle>
              <DialogDescription>
                Enter Student ID or Name for clean plate tracking
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <SearchableNameInput
                placeholder="Student ID or Name (e.g., 12345 or John Smith)"
                value={popupInputValue}
                onChange={(value, meta) => {
                  setPopupInputValue(value)
                  if (!meta || meta.source !== 'selection') {
                    setPopupSelectedEntry(null)
                  }
                }}
                onSelectName={(entry) => {
                  const sanitized = sanitizeSelection(entry)
                  setPopupSelectedEntry(sanitized)
                }}
                onKeyPress={(e) => handleKeyPress(e, 'clean')}
                names={studentNames}
                autoFocus
              />
              <div className="flex gap-2">
                <Button onClick={() => { setShowCleanDialog(false); setPopupSelectedEntry(null) }} variant="outline" className="flex-1">
                  Cancel
                </Button>
                <Button 
                  onClick={() => handlePopupSubmit('clean')} 
                  className="flex-1 bg-yellow-500 hover:bg-yellow-600"
                  disabled={isLoading}
                >
                  Record as CLEAN PLATE
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        <Dialog open={showDirtyDialog} onOpenChange={setShowDirtyDialog}>
          <DialogContent dismissOnOverlayClick={false}>
            <DialogHeader>
              <DialogTitle className="text-orange-600">🍽️ Add DIRTY PLATE</DialogTitle>
              <DialogDescription>
                Increase the dirty plate counter without recording a name
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <p className="text-sm text-gray-600">
                This action adds one to the dirty plate count. No student information is stored.
              </p>
              <div className="flex gap-2">
                <Button onClick={() => { setShowDirtyDialog(false); setPopupSelectedEntry(null) }} variant="outline" className="flex-1">
                  Cancel
                </Button>
                <Button
                  onClick={() => handlePopupSubmit('dirty')}
                  className="flex-1 bg-orange-500 hover:bg-orange-600"
                  disabled={isLoading}
                >
                  Add Dirty Plate
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        <Dialog open={showFacultyDialog} onOpenChange={setShowFacultyDialog}>
          <DialogContent dismissOnOverlayClick={false}>
            <DialogHeader>
              <DialogTitle className="text-green-600">🧑‍🏫 Record FACULTY CLEAN PLATE</DialogTitle>
              <DialogDescription>
                Enter the faculty member's name for clean plate tracking
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <SearchableNameInput
                placeholder="Faculty Name (e.g., Alex Morgan)"
                value={popupInputValue}
                onChange={(value, meta) => {
                  setPopupInputValue(value)
                  if (!meta || meta.source !== 'selection') {
                    setPopupSelectedEntry(null)
                  }
                }}
                onSelectName={(entry) => {
                  const sanitized = sanitizeSelection(entry)
                  setPopupSelectedEntry(sanitized)
                }}
                onKeyPress={(e) => handleKeyPress(e, 'faculty')}
                names={teacherNames}
                autoFocus
              />
              <div className="flex gap-2">
                <Button onClick={() => { setShowFacultyDialog(false); setPopupSelectedEntry(null) }} variant="outline" className="flex-1">
                  Cancel
                </Button>
                <Button
                  onClick={() => handlePopupSubmit('faculty')}
                  className="flex-1 bg-green-500 hover:bg-green-600"
                  disabled={isLoading}
                >
                  Record Faculty Clean Plate
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        <Dialog open={showRedDialog} onOpenChange={setShowRedDialog}>
          <DialogContent dismissOnOverlayClick={false}>
            <DialogHeader>
              <DialogTitle className="text-red-600">🍝 Record as VERY DIRTY PLATE</DialogTitle>
              <DialogDescription>
                Enter Student ID or Name for very dirty plate tracking
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <SearchableNameInput
                placeholder="Student ID or Name (e.g., 12345 or John Smith)"
                value={popupInputValue}
                onChange={(value, meta) => {
                  setPopupInputValue(value)
                  if (!meta || meta.source !== 'selection') {
                    setPopupSelectedEntry(null)
                  }
                }}
                onSelectName={(entry) => {
                  const sanitized = sanitizeSelection(entry)
                  setPopupSelectedEntry(sanitized)
                }}
                onKeyPress={(e) => handleKeyPress(e, 'red')}
                names={studentNames}
                autoFocus
              />
              <div className="flex gap-2">
                <Button onClick={() => { setShowRedDialog(false); setPopupSelectedEntry(null) }} variant="outline" className="flex-1">
                  Cancel
                </Button>
                <Button 
                  onClick={() => handlePopupSubmit('red')} 
                  className="flex-1 bg-red-500 hover:bg-red-600"
                  disabled={isLoading}
                >
                  Record as VERY DIRTY PLATE
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* New Session Dialog */}
        <Dialog open={showNewSessionDialog} onOpenChange={setShowNewSessionDialog}>
          <DialogContent dismissOnOverlayClick={false}>
            <DialogHeader>
              <DialogTitle>Create New Session</DialogTitle>
              <DialogDescription>
                Enter a custom name or leave blank for default naming
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="session-name">Session Name (Optional)</Label>
                <Input
                  id="session-name"
                  type="text"
                  placeholder="Leave blank for default name"
                  value={customSessionName}
                  onChange={(e) => setCustomSessionName(e.target.value)}
                />
              </div>
              <div className="flex gap-2">
                <Button onClick={() => setShowNewSessionDialog(false)} variant="outline" className="flex-1">
                  Cancel
                </Button>
                <Button 
                  onClick={() => createSession(customSessionName)} 
                  className="flex-1 bg-blue-600 hover:bg-blue-700"
                  disabled={isLoading}
                >
                  Create Session
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation Dialog */}
        <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
          <DialogContent dismissOnOverlayClick={false}>
            <DialogHeader>
              <DialogTitle className="text-red-600">Delete Session</DialogTitle>
              <DialogDescription>
                Are you sure you want to delete this session? This action cannot be undone.
              </DialogDescription>
            </DialogHeader>
            {sessionToDelete && (
              <div className="bg-gray-50 p-4 rounded-lg">
                <div className="font-medium">{sessionToDelete.session_name}</div>
                <div className="text-sm text-gray-600">
                  {sessionToDelete.total_records} records will be permanently deleted
                </div>
              </div>
            )}
            <div className="flex gap-2">
              <Button 
                onClick={() => setShowDeleteConfirm(false)} 
                variant="outline" 
                className="flex-1"
              >
                Cancel
              </Button>
              <Button 
                onClick={() => deleteSession(sessionToDelete?.session_id)} 
                className="flex-1 bg-red-600 hover:bg-red-700"
                disabled={isLoading}
              >
                Delete Session
              </Button>
            </div>
          </DialogContent>
        </Dialog>



        {/* CSV Preview Dialog */}
        <Dialog open={showCsvPreview} onOpenChange={setShowCsvPreview}>
          <DialogContent
            className="w-full sm:max-w-2xl lg:max-w-3xl max-h-[75vh] overflow-y-auto"
            dismissOnOverlayClick={false}
          >
            <DialogHeader>
              <DialogTitle>Student Database Preview</DialogTitle>
              <DialogDescription>
                Current student database with pagination
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              {csvPreviewData && (
                <>
                  <div className="text-sm text-gray-600">
                    <p><strong>Total Records:</strong> {csvPreviewData.pagination.total_records}</p>
                    <p><strong>Uploaded by:</strong> {csvPreviewData.metadata.uploaded_by}</p>
                    <p><strong>Uploaded at:</strong> {new Date(csvPreviewData.metadata.uploaded_at).toLocaleString()}</p>
                  </div>
                  
                  <div className="border rounded-lg overflow-hidden">
                    <div className="max-h-96 overflow-auto">
                      <table className="min-w-full table-auto text-xs leading-tight">
                        <thead className="bg-gray-50 sticky top-0 z-10">
                          <tr>
                            {csvPreviewData.columns.map((column, index) => (
                              <th
                                key={index}
                                className="px-3 py-2 text-left font-semibold text-gray-700 border-b border-gray-200 whitespace-nowrap"
                              >
                                {column}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {csvPreviewData.data.map((row, index) => (
                            <tr
                              key={index}
                              className={`${index % 2 === 0 ? 'bg-white' : 'bg-gray-50'} border-b border-gray-100 last:border-b-0`}
                            >
                              {csvPreviewData.columns.map((column, colIndex) => (
                                <td
                                  key={colIndex}
                                  className="px-3 py-1.5 text-gray-700 align-top break-words"
                                >
                                  {row[column] || '-'}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                  
                  <div className="flex justify-between items-center">
                    <div className="text-sm text-gray-600">
                      Page {csvPreviewData.pagination.page} of {csvPreviewData.pagination.total_pages}
                      ({csvPreviewData.data.length} of {csvPreviewData.pagination.total_records} records)
                    </div>
                    <div className="flex gap-2">
                      <Button 
                        onClick={() => previewCSV(csvPreviewPage - 1)}
                        disabled={!csvPreviewData.pagination.has_prev || csvPreviewLoading}
                        variant="outline"
                        size="sm"
                      >
                        Previous
                      </Button>
                      <Button 
                        onClick={() => previewCSV(csvPreviewPage + 1)}
                        disabled={!csvPreviewData.pagination.has_next || csvPreviewLoading}
                        variant="outline"
                        size="sm"
                      >
                        Next
                      </Button>
                    </div>
                  </div>
                </>
              )}
            </div>
            <Button onClick={() => setShowCsvPreview(false)} className="w-full">
              Close
            </Button>
          </DialogContent>
        </Dialog>

        {/* Teacher Preview Dialog */}
        {showTeacherPreview && (
        <Dialog open={showTeacherPreview} onOpenChange={setShowTeacherPreview}>
          <DialogContent className="w-full sm:max-w-2xl lg:max-w-4xl max-h-[80vh] overflow-hidden" dismissOnOverlayClick={false}>
            <DialogHeader>
              <DialogTitle>Teacher List Preview</DialogTitle>
              <DialogDescription>
                Preview of the uploaded teacher names
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              {teacherPreviewLoading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="text-muted-foreground">Loading teacher list...</div>
                </div>
              ) : teacherPreviewData ? (
                <>
                  <div className="text-sm text-muted-foreground">
                    <p><strong>Total Teachers:</strong> {teacherPreviewData.pagination.total_records}</p>
                    <p><strong>Uploaded by:</strong> {teacherPreviewData.metadata.uploaded_by}</p>
                    <p><strong>Uploaded at:</strong> {new Date(teacherPreviewData.metadata.uploaded_at).toLocaleString()}</p>
                  </div>
                  
                  <div className="max-h-96 overflow-y-auto border rounded-lg">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 p-4">
                      {teacherPreviewData.data.map((teacher, index) => (
                        <div key={index} className="p-2 bg-gray-50 rounded text-sm">
                          {teacher.name}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-4">
                    <div className="text-sm text-muted-foreground">
                      Page {teacherPreviewData.pagination.page} of {teacherPreviewData.pagination.total_pages}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        onClick={() => previewTeachers(teacherPreviewPage - 1)}
                        disabled={!teacherPreviewData.pagination.has_prev || teacherPreviewLoading}
                        variant="outline"
                        size="sm"
                      >
                        Previous
                      </Button>
                      <Button
                        onClick={() => previewTeachers(teacherPreviewPage + 1)}
                        disabled={!teacherPreviewData.pagination.has_next || teacherPreviewLoading}
                        variant="outline"
                        size="sm"
                      >
                        Next
                      </Button>
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-center py-8">
                  <div className="text-muted-foreground">No teacher data available</div>
                </div>
              )}
            </div>
            <Button onClick={() => setShowTeacherPreview(false)} className="w-full">
              Close
            </Button>
          </DialogContent>
        </Dialog>
        )}

      {/* Dashboard Dialog */}
      <Dialog open={showDashboard} onOpenChange={setShowDashboard}>
        <DialogContent
          className="w-full sm:max-w-2xl lg:max-w-4xl max-h-[82vh] overflow-y-auto"
          dismissOnOverlayClick={false}
        >
          <DialogHeader>
            <DialogTitle className="text-purple-600">Session Dashboard</DialogTitle>
            <DialogDescription>
              Key metrics for the currently selected session.
            </DialogDescription>
          </DialogHeader>
          {!sessionId ? (
            <div className="py-12 text-center text-gray-500">
              No active session selected. Switch to a session to view dashboard insights.
            </div>
          ) : (
            <div className="space-y-6">
              {isSessionDiscarded && (
                <Alert variant="destructive">
                  <Ban className="h-4 w-4" />
                  <AlertDescription>
                    This session is discarded from draw calculations. Reinstate it to include ticket updates.
                  </AlertDescription>
                </Alert>
              )}

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm sm:col-span-2 lg:col-span-3">
                  <div className="text-sm text-gray-500">Session</div>
                  <div className="text-2xl font-semibold text-gray-900">{sessionName || 'Untitled session'}</div>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-gray-500">
                    <Badge variant={isSessionDiscarded ? 'destructive' : 'outline'}>
                      {isSessionDiscarded ? 'Discarded' : 'Active'}
                    </Badge>
                    {drawSummary?.generated_at && (
                      <span>Updated {new Date(drawSummary.generated_at).toLocaleString()}</span>
                    )}
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                  <div className="text-sm text-gray-500">Total records</div>
                  <div className="text-2xl font-semibold text-gray-900">
                    {sessionDashboardStats.totalRecorded.toLocaleString()}
                  </div>
                  <div className="mt-1 text-xs text-gray-500">
                    Includes faculty clean plates
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                  <div className="text-sm text-gray-500">Clean plates</div>
                  <div className="text-2xl font-semibold text-emerald-700">
                    {sessionDashboardStats.cleanCount.toLocaleString()}
                  </div>
                  <div className="mt-1 text-xs text-gray-500">
                    Clean rate {sessionDashboardStats.cleanPercentage.toFixed(1)}% • Includes faculty clean
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                  <div className="text-sm text-gray-500">Dirty plates</div>
                  <div className="text-2xl font-semibold text-orange-700">
                    {sessionDashboardStats.combinedDirty.toLocaleString()}
                  </div>
                  <div className="mt-1 text-xs text-gray-500">
                    Dirty rate {sessionDashboardStats.dirtyPercentage.toFixed(1)}% • Standard dirty {sessionDashboardStats.dirtyCount.toLocaleString()}
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                  <div className="text-sm text-gray-500">Very dirty plates</div>
                  <div className="text-2xl font-semibold text-red-700">
                    {sessionDashboardStats.redCount.toLocaleString()}
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                  <div className="text-sm text-gray-500">Faculty clean plates</div>
                  <div className="text-2xl font-semibold text-gray-900">
                    {sessionDashboardStats.facultyCount.toLocaleString()}
                  </div>
                </div>
              </div>

              <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                  <Trophy className="h-4 w-4" />
                  Current winner
                </div>
                <div className="mt-3 text-sm text-gray-700">
                  {dashboardWinner.winner ? (
                    <div className="space-y-2">
                      <div className="text-lg font-semibold text-gray-900">{dashboardWinner.winner.display_name}</div>
                      {dashboardWinner.winner.student_identifier && (
                        <div className="text-xs text-gray-500">Student ID: {dashboardWinner.winner.student_identifier}</div>
                      )}
                      <div className="flex flex-wrap gap-2 text-xs text-gray-500">
                        {dashboardWinner.winner.grade && <span>Grade: {dashboardWinner.winner.grade}</span>}
                        {dashboardWinner.winner.house && <span>House: {dashboardWinner.winner.house}</span>}
                        {dashboardWinner.winner.clan && <span>Clan: {dashboardWinner.winner.clan}</span>}
                      </div>
                      <div className="text-xs text-gray-500">
                        Status:{' '}
                        <Badge variant={dashboardWinner.finalized ? 'default' : 'outline'}>
                          {dashboardWinner.finalized ? 'Finalized' : 'Pending finalization'}
                        </Badge>
                        {dashboardWinner.override && (
                          <span className="ml-2 text-orange-600">Override</span>
                        )}
                      </div>
                      {dashboardWinner.timestamp && (
                        <div className="flex items-center gap-1 text-xs text-gray-500">
                          <Clock className="h-3 w-3" />
                          {dashboardWinner.timestamp.toLocaleString()}
                        </div>
                      )}
                      {(dashboardWinner.tickets !== null || dashboardWinner.probability !== null) && (
                        <div className="text-xs text-gray-500">
                          Tickets at selection: {dashboardWinner.tickets !== null ? Number(dashboardWinner.tickets).toFixed(2) : '—'} • Chance: {dashboardWinner.probability !== null ? Number(dashboardWinner.probability).toFixed(2) : '—'}%
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-gray-500">No winner selected yet.</div>
                  )}
                </div>
              </div>
            </div>
          )}

          <Button onClick={() => setShowDashboard(false)} className="w-full">
            Close
          </Button>
        </DialogContent>
      </Dialog>

        </>
        )}
      </div>
      
      {renderSchoolSignupDialog()}

      {/* Admin Panel Dialog */}
      <Dialog open={showAdminPanel} onOpenChange={setShowAdminPanel}>
        <DialogContent
          className="w-full sm:max-w-2xl lg:max-w-3xl max-h-[82vh] overflow-y-auto"
          dismissOnOverlayClick={false}
        >
          <DialogHeader>
            <DialogTitle className="text-red-600">Admin Panel</DialogTitle>
            <DialogDescription>
              System administration and management
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-6">
            <div className="flex gap-4">
              {canUseTenantAdminFeatures && (
                <>
                  <Button
                    onClick={generateInviteCode}
                    variant="outline"
                    className="flex-1"
                  >
                    <UserPlus className="h-4 w-4 mr-2" />
                    Generate Invite Code
                  </Button>
                  <Button
                    onClick={() => {
                      setShowDeleteRequests(true)
                      loadDeleteRequests()
                    }}
                    variant="outline"
                    className="relative flex-1"
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    Delete Requests
                    {deleteRequests.length > 0 && (
                      <span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs rounded-full px-2 py-0.5">
                        {deleteRequests.length}
                      </span>
                    )}
                  </Button>
                </>
              )}
            </div>

            <div>
              <h3 className="text-lg font-semibold mb-3">Users</h3>
              <div className="space-y-2">
                {adminUsers.map((adminUser) => (
                  <div key={adminUser.username} className="flex items-center justify-between p-3 border rounded-lg">
                    <div>
                      <div className="font-medium">{adminUser.name}</div>
                      <div className="text-sm text-gray-500">@{adminUser.username} • {adminUser.role}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={adminUser.role === 'superadmin' ? 'destructive' : adminUser.role === 'admin' ? 'default' : 'secondary'}
                      >
                        {adminUser.role}
                      </Badge>
                      {canUseTenantSuperAdminFeatures && adminUser.username !== user.username && (
                        <div className="flex gap-1">
                          <select
                            className="text-xs border rounded px-2 py-1"
                            value={adminUser.role}
                            onChange={(e) => changeUserRole(adminUser.username, e.target.value)}
                          >
                            <option value="user">User</option>
                            <option value="admin">Admin</option>
                            <option value="superadmin">Super Admin</option>
                          </select>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => {
                              setUserToDelete(adminUser)
                              setShowUserDeleteConfirm(true)
                            }}
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h3 className="text-lg font-semibold mb-3">All Sessions</h3>
              <div className="space-y-2 max-h-40 overflow-y-auto">
                {adminSessions.map((adminSession) => (
                  <div key={adminSession.session_id} className="flex items-center justify-between p-3 border rounded-lg">
                    <div>
                      <div className="font-medium flex items-center gap-2">
                        {adminSession.session_name}
                        {adminSession.is_discarded && (
                          <Badge variant="destructive" className="text-xs uppercase">Discarded</Badge>
                        )}
                      </div>
                      <div className="text-sm text-gray-500">
                        Owner: {adminSession.owner} • {adminSession.total_records} records • Faculty Clean: {adminSession.faculty_clean_count ?? 0}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <Button onClick={() => setShowAdminPanel(false)} className="w-full">
            Close
          </Button>
        </DialogContent>
      </Dialog>

      {/* Account Management Dialog */}
      <Dialog open={showAccountManagement} onOpenChange={setShowAccountManagement}>
        <DialogContent className="max-w-2xl" dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle>Account Management</DialogTitle>
            <DialogDescription>
              Manage user account status (enable/disable accounts)
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 max-h-96 overflow-y-auto">
            {allUsers.map((userAccount) => (
              <div key={userAccount.username} className="flex items-center justify-between p-3 border rounded-lg">
                <div>
                  <div className="font-medium">{userAccount.name}</div>
                  <div className="text-sm text-gray-500">
                    @{userAccount.username} • {userAccount.role}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge
                    variant={userAccount.status === 'active' ? 'default' : 'destructive'}
                  >
                    {userAccount.status}
                  </Badge>
                  {(
                    (canUseTenantSuperAdminFeatures && userAccount.username !== user.username) ||
                    (canUseTenantAdminFeatures &&
                      user.role === 'admin' &&
                      !['superadmin', 'school_super_admin', 'admin', 'global_admin'].includes(userAccount.role))
                  ) && (
                    <Button
                      onClick={() => toggleAccountStatus(userAccount.username, userAccount.status)}
                      variant={userAccount.status === 'active' ? 'destructive' : 'default'}
                      size="sm"
                    >
                      {userAccount.status === 'active' ? 'Disable' : 'Enable'}
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
          <Button onClick={() => setShowAccountManagement(false)} className="w-full">
            Close
          </Button>
        </DialogContent>
      </Dialog>

      <Dialog open={showUserDeleteConfirm} onOpenChange={setShowUserDeleteConfirm}>
        <DialogContent dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle>Confirm Account Deletion</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete account "{userToDelete?.username}"? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="flex gap-2 mt-4">
            <Button
              variant="destructive"
              onClick={() => {
                if (userToDelete) {
                  deleteUserAccount(userToDelete.username)
                }
                setShowUserDeleteConfirm(false)
                setUserToDelete(null)
              }}
            >
              Delete
            </Button>
            <Button variant="outline" onClick={() => { setShowUserDeleteConfirm(false); setUserToDelete(null) }}>
              Cancel
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Requests Dialog */}
      <Dialog open={showDeleteRequests} onOpenChange={setShowDeleteRequests}>
        <DialogContent className="max-w-2xl" dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle>Delete Requests</DialogTitle>
            <DialogDescription>
              Pending session deletion requests from users
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 max-h-96 overflow-y-auto">
            {deleteRequests.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                No pending delete requests
              </div>
            ) : (
              deleteRequests.map((request) => (
                <div key={request.id} className="flex items-center justify-between p-3 border rounded-lg">
                  <div>
                    <div className="font-medium">{request.session_name}</div>
                    <div className="text-sm text-gray-500">
                      Requested by: {request.requester_name} (@{request.requester}) • {request.total_records} records
                    </div>
                    <div className="text-xs text-gray-400">
                      Clean: {request.clean_records} • Dirty: {request.dirty_records} • Red: {request.red_records} • Faculty: {request.faculty_clean_records || 0}
                    </div>
                    <div className="text-xs text-gray-400">
                      {new Date(request.requested_at).toLocaleString()}
                    </div>
                  </div>
                  <div className="flex flex-col gap-2">
                    <Button
                      onClick={() => approveDeleteRequest(request.id)}
                      variant="destructive"
                      size="sm"
                    >
                      <Trash2 className="h-4 w-4 mr-1" />
                      Approve
                    </Button>
                    <Button
                      onClick={() => rejectDeleteRequest(request.id)}
                      variant="outline"
                      size="sm"
                    >
                      <XCircle className="h-4 w-4 mr-1" />
                      Reject
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
          <Button onClick={() => setShowDeleteRequests(false)} className="w-full">
            Close
          </Button>
        </DialogContent>
      </Dialog>

      {/* Switch Session Dialog - Moved outside of conditional rendering */}
      <Dialog open={showSessionsDialog} onOpenChange={setShowSessionsDialog}>
        <DialogContent dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle>Switch Session</DialogTitle>
            <DialogDescription>
              Select a session to switch to or delete sessions
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {sessions.map((session) => (
              <div key={session.session_id} className="flex items-center justify-between p-2 border rounded">
                <Button
                  variant="ghost"
                  onClick={() => switchSession(session.session_id)}
                  className="flex-1 justify-start"
                  disabled={session.session_id === sessionId}
                >
                    <div className="text-left">
                      <div className="font-medium">{session.session_name}</div>
                      {session.is_discarded && (
                        <Badge variant="destructive" className="mt-1 text-xs uppercase">Discarded</Badge>
                      )}
                      <div className="text-sm text-gray-500">
                        {session.total_records > 0 ? (
                          <>
                            🥇 {session.clean_count} ({session.clean_percentage}% incl. faculty) •
                            🍽️ {session.dirty_count} ({session.dirty_percentage}%) •
                            🧑‍🏫 {session.faculty_clean_count ?? 0}
                          </>
                        ) : (
                          'No records yet'
                        )}
                      </div>
                  </div>
                </Button>
                {sessionId && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setSessionToDelete(session)
                      setShowDeleteConfirm(true)
                    }}
                    className="text-red-600 hover:text-red-700 hover:bg-red-50"
                    disabled={session.delete_requested}
                    title={session.delete_requested ? 'Delete request pending' : 'Delete session'}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
            ))}
          </div>
          <Button onClick={() => setShowSessionsDialog(false)} className="w-full">
            Close
          </Button>
        </DialogContent>
      </Dialog>

      {notification && notification.size === 'small' &&
        createPortal(
          <div
            className={`fixed top-4 left-1/2 z-[2100] -translate-x-1/2 transform rounded px-4 py-2 text-white ${
              notification.type === 'success'
                ? 'bg-green-600'
                : notification.type === 'error'
                ? 'bg-red-600'
                : 'bg-blue-600'
            }`}
          >
            {notification.text}
          </div>,
          document.body
        )}

      {notification && notification.size === 'large' && (
        <Modal open onClose={() => setNotification(null)}>
          <p className="mb-4">{notification.text}</p>
          <Button onClick={() => setNotification(null)}>Close</Button>
        </Modal>
      )}

      {modal?.type === 'invite' && (
        <Modal
          open
          onClose={() => { setModal(null); setInviteCode('') }}
          dismissOnOverlayClick={false}
        >
          <h2 className="text-lg font-semibold mb-4">Invite Code</h2>
          <div className="flex items-center gap-2 mb-4">
            <Input value={inviteCode} readOnly className="flex-1" />
            <Button onClick={copyInviteCode}>
              Copy
            </Button>
          </div>
          <Button onClick={() => { setModal(null); setInviteCode('') }}>Close</Button>
        </Modal>
      )}
    </div>
  )
}

export default App

