import { useEffect, useMemo, useState } from 'react'
import { makeStudentKey, normalizeName, sanitizeSelection } from '@/lib/names.js'

const API_BASE = '/api'

export function usePlateApp() {
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
  const [signupSchoolCode, setSignupSchoolCode] = useState('')
  const [showSchoolRegistration, setShowSchoolRegistration] = useState(false)
  const [schoolEmail, setSchoolEmail] = useState('')
  const [schoolName, setSchoolName] = useState('')
  const [schoolCode, setSchoolCode] = useState('')
  const [schoolAdminUsername, setSchoolAdminUsername] = useState('')
  const [schoolAdminPassword, setSchoolAdminPassword] = useState('')
  const [schoolAdminDisplayName, setSchoolAdminDisplayName] = useState('')
  const [emailVerificationCode, setEmailVerificationCode] = useState('')
  const [emailVerified, setEmailVerified] = useState(false)
  const [verificationSent, setVerificationSent] = useState(false)
  const [verificationLoading, setVerificationLoading] = useState(false)
  const [guestSchoolCode, setGuestSchoolCode] = useState('')
  const [showGuestSchoolDialog, setShowGuestSchoolDialog] = useState(false)
  
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
  const [accountRequests, setAccountRequests] = useState([])
  const [showAccountRequests, setShowAccountRequests] = useState(false)
  const [accountRequestsLoading, setAccountRequestsLoading] = useState(false)
  
  // Popup states for each category
  const [showCleanDialog, setShowCleanDialog] = useState(false)
  const [showDirtyDialog, setShowDirtyDialog] = useState(false)
  const [showRedDialog, setShowRedDialog] = useState(false)
  const [showFacultyDialog, setShowFacultyDialog] = useState(false)
  const [popupInputValue, setPopupInputValue] = useState('')
  const [popupSelectedEntry, setPopupSelectedEntry] = useState(null)
  
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

  // Draw center state
  const [drawSummary, setDrawSummary] = useState(null)
  const [drawSummaryLoading, setDrawSummaryLoading] = useState(false)
  const [overrideInput, setOverrideInput] = useState('')
  const [overrideCandidate, setOverrideCandidate] = useState(null)
  const [selectedCandidateKey, setSelectedCandidateKey] = useState(null)
  const [drawActionLoading, setDrawActionLoading] = useState(false)
  const [discardLoading, setDiscardLoading] = useState(false)
  const [isDrawCenterCollapsed, setIsDrawCenterCollapsed] = useState(false)
  const [facultyPick, setFacultyPick] = useState(null)
  const [facultyPickLoading, setFacultyPickLoading] = useState(false)
  const [drawActionComment, setDrawActionComment] = useState('')

  // House stats state
  const [houseStats, setHouseStats] = useState(null)
  const [houseStatsLoading, setHouseStatsLoading] = useState(false)
  const [houseSortBy, setHouseSortBy] = useState('percentage') // 'count' or 'percentage'

  // Notification and modal states
  const [notification, setNotification] = useState(null)
  const [modal, setModal] = useState(null)
  const [inviteCode, setInviteCode] = useState('')
  const [latestSchoolInvites, setLatestSchoolInvites] = useState([])
  const [schoolInviteLoading, setSchoolInviteLoading] = useState(false)
  const [interschoolSchools, setInterschoolSchools] = useState([])
  const [interschoolInvites, setInterschoolInvites] = useState([])
  const [interschoolRegistrationRequests, setInterschoolRegistrationRequests] = useState([])
  const [interschoolOverviewLoading, setInterschoolOverviewLoading] = useState(false)

  const isSessionDiscarded = drawSummary?.is_discarded ?? sessionStats.is_discarded
  const currentDrawInfo = drawSummary?.draw_info ?? sessionStats.draw_info
  const canManageDraw = ['admin', 'superadmin'].includes(user?.role)
  const canOverrideWinner = user?.role === 'superadmin'
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

  // Derived flags
  const isInterschoolUser = user?.role === 'inter_school'

  useEffect(() => {
    if (!sessionId) {
      setFacultyPick(null)
    }
  }, [sessionId])

  const buildDrawActionPayload = () => {
    const trimmed = drawActionComment.trim()
    return trimmed ? { comment: trimmed } : {}
  }

  // Check authentication status on load
  useEffect(() => {
    checkAuthStatus()
  }, [])

  const showMessage = (text, type = 'info', size = 'small') => {
    setNotification({ text, type, size })
    if (size === 'small') {
      setTimeout(() => setNotification(null), 3000)
    }
  }

  const loadInterschoolOverview = async ({ silent = false } = {}) => {
    if (user?.role !== 'inter_school') {
      setInterschoolSchools([])
      setInterschoolInvites([])
      setInterschoolRegistrationRequests([])
      setInterschoolOverviewLoading(false)
      return
    }

    setInterschoolOverviewLoading(true)
    try {
      const response = await fetch(`${API_BASE}/interschool/overview`)
      let data = null
      try {
        data = await response.json()
      } catch (error) {
        data = null
      }

      if (response.ok) {
        setInterschoolSchools(Array.isArray(data?.schools) ? data.schools : [])
        setInterschoolInvites(Array.isArray(data?.invites) ? data.invites : [])
        setInterschoolRegistrationRequests(Array.isArray(data?.registration_requests) ? data.registration_requests : [])
      } else if (!silent) {
        const message = data?.error || 'Failed to load inter-school overview'
        showMessage(message, 'error')
      }
    } catch (error) {
      if (!silent) {
        showMessage('Failed to load inter-school overview', 'error')
      }
      setInterschoolSchools([])
      setInterschoolInvites([])
      setInterschoolRegistrationRequests([])
    } finally {
      setInterschoolOverviewLoading(false)
    }
  }

  const refreshInterschoolOverview = async () => {
    await loadInterschoolOverview({ silent: false })
  }

  const resetSchoolRegistrationForm = () => {
    setSchoolEmail('')
    setSchoolName('')
    setSchoolCode('')
    setSchoolAdminUsername('')
    setSchoolAdminPassword('')
    setSchoolAdminDisplayName('')
    setEmailVerificationCode('')
    setEmailVerified(false)
    setVerificationSent(false)
    setVerificationLoading(false)
  }

  const sendVerificationCode = async (recaptchaToken = null) => {
    const trimmedEmail = schoolEmail.trim().toLowerCase()

    if (!trimmedEmail) {
      showMessage('Please enter your email address', 'error')
      return false
    }

    if (!trimmedEmail.includes('@') || !trimmedEmail.includes('.')) {
      showMessage('Please enter a valid email address', 'error')
      return false
    }

    setVerificationLoading(true)
    try {
      const response = await fetch(`${API_BASE}/auth/send-verification-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: trimmedEmail,
          recaptcha_token: recaptchaToken,
        }),
      })

      const data = await response.json()

      if (response.ok) {
        setVerificationSent(true)
        showMessage('Verification code sent to your email!', 'success')
        return true
      } else {
        // Show detailed error if available (helps with debugging)
        const errorMsg = data.detail
          ? `${data.error} (${data.detail})`
          : data.error || 'Failed to send verification code'
        showMessage(errorMsg, 'error')
        console.error('Email verification error:', data)
        return false
      }
    } catch (error) {
      showMessage('Failed to send verification code. Please try again.', 'error')
      return false
    } finally {
      setVerificationLoading(false)
    }
  }

  const verifyEmailCode = async () => {
    const trimmedEmail = schoolEmail.trim().toLowerCase()
    const trimmedCode = emailVerificationCode.trim()

    if (!trimmedCode) {
      showMessage('Please enter the verification code', 'error')
      return false
    }

    if (trimmedCode.length !== 6) {
      showMessage('Verification code must be 6 digits', 'error')
      return false
    }

    setVerificationLoading(true)
    try {
      const response = await fetch(`${API_BASE}/auth/verify-email-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: trimmedEmail,
          code: trimmedCode,
        }),
      })

      const data = await response.json()

      if (response.ok && data.verified) {
        setEmailVerified(true)
        showMessage('Email verified successfully!', 'success')
        return true
      } else {
        showMessage(data.error || 'Invalid verification code', 'error')
        return false
      }
    } catch (error) {
      showMessage('Failed to verify code. Please try again.', 'error')
      return false
    } finally {
      setVerificationLoading(false)
    }
  }

  const initializeInterschoolPortal = async () => {
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
    setOverrideInput('')
    setOverrideCandidate(null)
    setSelectedCandidateKey(null)
    setStudentNames([])
    setTeacherNames([])
    setShowNewSessionDialog(false)
    setShowSessionsDialog(false)
    setShowDashboard(false)
    setShowDeleteConfirm(false)
    setSessionToDelete(null)
    setShowAdminPanel(false)
    setShowAccountManagement(false)
    setShowDeleteRequests(false)
    setShowUserDeleteConfirm(false)
    setUserToDelete(null)
    setShowCleanDialog(false)
    setShowDirtyDialog(false)
    setShowRedDialog(false)
    setShowFacultyDialog(false)
    setCsvPreviewData(null)
    setShowCsvPreview(false)
    setTeacherPreviewData(null)
    setShowTeacherPreview(false)
    setDrawActionLoading(false)
    setDiscardLoading(false)
    setIsDrawCenterCollapsed(false)
    setSchoolInviteLoading(false)
    setLatestSchoolInvites([])
    setInterschoolSchools([])
    setInterschoolInvites([])
    setInterschoolRegistrationRequests([])
    setInterschoolOverviewLoading(false)
    setShowGuestSchoolDialog(false)
    setGuestSchoolCode('')
    await loadInterschoolOverview({ silent: true })
  }

  const handlePostAuth = async (userPayload) => {
    if (!userPayload) {
      return
    }
    if (userPayload.role === 'inter_school') {
      await initializeInterschoolPortal()
    } else {
      await initializeSession()
    }
  }

  const checkAuthStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/status`)
      if (response.ok) {
        const data = await response.json()
        if (data.authenticated) {
          setUser(data.user)
          setIsAuthenticated(true)
          await handlePostAuth(data.user)
        }
      }
    } catch (error) {
      console.error('Auth check failed:', error)
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
        setUser(data.user)
        setIsAuthenticated(true)
        setLoginUsername('')
        setLoginPassword('')
        showMessage(`Welcome, ${data.user.name}!`, 'success')
        await handlePostAuth(data.user)
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
    const trimmedCode = guestSchoolCode.trim()
    if (!trimmedCode) {
      showMessage('Enter a school code to continue as guest', 'error')
      return
    }

    const payload = { school_code: trimmedCode, school_slug: trimmedCode }

    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/auth/guest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      const data = await response.json()
      if (response.ok) {
        setUser(data.user)
        setIsAuthenticated(true)
        showMessage('Welcome, Guest! You can view sessions but cannot create or modify them.', 'info')
        setGuestSchoolCode('')
        setShowGuestSchoolDialog(false)
        await handlePostAuth(data.user)
      } else {
        showMessage(data.error || 'Guest login failed', 'error')
      }
    } catch (error) {
      showMessage('Guest login failed. Please try again.', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const signup = async (recaptchaToken = null) => {
    if (!signupUsername.trim() || !signupPassword.trim() || !signupName.trim() || !signupSchoolCode.trim()) {
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
      const payload = {
        username: signupUsername.trim(),
        password: signupPassword.trim(),
        name: signupName.trim(),
        school_code: signupSchoolCode.trim()
      }

      if (recaptchaToken) {
        payload.recaptcha_token = recaptchaToken
      }

      const response = await fetch(`${API_BASE}/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      const data = await response.json()
      if (response.ok) {
        showMessage(data.message || 'Account request submitted! Please wait for approval.', 'success')
        setSignupUsername('')
        setSignupPassword('')
        setSignupName('')
        setSignupSchoolCode('')
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

  const registerSchool = async (recaptchaToken = null) => {
    const trimmedEmail = schoolEmail.trim()
    const trimmedSchoolName = schoolName.trim()
    const trimmedCode = schoolCode.trim()
    const trimmedAdminUsername = schoolAdminUsername.trim()
    const trimmedAdminDisplayName = schoolAdminDisplayName.trim()

    if (!trimmedEmail || !trimmedSchoolName || !trimmedAdminUsername || !schoolAdminPassword || !trimmedAdminDisplayName) {
      showMessage('Please complete all required fields', 'error')
      return
    }

    // Basic email validation
    if (!trimmedEmail.includes('@') || !trimmedEmail.includes('.')) {
      showMessage('Please enter a valid email address', 'error')
      return
    }

    if (trimmedAdminUsername.length < 3) {
      showMessage('Admin username must be at least 3 characters long', 'error')
      return
    }

    if (schoolAdminPassword.length < 6) {
      showMessage('Admin password must be at least 6 characters long', 'error')
      return
    }

    setIsLoading(true)
    try {
      const payload = {
        email: trimmedEmail,
        school_name: trimmedSchoolName,
        admin_username: trimmedAdminUsername,
        admin_password: schoolAdminPassword,
        admin_display_name: trimmedAdminDisplayName
      }

      if (trimmedCode) {
        payload.school_code = trimmedCode
        payload.school_slug = trimmedCode
      }

      if (recaptchaToken) {
        payload.recaptcha_token = recaptchaToken
      }

      const response = await fetch(`${API_BASE}/auth/register-school`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      const data = await response.json()
      if (response.ok) {
        showMessage(data.message || 'School registration request submitted! Please wait for approval.', 'success')
        setShowSchoolRegistration(false)
        resetSchoolRegistrationForm()
      } else {
        showMessage(data.error || 'Failed to submit registration request', 'error')
      }
    } catch (error) {
      showMessage('Failed to submit registration request. Please try again.', 'error')
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
      setDrawSummary(null)
      setStudentNames([])
      setTeacherNames([])
      setLatestSchoolInvites([])
      setSchoolInviteLoading(false)
      setInterschoolSchools([])
      setInterschoolInvites([])
      setInterschoolRegistrationRequests([])
      setInterschoolOverviewLoading(false)
      setShowGuestSchoolDialog(false)
      setGuestSchoolCode('')
      setShowSchoolRegistration(false)
      resetSchoolRegistrationForm()
      showMessage('Logged out successfully', 'info')
    } catch (error) {
      showMessage('Logout failed', 'error')
    }
  }

  const initializeSession = async () => {
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
        setFacultyPick(data.faculty_pick ?? null)
        await loadScanHistory()
        await loadStudentNames()
        await loadTeacherNames()
        await loadDrawSummary({ silent: true, sessionIdOverride: data.session_id, sessionNameOverride: data.session_name, isDiscarded: data.is_discarded })
        await loadHouseStats({ silent: true, sessionIdOverride: data.session_id })
      } else {
        const sessionsList = await loadSessions()
        if (sessionsList.length > 0) {
          await switchSession(sessionsList[0].session_id)
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
          setFacultyPick(null)
          setScanHistory([])
          setDrawSummary(null)
          setOverrideInput('')
          setOverrideCandidate(null)
          setSelectedCandidateKey(null)
          await loadStudentNames()
          await loadTeacherNames()
        }
      }
    } catch (error) {
      console.error('Session initialization failed:', error)
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
      setFacultyPick(null)
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
      setFacultyPick(null)
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

  const requestDeleteSession = async (targetSessionId) => {
    try {
      const response = await fetch(`${API_BASE}/session/request-delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: targetSessionId })
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

  const deleteSession = async (targetSessionId) => {
    setIsLoading(true)
    try {
      if (user?.role === 'admin' || user?.role === 'superadmin') {
        const response = await fetch(`${API_BASE}/session/delete/${targetSessionId}`, {
          method: 'DELETE'
        })
        const data = await response.json()
        if (response.ok) {
          showMessage(data.message, 'success')
          const updated = await loadSessions()
          if (data.deleted_session_id === targetSessionId) {
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
        await requestDeleteSession(targetSessionId)
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

  const recordEntry = async (category, entryInputValue = '', selectedEntry = null) => {
    const trimmedValue = entryInputValue.trim()
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

        setPopupInputValue('')
        setShowCleanDialog(false)
        setShowDirtyDialog(false)
        setShowRedDialog(false)
        setShowFacultyDialog(false)
        setPopupSelectedEntry(null)

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
        setFacultyPick(data.faculty_pick ?? null)
        nextSessionId = data.session_id ?? nextSessionId
        nextSessionName = data.session_name ?? nextSessionName
        if (data.is_discarded !== undefined) {
          nextIsDiscarded = data.is_discarded
        }
      }
    } catch (error) {
      console.error('Failed to refresh session status:', error)
    }

    await loadScanHistory()
    await loadStudentNames()
    await loadTeacherNames()
    await loadDrawSummary({
      silent: true,
      sessionIdOverride: nextSessionId,
      sessionNameOverride: nextSessionName,
      isDiscarded: nextIsDiscarded
    })
    await loadHouseStats({ silent: true, sessionIdOverride: nextSessionId })
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

  const loadHouseStats = async ({ silent = false, sessionIdOverride = null } = {}) => {
    const targetSessionId = sessionIdOverride || sessionId
    if (!targetSessionId) {
      setHouseStats(null)
      return
    }

    setHouseStatsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/session/${targetSessionId}/house-stats`)
      const data = await response.json()
      if (response.ok) {
        setHouseStats(data)
      } else {
        if (!silent) {
          showMessage(data.error || 'Failed to load house statistics', 'error')
        }
        setHouseStats(null)
      }
    } catch (error) {
      console.error('Failed to load house stats:', error)
      if (!silent) {
        showMessage('Failed to load house statistics', 'error')
      }
      setHouseStats(null)
    } finally {
      setHouseStatsLoading(false)
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
        history: summaryData.history ?? drawSummary?.history ?? [],
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

  const pickRandomFaculty = async () => {
    if (!sessionId) {
      showMessage('Select a session before picking a faculty name', 'error')
      return
    }

    if (isSessionDiscarded) {
      showMessage('Restore the session before picking a faculty name', 'error')
      return
    }

    if ((sessionStats.faculty_clean_count ?? 0) <= 0) {
      showMessage('Add at least one faculty record before picking a name', 'error')
      return
    }

    setFacultyPickLoading(true)
    try {
      const response = await fetch(`${API_BASE}/session/${sessionId}/faculty/pick`)
      const data = await response.json()

      if (response.ok) {
        const faculty = data.faculty || {}
        const preferred = normalizeName(faculty.preferred_name)
        const last = normalizeName(faculty.last_name)
        const displayName = (faculty.display_name || `${preferred} ${last}`.trim()).trim() || 'Faculty Member'

        setFacultyPick({
          preferred_name: preferred,
          last_name: last,
          display_name: displayName,
          recorded_at: faculty.recorded_at || null,
          recorded_by: faculty.recorded_by || null
        })
      } else {
        showMessage(data.error || 'Failed to pick a faculty name', 'error')
      }
    } catch (error) {
      showMessage('Failed to pick a faculty name', 'error')
    } finally {
      setFacultyPickLoading(false)
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
    if (studentRecordCount <= 0) {
      showMessage('Add at least one student record before starting a draw', 'error')
      return
    }
    setDrawActionLoading(true)
    try {
      const response = await fetch(`${API_BASE}/session/${sessionId}/draw/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildDrawActionPayload())
      })
      const data = await response.json()
      if (response.ok) {
        applyDrawResponse(data, { silent: true })
        if (data.winner?.display_name) {
          showMessage(`Winner selected: ${data.winner.display_name}`, 'success')
        } else {
          showMessage('Winner selected', 'success')
        }
        setDrawActionComment('')
        await loadDrawSummary({ silent: true })
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
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildDrawActionPayload())
      })
      const data = await response.json()
      if (response.ok) {
        applyDrawResponse(data, { silent: true })
        showMessage('Winner finalized', 'success')
        setDrawActionComment('')
        await loadDrawSummary({ silent: true })
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
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildDrawActionPayload())
      })
      const data = await response.json()
      if (response.ok) {
        applyDrawResponse(data, { silent: true })
        showMessage('Draw reset successfully', 'success')
        setDrawActionComment('')
        await loadDrawSummary({ silent: true })
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

    const { comment } = buildDrawActionPayload()
    if (comment) {
      payload.comment = comment
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
        setDrawActionComment('')
        await loadDrawSummary({ silent: true })
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
    if (!user || !['admin', 'superadmin'].includes(user.role)) return

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

  const loadAllUsers = async () => {
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
        loadAllUsers()
      } else {
        const error = await response.json()
        showMessage(error.error, 'error')
      }
    } catch (error) {
      showMessage('Failed to update account status', 'error')
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
        const updated = await loadSessions()
        loadDeleteRequests()
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
    if (['admin', 'superadmin'].includes(user?.role)) {
      loadDeleteRequests()
    }
  }, [user])

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

  const issueSchoolInvite = async () => {
    setSchoolInviteLoading(true)
    try {
      const response = await fetch(`${API_BASE}/interschool/school-invite`, { method: 'POST' })
      const data = await response.json()
      if (response.ok) {
        const inviteInfo = {
          code: data.invite_code,
          schoolId: data.school_id,
          issuedAt: new Date().toISOString()
        }
        setLatestSchoolInvites((prev) => [inviteInfo, ...prev].slice(0, 5))
        setModal({ type: 'school-invite', payload: inviteInfo })
        showMessage('School invite generated', 'success')
        await refreshInterschoolOverview()
      } else {
        showMessage(data.error || 'Failed to generate school invite', 'error')
      }
    } catch (error) {
      showMessage('Failed to generate school invite', 'error')
    } finally {
      setSchoolInviteLoading(false)
    }
  }

  const approveSchoolRegistration = async (requestId) => {
    try {
      const response = await fetch(`${API_BASE}/interschool/registration-requests/${requestId}/approve`, {
        method: 'POST'
      })

      if (response.ok) {
        const data = await response.json()
        showMessage(data.message, 'success')
        await refreshInterschoolOverview()
      } else {
        const error = await response.json()
        showMessage(error.error || 'Failed to approve registration request', 'error')
      }
    } catch (error) {
      showMessage('Failed to approve registration request', 'error')
    }
  }

  const rejectSchoolRegistration = async (requestId, reason = '') => {
    try {
      const response = await fetch(`${API_BASE}/interschool/registration-requests/${requestId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason })
      })

      if (response.ok) {
        const data = await response.json()
        showMessage(data.message, 'success')
        await refreshInterschoolOverview()
      } else {
        const error = await response.json()
        showMessage(error.error || 'Failed to reject registration request', 'error')
      }
    } catch (error) {
      showMessage('Failed to reject registration request', 'error')
    }
  }

  const deleteSchool = async (schoolId) => {
    try {
      const response = await fetch(`${API_BASE}/interschool/schools/${schoolId}`, {
        method: 'DELETE',
      })

      if (response.ok) {
        const data = await response.json()
        showMessage(data.message, 'success')
        await refreshInterschoolOverview()
      } else {
        const error = await response.json()
        showMessage(error.error || 'Failed to delete school', 'error')
      }
    } catch (error) {
      showMessage('Failed to delete school', 'error')
    }
  }

  const copyToClipboard = async (text, successMessage = 'Copied to clipboard') => {
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
      } else if (typeof document !== 'undefined') {
        const textarea = document.createElement('textarea')
        textarea.value = text
        textarea.setAttribute('readonly', '')
        textarea.style.position = 'absolute'
        textarea.style.left = '-9999px'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      showMessage(successMessage, 'success')
    } catch (error) {
      console.error('Copy failed:', error)
      showMessage('Failed to copy to clipboard', 'error')
    }
  }

  const copyInviteCode = () => {
    if (!inviteCode) {
      return
    }
    copyToClipboard(inviteCode, 'Invite code copied')
  }

  const copySchoolInvite = (invite, mode = 'code') => {
    if (!invite) {
      return
    }
    const content = mode === 'details'
      ? `Invite Code: ${invite.code}\nSchool ID: ${invite.schoolId}`
      : invite.code
    const message = mode === 'details' ? 'Invite details copied' : 'Invite code copied'
    copyToClipboard(content, message)
  }

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
        loadAllUsers()
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
        loadAllUsers()
        loadAdminData()
      } else {
        const error = await response.json()
        showMessage(error.error, 'error')
      }
    } catch (error) {
      showMessage('Failed to delete user account', 'error')
    }
  }

  const loadAccountRequests = async () => {
    if (user?.role !== 'superadmin') {
      setAccountRequests([])
      return
    }

    setAccountRequestsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/superadmin/account-requests`)
      if (response.ok) {
        const data = await response.json()
        setAccountRequests(data.requests || [])
      } else {
        const error = await response.json()
        showMessage(error.error || 'Failed to load account requests', 'error')
      }
    } catch (error) {
      showMessage('Failed to load account requests', 'error')
      setAccountRequests([])
    } finally {
      setAccountRequestsLoading(false)
    }
  }

  const loadPendingAccountRequests = async () => {
    if (user?.role !== 'superadmin') {
      setAccountRequests([])
      return
    }

    setAccountRequestsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/superadmin/account-requests/pending`)
      if (response.ok) {
        const data = await response.json()
        setAccountRequests(data.requests || [])
      } else {
        const error = await response.json()
        showMessage(error.error || 'Failed to load pending account requests', 'error')
      }
    } catch (error) {
      showMessage('Failed to load pending account requests', 'error')
      setAccountRequests([])
    } finally {
      setAccountRequestsLoading(false)
    }
  }

  const approveAccountRequest = async (requestId) => {
    try {
      const response = await fetch(`${API_BASE}/superadmin/account-requests/${requestId}/approve`, {
        method: 'POST'
      })

      if (response.ok) {
        const data = await response.json()
        showMessage(data.message, 'success')
        loadAccountRequests()
        loadAllUsers()
        loadAdminData()
      } else {
        const error = await response.json()
        showMessage(error.error, 'error')
      }
    } catch (error) {
      showMessage('Failed to approve account request', 'error')
    }
  }

  const rejectAccountRequest = async (requestId, reason = '') => {
    try {
      const response = await fetch(`${API_BASE}/superadmin/account-requests/${requestId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason })
      })

      if (response.ok) {
        const data = await response.json()
        showMessage(data.message, 'success')
        loadAccountRequests()
      } else {
        const error = await response.json()
        showMessage(error.error, 'error')
      }
    } catch (error) {
      showMessage('Failed to reject account request', 'error')
    }
  }

  return {
    // state
    user,
    setUser,
    isAuthenticated,
    setIsAuthenticated,
    loginUsername,
    setLoginUsername,
    loginPassword,
    setLoginPassword,
    showLoginDialog,
    setShowLoginDialog,
    showSignupDialog,
    setShowSignupDialog,
    signupUsername,
    setSignupUsername,
    signupPassword,
    setSignupPassword,
    signupName,
    setSignupName,
    signupSchoolCode,
    setSignupSchoolCode,
    showSchoolRegistration,
    setShowSchoolRegistration,
    schoolEmail,
    setSchoolEmail,
    schoolName,
    setSchoolName,
    schoolCode,
    setSchoolCode,
    schoolAdminUsername,
    setSchoolAdminUsername,
    schoolAdminPassword,
    setSchoolAdminPassword,
    schoolAdminDisplayName,
    setSchoolAdminDisplayName,
    emailVerificationCode,
    setEmailVerificationCode,
    emailVerified,
    setEmailVerified,
    verificationSent,
    setVerificationSent,
    verificationLoading,
    sendVerificationCode,
    verifyEmailCode,
    sessionId,
    setSessionId,
    sessionName,
    setSessionName,
    customSessionName,
    setCustomSessionName,
    sessions,
    setSessions,
    csvData,
    setCsvData,
    inputValue,
    setInputValue,
    scanHistory,
    setScanHistory,
    sessionStats,
    setSessionStats,
    isLoading,
    setIsLoading,
    showNewSessionDialog,
    setShowNewSessionDialog,
    showSessionsDialog,
    setShowSessionsDialog,
    showDashboard,
    setShowDashboard,
    showDeleteConfirm,
    setShowDeleteConfirm,
    sessionToDelete,
    setSessionToDelete,
    showAdminPanel,
    setShowAdminPanel,
    showAccountManagement,
    setShowAccountManagement,
    showDeleteRequests,
    setShowDeleteRequests,
    showUserDeleteConfirm,
    setShowUserDeleteConfirm,
    userToDelete,
    setUserToDelete,
    allUsers,
    setAllUsers,
    deleteRequests,
    setDeleteRequests,
    accountRequests,
    setAccountRequests,
    showAccountRequests,
    setShowAccountRequests,
    accountRequestsLoading,
    setAccountRequestsLoading,
    showCleanDialog,
    setShowCleanDialog,
    showDirtyDialog,
    setShowDirtyDialog,
    showRedDialog,
    setShowRedDialog,
    showFacultyDialog,
    setShowFacultyDialog,
    popupInputValue,
    setPopupInputValue,
    popupSelectedEntry,
    setPopupSelectedEntry,
    adminUsers,
    setAdminUsers,
    adminSessions,
    setAdminSessions,
    showCsvPreview,
    setShowCsvPreview,
    csvPreviewData,
    setCsvPreviewData,
    csvPreviewPage,
    setCsvPreviewPage,
    csvPreviewLoading,
    setCsvPreviewLoading,
    studentNames,
    setStudentNames,
    teacherNames,
    setTeacherNames,
    showTeacherPreview,
    setShowTeacherPreview,
    teacherPreviewData,
    setTeacherPreviewData,
    teacherPreviewPage,
    setTeacherPreviewPage,
    teacherPreviewLoading,
    setTeacherPreviewLoading,
    drawSummary,
    setDrawSummary,
    drawSummaryLoading,
    setDrawSummaryLoading,
    overrideInput,
    setOverrideInput,
    overrideCandidate,
    setOverrideCandidate,
    selectedCandidateKey,
    setSelectedCandidateKey,
    drawActionLoading,
    setDrawActionLoading,
    discardLoading,
    setDiscardLoading,
    isDrawCenterCollapsed,
    setIsDrawCenterCollapsed,
    facultyPick,
    setFacultyPick,
    facultyPickLoading,
    setFacultyPickLoading,
    notification,
    setNotification,
    modal,
    setModal,
    inviteCode,
    setInviteCode,
    latestSchoolInvites,
    setLatestSchoolInvites,
    schoolInviteLoading,
    setSchoolInviteLoading,
    interschoolSchools,
    setInterschoolSchools,
    interschoolInvites,
    setInterschoolInvites,
    interschoolRegistrationRequests,
    setInterschoolRegistrationRequests,
    interschoolOverviewLoading,
    setInterschoolOverviewLoading,

    // computed
    isSessionDiscarded,
    currentDrawInfo,
    canManageDraw,
    canOverrideWinner,
    studentRecordCount,
    hasStudentRecords,
    showExportCard,
    drawActionComment,
    selectedCandidate,
    overrideOptions,
    sessionDashboardStats,
    dashboardWinner,
    isInterschoolUser,
    houseStats,
    houseStatsLoading,
    houseSortBy,

    // actions
    checkAuthStatus,
    login,
    guestLogin,
    guestSchoolCode,
    setGuestSchoolCode,
    showGuestSchoolDialog,
    setShowGuestSchoolDialog,
    signup,
    registerSchool,
    logout,
    initializeSession,
    initializeInterschoolPortal,
    handlePostAuth,
    createSession,
    loadSessions,
    switchSession,
    deleteSession,
    uploadCSV,
    uploadTeachers,
    previewCSV,
    previewTeachers,
    recordEntry,
    refreshSessionStatus,
    loadScanHistory,
    loadStudentNames,
    loadTeacherNames,
    updateDrawSummaryState,
    loadDrawSummary,
    applyDrawResponse,
    setDrawActionComment,
    pickRandomFaculty,
    startDrawProcess,
    finalizeDrawWinner,
    resetDrawWinner,
    overrideDrawWinner,
    toggleDiscardState,
    exportCSV,
    exportDetailedCSV,
    loadAdminData,
    showMessage,
    handleCategoryClick,
    handlePopupSubmit,
    handleKeyPress,
    loadAllUsers,
    toggleAccountStatus,
    requestDeleteSession,
    loadDeleteRequests,
    approveDeleteRequest,
    rejectDeleteRequest,
    generateInviteCode,
    issueSchoolInvite,
    approveSchoolRegistration,
    rejectSchoolRegistration,
    deleteSchool,
    refreshInterschoolOverview,
    copyToClipboard,
    copyInviteCode,
    copySchoolInvite,
    changeUserRole,
    deleteUserAccount,
    loadAccountRequests,
    loadPendingAccountRequests,
    approveAccountRequest,
    rejectAccountRequest,
    sanitizeSelection,
    resetSchoolRegistrationForm,
    loadHouseStats,
    setHouseSortBy
  }
}
