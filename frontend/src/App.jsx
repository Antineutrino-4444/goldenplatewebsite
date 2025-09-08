import React, { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Alert, AlertDescription } from '@/components/ui/alert.jsx'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog.jsx'
import { Upload, Scan, Download, FileText, CheckCircle, AlertCircle, Plus, Users, BarChart3, LogOut, Shield, Settings, Trash2, UserPlus } from 'lucide-react'
import './App.css'

const API_BASE = '/api'

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
    total_recorded: 0, 
    clean_percentage: 0, 
    dirty_percentage: 0 
  })
  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState('info')
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
  
  // Account management state
  const [allUsers, setAllUsers] = useState([])
  const [deleteRequests, setDeleteRequests] = useState([])
  
  // Popup states for each category
  const [showCleanDialog, setShowCleanDialog] = useState(false)
  const [showDirtyDialog, setShowDirtyDialog] = useState(false)
  const [showRedDialog, setShowRedDialog] = useState(false)
  const [popupInputValue, setPopupInputValue] = useState('')
  
  // Admin panel state
  const [adminUsers, setAdminUsers] = useState([])
  const [adminSessions, setAdminSessions] = useState([])
  
  // CSV preview state
  const [showCsvPreview, setShowCsvPreview] = useState(false)
  const [csvPreviewData, setCsvPreviewData] = useState(null)
  const [csvPreviewPage, setCsvPreviewPage] = useState(1)
  const [csvPreviewLoading, setCsvPreviewLoading] = useState(false)

  // Check authentication status on load
  useEffect(() => {
    checkAuthStatus()
  }, [])

  const checkAuthStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/status`)
      if (response.ok) {
        const data = await response.json()
        if (data.authenticated) {
          setUser(data.user)
          setIsAuthenticated(true)
          await initializeSession()
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
        await initializeSession()
      } else {
        showMessage(data.error || 'Login failed', 'error')
      }
    } catch (error) {
      showMessage('Login failed. Please try again.', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const signup = async () => {
    if (!signupUsername.trim() || !signupPassword.trim() || !signupName.trim()) {
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
          name: signupName.trim()
        })
      })

      const data = await response.json()
      if (response.ok) {
        showMessage('Account created successfully! Please login.', 'success')
        setSignupUsername('')
        setSignupPassword('')
        setSignupName('')
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
      setSessionStats({ clean_count: 0, dirty_count: 0, red_count: 0 })
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
          total_recorded: data.total_recorded,
          clean_percentage: data.clean_percentage,
          dirty_percentage: data.dirty_percentage
        })
        // Load scan history for the session
        await loadScanHistory()
      } else {
        // No active session, create one
        await createSession()
      }
    } catch (error) {
      console.error('Session initialization failed:', error)
      await createSession()
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
        setSessionStats({ clean_count: 0, dirty_count: 0, red_count: 0, combined_dirty_count: 0, total_recorded: 0, clean_percentage: 0, dirty_percentage: 0 })
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
        setSessions(data.sessions || [])
      }
    } catch (error) {
      console.error('Failed to load sessions:', error)
    }
  }

  const switchSession = async (sessionId) => {
    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/session/switch/${sessionId}`, {
        method: 'POST'
      })

      const data = await response.json()
      if (response.ok) {
        setSessionId(sessionId)
        setSessionName(data.session_name)
        await refreshSessionStatus()
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
      // Use the new request system instead of direct deletion
      await requestDeleteSession(sessionId)
      setShowDeleteConfirm(false)
      setSessionToDelete(null)
    } catch (error) {
      showMessage('Failed to process delete request', 'error')
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
      } else {
        showMessage(data.error || 'Failed to upload CSV', 'error')
      }
    } catch (error) {
      showMessage('Failed to upload CSV', 'error')
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

  const recordStudent = async (category, inputValue) => {
    if (!inputValue.trim()) {
      showMessage('Please enter a Student ID or Name', 'error')
      return
    }

    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/record/${category}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input_value: inputValue.trim() })
      })

      const data = await response.json()
      if (response.ok) {
        const displayName = `${data.first_name} ${data.last_name}`.trim()
        const idInfo = data.is_manual_entry ? 'Manual Input' : data.student_id
        showMessage(`${displayName} recorded as ${category.toUpperCase()} (${idInfo})`, 'success')
        
        // Clear input and close dialog
        setPopupInputValue('')
        setShowCleanDialog(false)
        setShowDirtyDialog(false)
        setShowRedDialog(false)
        
        // Refresh session status
        await refreshSessionStatus()
      } else {
        if (data.error === 'duplicate') {
          showMessage(data.message, 'error')
        } else {
          showMessage(data.error || 'Failed to record student', 'error')
        }
      }
    } catch (error) {
      showMessage('Failed to record student', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const refreshSessionStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/session/status`)
      if (response.ok) {
        const data = await response.json()
        setSessionStats({
          clean_count: data.clean_count,
          dirty_count: data.dirty_count,
          red_count: data.red_count,
          combined_dirty_count: data.combined_dirty_count,
          total_recorded: data.total_recorded,
          clean_percentage: data.clean_percentage,
          dirty_percentage: data.dirty_percentage
        })
      }
    } catch (error) {
      console.error('Failed to refresh session status:', error)
    }
    
    // Also load scan history
    await loadScanHistory()
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

  const showMessage = (text, type = 'info') => {
    setMessage(text)
    setMessageType(type)
    setTimeout(() => setMessage(''), 5000)
  }

  const handleCategoryClick = (category) => {
    if (category === 'clean') setShowCleanDialog(true)
    else if (category === 'dirty') setShowDirtyDialog(true)
    else if (category === 'red') setShowRedDialog(true)
  }

  const handlePopupSubmit = (category) => {
    recordStudent(category, popupInputValue)
  }

  const handleKeyPress = (e, category) => {
    if (e.key === 'Enter') {
      handlePopupSubmit(category)
    }
  }

  // Account management functions
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
        if (user.role === 'user') {
          // For normal users, refresh sessions list to remove deleted session
          loadSessions()
        }
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
        setDeleteRequests(data.requests || [])
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
        loadDeleteRequests() // Refresh delete requests
        loadSessions() // Refresh sessions list
      } else {
        const error = await response.json()
        showMessage(error.error, 'error')
      }
    } catch (error) {
      showMessage('Failed to approve delete request', 'error')
    }
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
            
            <div className="text-center">
              <Button 
                variant="link" 
                onClick={() => setShowSignupDialog(true)}
                className="text-amber-600 hover:text-amber-700"
              >
                Don't have an account? Sign up
              </Button>
            </div>

            {message && (
              <Alert className={messageType === 'error' ? 'border-red-200 bg-red-50' : messageType === 'success' ? 'border-green-200 bg-green-50' : 'border-blue-200 bg-blue-50'}>
                <AlertCircle className="h-4 w-4" />
                <AlertDescription className={messageType === 'error' ? 'text-red-800' : messageType === 'success' ? 'text-green-800' : 'text-blue-800'}>
                  {message}
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>

        {/* Signup Dialog */}
        <Dialog open={showSignupDialog} onOpenChange={setShowSignupDialog}>
          <DialogContent>
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
        {/* Session Info */}
        <div className="mb-6 text-center">
          <div className="text-lg font-medium text-gray-900">
            Session: {sessionName}
          </div>
          <div className="text-sm text-gray-500">
            Total: {sessionStats.clean_count + sessionStats.dirty_count + sessionStats.red_count}
          </div>
        </div>

        {/* Success/Error Messages */}
        {message && (
          <Alert className={`mb-6 ${messageType === 'error' ? 'border-red-200 bg-red-50' : messageType === 'success' ? 'border-green-200 bg-green-50' : 'border-blue-200 bg-blue-50'}`}>
            <CheckCircle className="h-4 w-4" />
            <AlertDescription className={messageType === 'error' ? 'text-red-800' : messageType === 'success' ? 'text-green-800' : 'text-blue-800'}>
              {message}
            </AlertDescription>
          </Alert>
        )}

        {/* Navigation Buttons */}
        <div className="flex flex-wrap gap-2 mb-6 justify-center">
          <Button onClick={() => setShowNewSessionDialog(true)} className="bg-blue-600 hover:bg-blue-700">
            <Plus className="h-4 w-4 mr-2" />
            New Session
          </Button>
          <Button onClick={() => { loadSessions(); setShowSessionsDialog(true) }} className="bg-orange-600 hover:bg-orange-700">
            <Users className="h-4 w-4 mr-2" />
            Switch Session
          </Button>
          {user.role !== 'user' && (
            <Button onClick={() => { loadAdminData(); setShowDashboard(true) }} className="bg-purple-600 hover:bg-purple-700">
              <BarChart3 className="h-4 w-4 mr-2" />
              Dashboard
            </Button>
          )}
          {['admin', 'superadmin'].includes(user.role) && (
            <Button onClick={() => { loadAdminData(); setShowAdminPanel(true) }} className="bg-red-600 hover:bg-red-700">
              <Shield className="h-4 w-4 mr-2" />
              Admin Panel
            </Button>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Student Database */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Upload className="h-5 w-5" />
                Student Database
              </CardTitle>
              <CardDescription>
                Upload CSV with student data for food waste tracking (Last, First, Student ID)
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Input
                type="file"
                accept=".csv"
                onChange={(e) => e.target.files[0] && uploadCSV(e.target.files[0])}
                className="mb-4"
              />
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
              {csvData && (
                <div className="text-sm text-green-600">
                  ✓ {csvData.rows_count} students loaded
                </div>
              )}
            </CardContent>
          </Card>

          {/* Export Records */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Download className="h-5 w-5" />
                Export Food Waste Data
              </CardTitle>
              <CardDescription>
                Download plate cleanliness records by category (Clean, Dirty, Very Dirty)
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button onClick={exportCSV} className="w-full bg-amber-600 hover:bg-amber-700">
                <Download className="h-4 w-4 mr-2" />
                Export Food Waste Data
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Category Recording Buttons */}
        <div className="mt-8 space-y-4">
          <Button
            onClick={() => handleCategoryClick('clean')}
            className="w-full h-20 text-xl font-semibold bg-yellow-500 hover:bg-yellow-600 text-white shadow-lg"
            disabled={isLoading}
          >
            🥇 CLEAN PLATE
            <br />
            <span className="text-sm opacity-90">({sessionStats.clean_count} recorded)</span>
          </Button>

          <Button
            onClick={() => handleCategoryClick('dirty')}
            className="w-full h-20 text-xl font-semibold bg-orange-500 hover:bg-orange-600 text-white shadow-lg"
            disabled={isLoading}
          >
            🍽️ DIRTY PLATE
            <br />
            <span className="text-sm opacity-90">({sessionStats.dirty_count} recorded)</span>
          </Button>

          <Button
            onClick={() => handleCategoryClick('red')}
            className="w-full h-20 text-xl font-semibold bg-red-500 hover:bg-red-600 text-white shadow-lg"
            disabled={isLoading}
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
                        <div className="text-gray-600">
                          ID: {record.student_id}
                        </div>
                      </div>
                      <div className={`px-2 py-1 rounded text-xs font-medium ${
                        record.category === 'CLEAN' ? 'bg-yellow-100 text-yellow-800' :
                        record.category === 'DIRTY' ? 'bg-orange-100 text-orange-800' :
                        'bg-red-100 text-red-800'
                      }`}>
                        {record.category === 'CLEAN' ? '🥇 CLEAN' : 
                         record.category === 'DIRTY' ? '🍽️ DIRTY' : 
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
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="text-yellow-600">🥇 Record as CLEAN PLATE</DialogTitle>
              <DialogDescription>
                Enter Student ID or Name for clean plate tracking
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <Input
                type="text"
                placeholder="Student ID or Name (e.g., 12345 or John Smith)"
                value={popupInputValue}
                onChange={(e) => setPopupInputValue(e.target.value)}
                onKeyPress={(e) => handleKeyPress(e, 'clean')}
                autoFocus
              />
              <div className="flex gap-2">
                <Button onClick={() => setShowCleanDialog(false)} variant="outline" className="flex-1">
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
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="text-orange-600">🍽️ Record as DIRTY PLATE</DialogTitle>
              <DialogDescription>
                Enter Student ID or Name for dirty plate tracking
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <Input
                type="text"
                placeholder="Student ID or Name (e.g., 12345 or John Smith)"
                value={popupInputValue}
                onChange={(e) => setPopupInputValue(e.target.value)}
                onKeyPress={(e) => handleKeyPress(e, 'dirty')}
                autoFocus
              />
              <div className="flex gap-2">
                <Button onClick={() => setShowDirtyDialog(false)} variant="outline" className="flex-1">
                  Cancel
                </Button>
                <Button 
                  onClick={() => handlePopupSubmit('dirty')} 
                  className="flex-1 bg-orange-500 hover:bg-orange-600"
                  disabled={isLoading}
                >
                  Record as DIRTY PLATE
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        <Dialog open={showRedDialog} onOpenChange={setShowRedDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="text-red-600">🍝 Record as VERY DIRTY PLATE</DialogTitle>
              <DialogDescription>
                Enter Student ID or Name for very dirty plate tracking
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <Input
                type="text"
                placeholder="Student ID or Name (e.g., 12345 or John Smith)"
                value={popupInputValue}
                onChange={(e) => setPopupInputValue(e.target.value)}
                onKeyPress={(e) => handleKeyPress(e, 'red')}
                autoFocus
              />
              <div className="flex gap-2">
                <Button onClick={() => setShowRedDialog(false)} variant="outline" className="flex-1">
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
          <DialogContent>
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

        {/* Switch Session Dialog */}
        <Dialog open={showSessionsDialog} onOpenChange={setShowSessionsDialog}>
          <DialogContent>
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
                      <div className="text-sm text-gray-500">
                        {session.total_records > 0 ? (
                          <>
                            🥇 {session.clean_count} ({session.clean_percentage}%) • 
                            🍽️ {session.dirty_count} ({session.dirty_percentage}%)
                          </>
                        ) : (
                          'No records yet'
                        )}
                      </div>
                    </div>
                  </Button>
                  {session.session_id !== sessionId && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setSessionToDelete(session)
                        setShowDeleteConfirm(true)
                      }}
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
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

        {/* Delete Confirmation Dialog */}
        <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
          <DialogContent>
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

        {/* Dashboard Dialog */}
        <Dialog open={showDashboard} onOpenChange={setShowDashboard}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Dashboard</DialogTitle>
              <DialogDescription>
                Session overview and system statistics
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="text-center p-4 bg-yellow-50 rounded-lg">
                  <div className="text-2xl font-bold text-yellow-600">{sessionStats.clean_count}</div>
                  <div className="text-sm text-yellow-700">🥇 Clean Plates</div>
                  <div className="text-xs text-yellow-600">
                    {sessionStats.clean_percentage || 0}%
                  </div>
                </div>
                <div className="text-center p-4 bg-orange-50 rounded-lg">
                  <div className="text-2xl font-bold text-orange-600">{sessionStats.combined_dirty_count || (sessionStats.dirty_count + sessionStats.red_count)}</div>
                  <div className="text-sm text-orange-700">🍽️ Dirty Plates</div>
                  <div className="text-xs text-orange-600">
                    {sessionStats.dirty_percentage || 0}%
                  </div>
                </div>
              </div>
              <div className="text-center p-4 bg-blue-50 rounded-lg">
                <div className="text-2xl font-bold text-blue-600">
                  {sessionStats.total_recorded || (sessionStats.clean_count + sessionStats.dirty_count + sessionStats.red_count)}
                </div>
                <div className="text-sm text-blue-700">Total Records</div>
              </div>
            </div>
            <Button onClick={() => setShowDashboard(false)} className="w-full">
              Close
            </Button>
          </DialogContent>
        </Dialog>

        {/* Admin Panel Dialog */}
        <Dialog open={showAdminPanel} onOpenChange={setShowAdminPanel}>
          <DialogContent className="max-w-4xl">
            <DialogHeader>
              <DialogTitle className="text-red-600">Admin Panel</DialogTitle>
              <DialogDescription>
                System administration and management
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-6">
              <div className="flex gap-4">
                {user.role === 'admin' || user.role === 'superadmin' ? (
                  <Button 
                    onClick={() => {
                      setShowDeleteRequests(true)
                      loadDeleteRequests()
                    }}
                    variant="outline"
                    className="flex-1"
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    Delete Requests ({deleteRequests.length})
                  </Button>
                ) : null}
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
                        {user.role === 'superadmin' && adminUser.username !== user.username && (
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
                                if (confirm(`Are you sure you want to delete account "${adminUser.username}"? This action cannot be undone.`)) {
                                  deleteUserAccount(adminUser.username)
                                }
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
                        <div className="font-medium">{adminSession.session_name}</div>
                        <div className="text-sm text-gray-500">
                          Owner: {adminSession.owner} • {adminSession.total_records} records
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
          <DialogContent className="max-w-2xl">
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
                    {((user.role === 'superadmin' && userAccount.username !== user.username) ||
                      (user.role === 'admin' && !['superadmin', 'admin'].includes(userAccount.role))) && (
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

        {/* Delete Requests Dialog */}
        <Dialog open={showDeleteRequests} onOpenChange={setShowDeleteRequests}>
          <DialogContent className="max-w-2xl">
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
                        Requested by: {request.requester_name} (@{request.requester})
                      </div>
                      <div className="text-xs text-gray-400">
                        {new Date(request.requested_at).toLocaleString()}
                      </div>
                    </div>
                    <Button
                      onClick={() => approveDeleteRequest(request.id)}
                      variant="destructive"
                      size="sm"
                    >
                      <Trash2 className="h-4 w-4 mr-1" />
                      Approve Delete
                    </Button>
                  </div>
                ))
              )}
            </div>
            <Button onClick={() => setShowDeleteRequests(false)} className="w-full">
              Close
            </Button>
          </DialogContent>
        </Dialog>

        {/* CSV Preview Dialog */}
        <Dialog open={showCsvPreview} onOpenChange={setShowCsvPreview}>
          <DialogContent className="max-w-4xl max-h-[80vh]">
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
                    <div className="overflow-x-auto max-h-96">
                      <table className="w-full text-sm">
                        <thead className="bg-gray-50 sticky top-0">
                          <tr>
                            {csvPreviewData.columns.map((column, index) => (
                              <th key={index} className="px-4 py-2 text-left font-medium text-gray-900 border-b">
                                {column}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {csvPreviewData.data.map((row, index) => (
                            <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                              {csvPreviewData.columns.map((column, colIndex) => (
                                <td key={colIndex} className="px-4 py-2 border-b text-gray-700">
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
      </div>
    </div>
  )
}

export default App

