import SessionMetrics from '@/components/SessionMetrics.jsx'
import React, { useRef, useState } from 'react'
import AdminSessionExport from '@/components/AdminSessionExport.jsx'
import HouseRanking from '@/components/HouseRanking.jsx'
import HouseScoreSettings from '@/components/HouseScoreSettings.jsx'
import GuestPrivacySettings from '@/components/GuestPrivacySettings.jsx'
import PortalHeader from '@/components/PortalHeader.jsx'
import SessionSwitcher from '@/components/SessionSwitcher.jsx'
import StudentRosterUpload from '@/components/StudentRosterUpload.jsx'
import RosterUpload from '@/components/RosterUpload.jsx'
import TeacherNameEditor from '@/components/TeacherNameEditor.jsx'
import { Alert, AlertDescription } from '@/components/ui/alert.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import { SearchableNameInput } from '@/components/SearchableNameInput.jsx'
import {
  AlertCircle,
  Ban,
  BarChart3,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  Copy,
  Download,
  FileText,
  History,
  ListOrdered,
  Plus,
  RefreshCcw,
  Shield,
  ShieldCheck,
  Sparkles,
  Trash2,
  Trophy,
  Upload,
  UserPlus,
  Users,
  Wand2,
  XCircle
} from 'lucide-react'

function PortalPageContent({ children }) {
  return <main id="main-content" className="mx-auto my-6 w-[calc(100%-1.5rem)] max-w-5xl space-y-6 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-7">{children}</main>
}

function MainPortal({ app }) {
  const DashboardContent = app.pageSection === 'dashboard' ? PortalPageContent : DialogContent
  const AdminContent = app.pageSection === 'admin' ? PortalPageContent : DialogContent
  const [showSessionExport, setShowSessionExport] = useState(false)
  const [sessionPanel, setSessionPanel] = useState(null)
  const selectSessionPanel = (panel) => {
    setSessionPanel((current) => current === panel || current === 'all' ? null : panel)
    if (panel === 'draw' || panel === 'all') app.setIsDrawCenterCollapsed(false)
  }
  const panelIsOpen = (panel) => sessionPanel === panel || sessionPanel === 'all'
  const recordOrigin = useRef(null)
  const openRecordDialog = (category, event) => {
    recordOrigin.current = { element: event.currentTarget, x: window.scrollX, y: window.scrollY }
    app.handleCategoryClick(category)
  }
  const restoreRecordPosition = (event) => {
    event.preventDefault()
    const origin = recordOrigin.current
    if (!origin) return
    // Radix has no DialogTrigger for these controlled dialogs. Restore focus
    // explicitly, without letting focus or the mobile keyboard scroll the page.
    origin.element?.focus({ preventScroll: true })
    window.scrollTo({ left: origin.x, top: origin.y, behavior: 'instant' })
    requestAnimationFrame(() => window.scrollTo({ left: origin.x, top: origin.y, behavior: 'instant' }))
  }
  const {
    user,
    sessionId,
    sessionName,
    sessionOwner,
    sessionStats,
    sessionDashboardStats,
    dashboardWinner,
    isSessionDiscarded,
    currentDrawInfo,
    hasStudentRecords,
    canExportSessionData,
    canManageDraw,
    canOverrideWinner,
    selectedCandidate,
    selectedCandidateKey,
    setSelectedCandidateKey,
    drawSummary,
    drawSummaryLoading,
    drawActionLoading,
    discardLoading,
    isDrawCenterCollapsed,
    setIsDrawCenterCollapsed,
    drawActionComment,
    setDrawActionComment,
    facultyPick,
    facultyPickLoading,
    pickRandomFaculty,
    finalizeFacultyWinner,
    overrideInput,
    setOverrideInput,
    setOverrideCandidate,
    overrideOptions,
    loadDrawSummary,
    startDrawProcess,
    finalizeDrawWinner,
    resetDrawWinner,
    overrideDrawWinner,
    toggleDiscardState,
    showNewSessionDialog,
    setShowNewSessionDialog,
    customSessionName,
    setCustomSessionName,
    createSession,
    isLoading,
    deleteRequests,
    loadAdminData,
    setShowAdminPanel,
    showAdminPanel,
    loadSessions,
    setShowSessionsDialog,
    sessions,
    setShowDeleteConfirm,
    showDeleteConfirm,
    deleteSession,
    sessionToDelete,
    showDashboard,
    setShowDashboard,
    showCleanDialog,
    setShowCleanDialog,
    showDirtyDialog,
    setShowDirtyDialog,
    showRedDialog,
    setShowRedDialog,
    showFacultyDialog,
    setShowFacultyDialog,
    isRecording,
    handlePopupSubmit,
    handleKeyPress,
    popupInputValue,
    setPopupInputValue,
    setPopupSelectedEntry,
    studentNames,
    teacherNames,
    sanitizeSelection,
    csvData,
    csvPreviewLoading,
    previewCSV,
    showCsvPreview,
    setShowCsvPreview,
    csvPreviewData,
    csvPreviewPage,
    csvPreviewSearch,
    setCsvPreviewSearch,
    teacherPreviewLoading,
    previewTeachers,
    showTeacherPreview,
    setShowTeacherPreview,
    teacherPreviewData,
    teacherPreviewPage,
    teacherPreviewSearch,
    setTeacherPreviewSearch,
    uploadTeachers,
    exportCSV,
    exportDetailedCSV,
    scanHistory,
    allUsers,
    loadAllUsers,
    toggleAccountStatus,
    showAccountManagement,
    setShowAccountManagement,
    adminUsers,
    adminSessions,
    showDeleteRequests,
    setShowDeleteRequests,
    loadDeleteRequests,
    approveDeleteRequest,
    rejectDeleteRequest,
    generateInviteCode,
    changeUserRole,
    setUserToDelete,
    setShowUserDeleteConfirm,
    showUserDeleteConfirm,
    userToDelete,
    deleteUserAccount,
    accountRequests,
    showAccountRequests,
    setShowAccountRequests,
    accountRequestsLoading,
    loadAccountRequests,
    approveAccountRequest,
    rejectAccountRequest,
    isExtraSession,
    currentMainSessionId,
    showMergeDialog,
    mergeTargetSession,
    mergeMainSessionId,
    setMergeMainSessionId,
    mergeActionLoading,
    mergeSession,
    unmergeSession,
    closeMergeDialog
  } = app

  const formatSchoolNameWithCode = (school) => {
    if (!school?.name) {
      return null
    }
    const code = (school.code ?? school.slug ?? '').trim()
    return code ? `${school.name} (Code: ${code})` : school.name
  }

  const deleteRequestsCount = deleteRequests.length
  const pendingAccountRequestsCount = accountRequests.filter(r => r.status === 'pending').length

  return (
    <div className="min-h-screen min-w-0 bg-gray-50 [overflow-wrap:anywhere]">
      <PortalHeader app={app} />

      <div hidden={app.pageSection === 'dashboard' || app.pageSection === 'admin'} className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-8">
        {!sessionId ? (
          <div className="text-center py-16">
            <div className="max-w-md mx-auto">
              <div className="mb-8">
                <div className="text-6xl mb-4">🍽️</div>
                <h2 className="text-2xl font-bold text-gray-900 mb-2">No Active Session</h2>
                <p className="text-gray-600 mb-6">
                  {user?.role === 'guest' ? 'No public sessions are available for this school.' : 'Create a session to record plates from a lunch.'}
                </p>
              </div>
              <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center">
                <Button
                  onClick={() => createSession('')}
                  className="bg-amber-600 hover:bg-amber-700 text-white px-6 py-3 text-base sm:px-8 sm:text-lg w-full sm:w-auto"
                  size="lg"
                  disabled={isLoading}
                >
                  <Plus className="h-5 w-5 mr-2" />
                  {isLoading ? 'Creating...' : 'Create New Session'}
                </Button>
                {['admin', 'superadmin'].includes(user?.role) && (
                  <Button
                    onClick={() => {
                      setShowAdminPanel(true)
                      loadAdminData()
                    }}
                    className="relative bg-red-600 hover:bg-red-700 text-white px-6 py-3 text-base sm:px-8 sm:text-lg w-full sm:w-auto"
                    size="lg"
                    disabled={isLoading}
                  >
                    <Shield className="h-5 w-5 mr-2" />
                    Admin Panel
                    {deleteRequestsCount > 0 && (
                      <span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs rounded-full px-2 py-0.5">
                        {deleteRequestsCount}
                      </span>
                    )}
                  </Button>
                )}
              </div>
            </div>
          </div>
        ) : (
          <>
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
                  <Badge variant="destructive" className="uppercase tracking-wide">Discarded · excluded from live totals</Badge>
                </div>
              )}
              <div className="mt-3 text-sm text-gray-600">
                {currentDrawInfo?.winner ? (
                  <div className="space-y-1">
                    <div>
                      Current Winner:{' '}
                      <span className="font-semibold">{currentDrawInfo.winner.display_name}</span>
                      {currentDrawInfo.finalized ? ' (Finalized)' : ' (Pending Finalization)'}
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
              <Button
                onClick={() => {
                  if (['admin', 'superadmin'].includes(user?.role)) {
                    loadAdminData()
                  }
                  setShowDashboard(true)
                }}
                className="bg-purple-600 hover:bg-purple-700"
              >
                <BarChart3 className="h-4 w-4 mr-2" />
                Dashboard
              </Button>
              {['admin', 'superadmin'].includes(user.role) && (
                <Button
                  onClick={() => { loadAdminData(); setShowAdminPanel(true) }}
                  className="relative bg-red-600 hover:bg-red-700"
                >
                  <Shield className="h-4 w-4 mr-2" />
                  Admin Panel
                  {deleteRequestsCount > 0 && (
                    <span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs rounded-full px-2 py-0.5">
                      {deleteRequestsCount}
                    </span>
                  )}
                </Button>
              )}
            </div>

            <section id="record-entry" aria-labelledby="record-entry-title" className="mb-6 scroll-mt-4 rounded-xl border bg-white p-4">
              <h2 id="record-entry-title" className="mb-3 text-lg font-semibold">Add a plate record</h2>
              {user?.role === 'guest' && (
                <Alert className="mb-3 w-full border-blue-200 bg-blue-50">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription className="text-blue-800">
                    Sign in with your school account to record plates.
                  </AlertDescription>
                </Alert>
              )}

              <div className="grid grid-cols-2 gap-3">
              <Button
                onClick={(event) => openRecordDialog('clean', event)}
                className="w-full h-auto min-h-20 flex-col gap-1 whitespace-normal px-2 py-3 text-sm sm:text-base font-semibold bg-yellow-500 hover:bg-yellow-600 text-white shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading || isRecording || user?.role === 'guest'}
              >
                🥇 CLEAN PLATE
                <span className="text-xs sm:text-sm opacity-90">({sessionStats.clean_count} recorded)</span>
              </Button>

              <Button
                onClick={(event) => openRecordDialog('faculty', event)}
                className="w-full h-auto min-h-20 flex-col gap-1 whitespace-normal px-2 py-3 text-sm sm:text-base font-semibold bg-green-500 hover:bg-green-600 text-white shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading || isRecording || user?.role === 'guest'}
              >
                🧑‍🏫 FACULTY CLEAN
                <span className="text-xs sm:text-sm opacity-90">({sessionStats.faculty_clean_count} recorded)</span>
              </Button>

              <Button
                onClick={(event) => openRecordDialog('dirty', event)}
                className="w-full h-auto min-h-20 flex-col gap-1 whitespace-normal px-2 py-3 text-sm sm:text-base font-semibold bg-orange-500 hover:bg-orange-600 text-white shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading || isRecording || user?.role === 'guest'}
              >
                🍽️ DIRTY PLATE
                <span className="text-xs sm:text-sm opacity-90">({sessionStats.dirty_count} total)</span>
              </Button>

              <Button
                onClick={(event) => openRecordDialog('red', event)}
                className="w-full h-auto min-h-20 flex-col gap-1 whitespace-normal px-2 py-3 text-sm sm:text-base font-semibold bg-red-500 hover:bg-red-600 text-white shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading || isRecording || user?.role === 'guest'}
              >
                🍝 VERY DIRTY PLATE
                <span className="text-xs sm:text-sm opacity-90">({sessionStats.red_count} recorded)</span>
              </Button>
            </div>
            </section>

            <div role="group" aria-label="Session sections" className="mb-4 flex flex-wrap gap-2 text-sm">
              {[
                ['rankings', 'House rankings', 'session-rankings-panel'],
                ['draw', 'Draw Center', 'session-draw-panel'],
                ...(['admin', 'superadmin'].includes(user?.role) ? [['databases', 'Student and teacher databases', 'session-databases-panel']] : []),
              ].map(([panel, label, id]) => (
                <Button key={panel} type="button" variant={panelIsOpen(panel) ? 'default' : 'outline'}
                  className="min-h-11 h-auto whitespace-normal" aria-expanded={panelIsOpen(panel)} aria-controls={id}
                  onClick={() => selectSessionPanel(panel)}>{label}</Button>
              ))}
              <Button type="button" variant="outline" className="min-h-11 h-auto whitespace-normal sm:ml-auto"
                aria-expanded={sessionPanel === 'all'}
                aria-controls={`session-rankings-panel session-draw-panel${['admin', 'superadmin'].includes(user?.role) ? ' session-databases-panel' : ''}`}
                onClick={() => selectSessionPanel('all')}>{sessionPanel === 'all' ? 'Collapse all' : 'Expand all'}</Button>
            </div>
            <div className={`grid grid-cols-1 gap-4 sm:gap-6 ${sessionPanel === 'all' && canExportSessionData ? 'lg:grid-cols-2' : ''}`}>
              <div id="session-rankings-panel" hidden={!panelIsOpen('rankings')} className="min-w-0">
                <HouseRanking app={app} />
              </div>
              <div id="session-draw-panel" hidden={!panelIsOpen('draw')} className="min-w-0">
              {isExtraSession ? (
                <Card
                  id="draw-center-section"
                  className="min-w-0"
                >
                  <CardHeader>
                    <CardTitle className="flex flex-wrap items-center gap-2">
                      <Trophy className="h-5 w-5" />
                      Draw Center
                    </CardTitle>
                    <CardDescription>
                      Draws are disabled for extra sessions merged into a main session.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Alert>
                      <AlertDescription>
                        This session is merged as an extra session. Its records count toward the main session's draw.
                        {currentMainSessionId && sessions?.length > 0 && (() => {
                          const mainSess = sessions.find(s => s.session_id === currentMainSessionId)
                          return mainSess ? (
                            <> Main session: <strong>{mainSess.session_name}</strong>.</>
                          ) : null
                        })()}
                        {canManageDraw && (
                          <Button
                            onClick={() => unmergeSession(sessionId)}
                            disabled={mergeActionLoading}
                            variant="outline"
                            size="sm"
                            className="ml-2 mt-2"
                          >
                            Unmerge this session
                          </Button>
                        )}
                      </AlertDescription>
                    </Alert>
                  </CardContent>
                </Card>
              ) : (
              <Card
                id="draw-center-section"
                className="min-w-0"
              >
                <CardHeader>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <CardTitle className="flex flex-wrap items-center gap-2">
                      <Trophy className="h-5 w-5" />
                      Draw Center
                    </CardTitle>
                    <div className="flex flex-wrap items-center gap-2">
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
                  {!isDrawCenterCollapsed ? (
                    <CardContent>
                      {drawSummaryLoading ? (
                        <div className="py-8 text-center text-gray-500">Loading draw summary...</div>
                      ) : drawSummary ? (
                        <div className="space-y-6">
                          {isSessionDiscarded && (
                            <Alert variant="destructive">
                              <Ban className="h-4 w-4" />
                              <AlertDescription>
                                This session is discarded. Its plates are excluded from live totals and its draws are disabled. Restore it to include it again.
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
                                user?.role === 'guest' ||
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
                              disabled={
                                drawActionLoading ||
                                !canManageDraw ||
                                user?.role === 'guest' ||
                                !currentDrawInfo?.winner ||
                                currentDrawInfo.finalized
                              }
                            >
                              <CheckCircle className="h-4 w-4 mr-2" />
                              Finalize Winner
                            </Button>
                            <Button
                              onClick={resetDrawWinner}
                              variant="outline"
                              disabled={
                                drawActionLoading ||
                                !canManageDraw ||
                                user?.role === 'guest' ||
                                !currentDrawInfo?.winner
                              }
                            >
                              <RefreshCcw className="h-4 w-4 mr-2" />
                              Reset Draw
                            </Button>
                          </div>
                          <div className="flex flex-col gap-1">
                            <Label htmlFor="draw-action-comment" className="text-xs text-gray-600">
                              Action comment (optional)
                            </Label>
                            <Input
                              id="draw-action-comment"
                              value={drawActionComment}
                              onChange={(event) => setDrawActionComment(event.target.value)}
                              placeholder="Add context for this draw action"
                            />
                            <p className="text-xs text-gray-500">
                              The note is saved to the draw history when you start, finalize, reset, or override.
                            </p>
                          </div>
                          <div className="flex w-full flex-col gap-2 rounded-lg border border-gray-200 bg-white p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
                            <div>
                              <div className="text-sm text-gray-500">Random Faculty Picker</div>
                              <div className="text-lg font-semibold">
                                {facultyPick?.display_name || 'No faculty selected yet'}
                              </div>
                              {facultyPick && <div className="text-xs text-gray-600">{facultyPick.finalized ? 'Finalized winner' : 'Pending finalization'}</div>}
                              {facultyPick?.recorded_at && (
                                <div className="text-xs text-gray-500">
                                  Recorded at {new Date(facultyPick.recorded_at).toLocaleString()}
                                </div>
                              )}
                            </div>
                            <div className="flex flex-wrap gap-2">
                              <Button
                                onClick={pickRandomFaculty}
                                variant="outline"
                                disabled={
                                  facultyPickLoading ||
                                  !canManageDraw ||
                                  user?.role === 'guest' ||
                                  isSessionDiscarded ||
                                  (sessionStats.faculty_clean_count ?? 0) <= 0 ||
                                  !sessionId
                                }
                              >
                                <Sparkles className="h-4 w-4 mr-2" />
                                Pick Faculty Name
                              </Button>
                              <Button
                                onClick={finalizeFacultyWinner}
                                variant="outline"
                                disabled={facultyPickLoading || !canManageDraw || !facultyPick || facultyPick.finalized || isSessionDiscarded}
                              >
                                <CheckCircle className="h-4 w-4 mr-2" />
                                Finalize Faculty Winner
                              </Button>
                            </div>
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
                                disabled={
                                  drawActionLoading ||
                                  user?.role === 'guest' ||
                                  !overrideInput.trim() ||
                                  !hasStudentRecords
                                }
                              >
                                <ShieldCheck className="h-4 w-4 mr-2" />
                                Override Winner
                              </Button>
                            </div>
                          )}
                          <div className="grid gap-4 lg:grid-cols-2">
                            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                              <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-gray-700">
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
                                    <div className="text-xs text-gray-500">
                                      Draw type: {currentDrawInfo.override_applied || currentDrawInfo.method === 'override' ? 'Override' : 'Random'}
                                    </div>
                                    <div className="text-xs">
                                      Status:{' '}
                                      <Badge variant={currentDrawInfo.finalized ? 'default' : 'outline'}>
                                        {currentDrawInfo.finalized ? 'Finalized' : 'Awaiting Finalization'}
                                      </Badge>
                                    </div>
                                  </div>
                                ) : (
                                  <div className="text-sm text-gray-500">No winner selected yet.</div>
                                )}
                              </div>
                            </div>
                            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                              <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-gray-700">
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
                              <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-gray-700">
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
                              <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-gray-700">
                                <History className="h-4 w-4" />
                                Draw History
                              </div>
                              <div className="mt-3 text-sm">
                                {drawSummary?.history && drawSummary.history.length > 0 ? (
                                  <div className="max-h-48 space-y-2 overflow-x-hidden overflow-y-auto pr-1 text-xs text-gray-600">
                                    {drawSummary.history
                                      .slice()
                                      .reverse()
                                      .map((entry, index) => (
                                        <div key={`${entry.timestamp}-${index}`} className="rounded border p-2">
                                          <div className="font-semibold uppercase">{entry.event_type.replace(/_/g, ' ')}</div>
                                          <div>When: {entry.timestamp ? new Date(entry.timestamp).toLocaleString() : 'N/A'}</div>
                                          {entry.student_name && <div>Student: {entry.student_name}</div>}
                                          {entry.faculty_name && <div>Faculty: {entry.faculty_name}</div>}
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
                                          {entry.comment && <div className="text-gray-700">Comment: {entry.comment}</div>}
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
                            <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-gray-700">
                              <ListOrdered className="h-4 w-4" />
                              Eligible Students
                            </div>
                            <div className="mt-3">
                              {drawSummary.candidates && drawSummary.candidates.length > 0 ? (
                                <div className="max-h-56 space-y-1 overflow-x-hidden overflow-y-auto pr-1">
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
                          No draw data available. Record an eligible student’s plate to generate tickets.
                        </div>
                      )}
                      </CardContent>
                    ) : null}
                  </Card>
              )}

              </div>
              {['admin', 'superadmin'].includes(user?.role) && <section id="session-databases-panel" hidden={!panelIsOpen('databases')} aria-labelledby="session-databases-title" className={`min-w-0 rounded-lg border bg-white p-4 ${sessionPanel === 'all' && canExportSessionData ? 'lg:col-span-2' : ''}`}>
                <h2 id="session-databases-title" className="py-2 text-lg font-semibold">Student and teacher databases</h2>
                <div className="mt-3 grid min-w-0 gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="flex flex-wrap items-center gap-2">
                    <Upload className="h-5 w-5" />
                    Student Database
                  </CardTitle>
                  <CardDescription>
                    Upload your student roster as a CSV. Include Student ID, Last, and Preferred; use First only if there is no Preferred column. Grade, Advisor, House, and Clan are optional. The new roster sets student eligibility for ticket draws.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {!['admin', 'superadmin'].includes(user?.role) ? (
                    <Alert className="border-blue-200 bg-blue-50">
                      <AlertCircle className="h-4 w-4" />
                      <AlertDescription className="text-blue-800">
                        Ask a school admin to upload the student roster.
                      </AlertDescription>
                    </Alert>
                  ) : (
                    <StudentRosterUpload app={app} />
                  )}
                  {['admin', 'superadmin'].includes(user?.role) && (
                    <div className="flex flex-wrap gap-2 mb-4">
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

              <Card>
                <CardHeader>
                  <CardTitle className="flex flex-wrap items-center gap-2">
                    <Users className="h-5 w-5" />
                    Teacher Database
                  </CardTitle>
                  <CardDescription>
                    Upload a faculty CSV or comma-separated TXT file with Last and Preferred; use First only if there is no Preferred column. Add Faculty ID to keep records connected when names change. Use the preview to review the roster or edit a name.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {!['admin', 'superadmin'].includes(user?.role) ? (
                    <Alert className="border-blue-200 bg-blue-50">
                      <AlertCircle className="h-4 w-4" />
                      <AlertDescription className="text-blue-800">
                        Ask a school admin to upload the faculty roster.
                      </AlertDescription>
                    </Alert>
                  ) : (
                    <RosterUpload roster={app.teacherRoster} kind="teacher" accept=".csv,.txt" isLoading={isLoading} upload={uploadTeachers} setModal={app.setModal} />
                  )}
                  {['admin', 'superadmin'].includes(user?.role) && (
                    <div className="flex flex-wrap gap-2 mb-4">
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

                </div>
              </section>}
                </div>

            <div className="mt-8">
              <Card>
                <CardHeader>
                  <CardTitle id="plate-history" className="flex scroll-mt-4 flex-wrap items-center gap-2">
                    <FileText className="h-5 w-5" />
                    Plate Tracking History
                  </CardTitle>
                  <CardDescription>
                    Recent plate records for this session
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {scanHistory.length > 0 ? (
                    <div className="space-y-2 max-h-60 overflow-x-hidden overflow-y-auto">
                      {scanHistory.map((record, index) => (
                        <div key={index} className="flex flex-wrap items-center justify-between gap-2 p-2 border rounded-lg text-sm">
                          <div className="flex flex-wrap items-center gap-2 sm:gap-4 min-w-0">
                            <div className="text-gray-500 shrink-0 text-xs sm:text-sm">
                              {new Date(record.timestamp).toLocaleTimeString()}
                            </div>
                            <div className="font-medium truncate">
                              {record.name}
                              {record.is_excluded && <span className="ml-2 rounded bg-gray-200 px-2 py-0.5 text-xs text-gray-700">Excluded from calculations</span>}
                            </div>
                          </div>
                          <div className={`px-2 py-1 rounded text-xs font-medium shrink-0 ${
                            record.category === 'CLEAN' ? 'bg-yellow-100 text-yellow-800' :
                            record.category === 'DIRTY' ? 'bg-orange-100 text-orange-800' :
                            record.category === 'FACULTY' ? 'bg-green-100 text-green-800' :
                            'bg-red-100 text-red-800'
                          }`}>
                            {record.category === 'CLEAN' ? '🥇 CLEAN' :
                             record.category === 'DIRTY' ? '🍽️ DIRTY' :
                             record.category === 'FACULTY' ? '🧑‍🏫 FACULTY' :
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
          </>
        )}
      </div>

      <Dialog open={showCleanDialog} onOpenChange={setShowCleanDialog}>
        <DialogContent dismissOnOverlayClick={false} onCloseAutoFocus={restoreRecordPosition}>
          <DialogHeader>
            <DialogTitle className="text-yellow-600">🥇 Record as CLEAN PLATE</DialogTitle>
            <DialogDescription>
              Enter a Student ID or name, or leave blank to add one clean plate to the count.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <SearchableNameInput
              placeholder="Student ID or name (optional)"
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
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => { setShowCleanDialog(false); setPopupSelectedEntry(null) }} variant="outline" className="flex-1">
                Cancel
              </Button>
              <Button
                onClick={() => handlePopupSubmit('clean')}
                className="min-h-11 h-auto flex-1 whitespace-normal bg-yellow-500 hover:bg-yellow-600"
                disabled={isRecording}
              >
                Record as CLEAN PLATE
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showDirtyDialog} onOpenChange={setShowDirtyDialog}>
        <DialogContent dismissOnOverlayClick={false} onCloseAutoFocus={restoreRecordPosition}>
          <DialogHeader>
            <DialogTitle className="text-orange-600">🍽️ Add DIRTY PLATE</DialogTitle>
            <DialogDescription>
              Enter a Student ID or name, or leave blank to add one dirty plate to the count.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <SearchableNameInput
              placeholder="Student ID or name (optional)"
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
              onKeyPress={(e) => handleKeyPress(e, 'dirty')}
              names={studentNames}
              autoFocus
            />
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => { setShowDirtyDialog(false); setPopupSelectedEntry(null) }} variant="outline" className="flex-1">
                Cancel
              </Button>
              <Button
                onClick={() => handlePopupSubmit('dirty')}
                className="min-h-11 h-auto flex-1 whitespace-normal bg-orange-500 hover:bg-orange-600"
                disabled={isRecording}
              >
                Add Dirty Plate
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showFacultyDialog} onOpenChange={setShowFacultyDialog}>
        <DialogContent dismissOnOverlayClick={false} onCloseAutoFocus={restoreRecordPosition}>
          <DialogHeader>
            <DialogTitle className="text-green-600">🧑‍🏫 Record FACULTY CLEAN PLATE</DialogTitle>
            <DialogDescription>
              Enter a faculty name, or leave blank to add one faculty clean plate to the count.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <SearchableNameInput
              placeholder="Faculty name (optional)"
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
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => { setShowFacultyDialog(false); setPopupSelectedEntry(null) }} variant="outline" className="flex-1">
                Cancel
              </Button>
              <Button
                onClick={() => handlePopupSubmit('faculty')}
                className="min-h-11 h-auto flex-1 whitespace-normal bg-green-500 hover:bg-green-600"
                disabled={isRecording}
              >
                Record Faculty Clean Plate
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showRedDialog} onOpenChange={setShowRedDialog}>
        <DialogContent dismissOnOverlayClick={false} onCloseAutoFocus={restoreRecordPosition}>
          <DialogHeader>
            <DialogTitle className="text-red-600">🍝 Record as VERY DIRTY PLATE</DialogTitle>
            <DialogDescription>
              Enter a Student ID or name, or leave blank to add one very dirty plate to the count.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <SearchableNameInput
              placeholder="Student ID or name (optional)"
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
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => { setShowRedDialog(false); setPopupSelectedEntry(null) }} variant="outline" className="flex-1">
                Cancel
              </Button>
              <Button
                onClick={() => handlePopupSubmit('red')}
                className="min-h-11 h-auto flex-1 whitespace-normal bg-red-500 hover:bg-red-600"
                disabled={isRecording}
              >
                Record as VERY DIRTY PLATE
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showNewSessionDialog} onOpenChange={setShowNewSessionDialog}>
        <DialogContent dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle>Create New Session</DialogTitle>
            <DialogDescription>
              Name this lunch session, or leave blank to use the default name.
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
            <div className="flex flex-wrap gap-2">
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

      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle className="text-red-600">{canManageDraw ? 'Delete Session' : 'Request Session Deletion'}</DialogTitle>
            <DialogDescription>
              {canManageDraw ? 'Permanently delete this session and its records? This cannot be undone.' : 'Request administrator approval to delete this session and its records.'}
            </DialogDescription>
          </DialogHeader>
          {sessionToDelete && (
            <div className="bg-gray-50 p-4 rounded-lg">
              <div className="font-medium">{sessionToDelete.session_name}</div>
              <div className="text-sm text-gray-600">
                {sessionToDelete.total_records} records {canManageDraw ? 'will be permanently deleted' : 'will be permanently deleted if approved'}
              </div>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
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
              {canManageDraw ? 'Delete Session' : 'Request Deletion'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showCsvPreview} onOpenChange={setShowCsvPreview}>
        <DialogContent
          className="flex max-h-[85dvh] flex-col overflow-y-hidden sm:max-w-2xl lg:max-w-3xl"
          dismissOnOverlayClick={false}
        >
          <DialogHeader>
            <DialogTitle>Student Database Preview</DialogTitle>
            <DialogDescription>
              Search the uploaded student roster.
            </DialogDescription>
          </DialogHeader>
          <div className="flex min-h-0 flex-col gap-4">
            <form className="flex shrink-0 flex-wrap gap-2" onSubmit={(event) => { event.preventDefault(); previewCSV(1) }}>
              <Input className="min-w-0 flex-1" aria-label="Search student names" placeholder="Search student names" value={csvPreviewSearch} onChange={(event) => setCsvPreviewSearch(event.target.value)} />
              <Button type="submit" variant="outline" disabled={csvPreviewLoading}>Search</Button>
              {csvPreviewSearch && <Button type="button" variant="ghost" onClick={() => { setCsvPreviewSearch(''); previewCSV(1, '') }}>Clear</Button>}
            </form>
            {csvPreviewData && (
              <>
                <div className="shrink-0 text-sm text-gray-600">
                  <p><strong>Total Records:</strong> {csvPreviewData.pagination.total_records}</p>
                  <p><strong>Uploaded by:</strong> {csvPreviewData.metadata.uploaded_by}</p>
                  <p><strong>Uploaded at:</strong> {csvPreviewData.metadata.uploaded_at ? new Date(csvPreviewData.metadata.uploaded_at).toLocaleString() : 'Unknown'}</p>
                </div>

                <div className="min-h-0 flex-1 space-y-3 overflow-x-hidden overflow-y-auto rounded-lg border bg-slate-50 p-3">
                  {csvPreviewData.data.length === 0 && <p className="py-4 text-center text-sm text-gray-500">No students match this name.</p>}
                  {csvPreviewData.data.map((row, index) => (
                    <dl key={index} className="grid min-w-0 grid-cols-1 gap-x-4 gap-y-3 rounded-md border bg-white p-3 text-xs sm:grid-cols-2 lg:grid-cols-3">
                      {csvPreviewData.columns.map((column, colIndex) => (
                        <div key={colIndex} className="min-w-0">
                          <dt className="font-medium text-slate-500">{column}</dt>
                          <dd className="mt-1 text-slate-900 [overflow-wrap:anywhere]">{row[column] ?? '-'}</dd>
                        </div>
                      ))}
                    </dl>
                  ))}
                </div>

                <div className="flex shrink-0 flex-wrap justify-between items-center gap-3">
                  <div className="shrink-0 text-sm text-gray-600">
                    Page {csvPreviewData.pagination.page} of {csvPreviewData.pagination.total_pages}
                    ({csvPreviewData.data.length} of {csvPreviewData.pagination.total_records} records)
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      onClick={() => previewCSV(csvPreviewPage - 1, csvPreviewData.search || '')}
                      disabled={!csvPreviewData.pagination.has_prev || csvPreviewLoading}
                      variant="outline"
                      size="sm"
                    >
                      Previous
                    </Button>
                    <Button
                      onClick={() => previewCSV(csvPreviewPage + 1, csvPreviewData.search || '')}
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
          <Button onClick={() => setShowCsvPreview(false)} className="w-full shrink-0">
            Close
          </Button>
        </DialogContent>
      </Dialog>

      {showTeacherPreview && (
        <Dialog open={showTeacherPreview} onOpenChange={setShowTeacherPreview}>
          <DialogContent className="flex max-h-[85dvh] flex-col overflow-y-hidden sm:max-w-2xl lg:max-w-4xl" dismissOnOverlayClick={false}>
            <DialogHeader>
              <DialogTitle>Teacher List Preview</DialogTitle>
              <DialogDescription>
                Search the uploaded faculty roster.
              </DialogDescription>
            </DialogHeader>
            <div className="flex min-h-0 flex-col gap-4">
              <form className="flex shrink-0 flex-wrap gap-2" onSubmit={(event) => { event.preventDefault(); previewTeachers(1) }}>
                <Input className="min-w-0 flex-1" aria-label="Search teacher names" placeholder="Search teacher names" value={teacherPreviewSearch} onChange={(event) => setTeacherPreviewSearch(event.target.value)} />
                <Button type="submit" variant="outline" disabled={teacherPreviewLoading}>Search</Button>
                {teacherPreviewSearch && <Button type="button" variant="ghost" onClick={() => { setTeacherPreviewSearch(''); previewTeachers(1, '') }}>Clear</Button>}
              </form>
              {teacherPreviewLoading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="text-muted-foreground">Loading teacher list...</div>
                </div>
              ) : teacherPreviewData ? (
                <>
                  <div className="shrink-0 text-sm text-muted-foreground">
                    <p><strong>Total Teachers:</strong> {teacherPreviewData.pagination.total_records}</p>
                    <p><strong>Uploaded by:</strong> {teacherPreviewData.metadata.uploaded_by}</p>
                    <p><strong>Uploaded at:</strong> {teacherPreviewData.metadata.uploaded_at ? new Date(teacherPreviewData.metadata.uploaded_at).toLocaleString() : 'Unknown'}</p>
                  </div>

                  <div className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto border rounded-lg">
                    {teacherPreviewData.data.length === 0 && <p className="py-4 text-center text-sm text-gray-500">No teachers match this name.</p>}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 p-4">
                      {teacherPreviewData.data.map((teacher, index) => (
                        <div key={teacher.teacher_id || index} className="min-w-0 p-2 bg-gray-50 rounded text-sm [overflow-wrap:anywhere]">
                          <TeacherNameEditor teacher={teacher} save={app.saveTeacherName} />
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 pt-4">
                    <div className="shrink-0 text-sm text-muted-foreground">
                      Page {teacherPreviewData.pagination.page} of {teacherPreviewData.pagination.total_pages}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        onClick={() => previewTeachers(teacherPreviewPage - 1, teacherPreviewData.search || '')}
                        disabled={!teacherPreviewData.pagination.has_prev || teacherPreviewLoading}
                        variant="outline"
                        size="sm"
                      >
                        Previous
                      </Button>
                      <Button
                        onClick={() => previewTeachers(teacherPreviewPage + 1, teacherPreviewData.search || '')}
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
            <Button onClick={() => setShowTeacherPreview(false)} className="w-full shrink-0">
              Close
            </Button>
          </DialogContent>
        </Dialog>
      )}

      <Dialog open={showDashboard} onOpenChange={setShowDashboard}>
        <DashboardContent
          className="sm:max-w-2xl lg:max-w-4xl max-h-[82vh] overflow-x-hidden overflow-y-auto"
          dismissOnOverlayClick={false}
        >
          <DialogHeader>
            <DialogTitle className="text-purple-600">Session Dashboard</DialogTitle>
            <DialogDescription>
              Totals for the selected session.
            </DialogDescription>
          </DialogHeader>
          {!sessionId ? (
            <div className="py-12 text-center text-gray-500">
              No active session selected. Switch to a session to view its totals.
            </div>
          ) : (
            <div className="space-y-6">
              {isSessionDiscarded && (
                <Alert variant="destructive">
                  <Ban className="h-4 w-4" />
                  <AlertDescription>
                    This session is discarded. Its plates are excluded from live totals and its draws are disabled. Restore it to include it again.
                  </AlertDescription>
                </Alert>
              )}

              {user?.role === 'superadmin' && (
                <div className="flex flex-wrap justify-end gap-2">
                  <Button
                    onClick={() => toggleDiscardState(!isSessionDiscarded)}
                    variant="outline"
                    disabled={discardLoading}
                    className={isSessionDiscarded ? 'border-emerald-200 text-emerald-700 hover:bg-emerald-50' : 'border-red-200 text-red-700 hover:bg-red-50'}
                  >
                    <Ban className="h-4 w-4 mr-2" />
                    {isSessionDiscarded ? 'Restore Session' : 'Discard Session'}
                  </Button>
                </div>
              )}

              <SessionMetrics sessionName={sessionName} sessionOwner={sessionOwner || 'Unknown account'}
                sessionDashboardStats={sessionDashboardStats} isSessionDiscarded={isSessionDiscarded}
                updatedAt={drawSummary?.generated_at} />

              {canExportSessionData && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex flex-wrap items-center gap-2">
                      <Download className="h-5 w-5" />
                      Export Food Waste Data
                    </CardTitle>
                    <CardDescription>
                      Download plate records by category: clean, dirty, very dirty, and faculty clean.
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

              <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-gray-700">
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

          <Button onClick={() => setShowDashboard(false)} className="w-full shrink-0">
            Close
          </Button>
        </DashboardContent>
      </Dialog>

      <Dialog open={showAdminPanel} onOpenChange={setShowAdminPanel}>
        <AdminContent
          className="sm:max-w-2xl lg:max-w-3xl max-h-[82vh] overflow-x-hidden overflow-y-auto"
          dismissOnOverlayClick={false}
        >
          <DialogHeader>
            <DialogTitle className="text-red-600">Admin Panel</DialogTitle>
            <DialogDescription>
              Manage your school’s accounts, sessions, and settings.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-6">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {['admin', 'superadmin'].includes(user.role) && (
                <>
                  <Button onClick={() => setShowSessionExport(true)} variant="outline">
                    <Download className="h-4 w-4 mr-2" />
                    Export All Sessions
                  </Button>
                  <Button
                    onClick={generateInviteCode}
                    variant="outline"
                    className="flex-1"
                  >
                    <Copy className="h-4 w-4 mr-2" />
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
                    {deleteRequestsCount > 0 && (
                      <span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs rounded-full px-2 py-0.5">
                        {deleteRequestsCount}
                      </span>
                    )}
                  </Button>
                  <Button
                    onClick={() => {
                      loadAllUsers()
                      setShowAccountManagement(true)
                    }}
                    variant="outline"
                    className="flex-1"
                  >
                    <Users className="h-4 w-4 mr-2" />
                    Manage Accounts
                  </Button>
                </>
              )}
              {user.role === 'superadmin' && (
                <Button
                  onClick={() => {
                    loadAccountRequests()
                    setShowAccountRequests(true)
                  }}
                  variant="outline"
                  className="relative flex-1"
                >
                  <UserPlus className="h-4 w-4 mr-2" />
                  Account Requests
                  {pendingAccountRequestsCount > 0 && (
                    <span className="absolute -top-2 -right-2 bg-amber-500 text-white text-xs rounded-full px-2 py-0.5">
                      {pendingAccountRequestsCount}
                    </span>
                  )}
                </Button>
              )}
            </div>

            {user.role === 'superadmin' && showAdminPanel && <HouseScoreSettings app={app} />}
            {['admin', 'superadmin'].includes(user.role) && showAdminPanel && <GuestPrivacySettings app={app} />}

            <div>
              <h3 className="text-lg font-semibold mb-3">Users</h3>
              <div className="space-y-2">
                {adminUsers.map((adminUser) => (
                  <div key={adminUser.username} className="flex min-w-0 flex-col gap-3 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between [&>div]:min-w-0 [&>div]:max-w-full [&>div:first-child]:flex-1 [&>div:last-child]:shrink-0">
                    <div>
                      <div className="font-medium">{adminUser.name}</div>
                      <div className="text-sm text-gray-500">
                        @{adminUser.username} • {adminUser.role}
                        {formatSchoolNameWithCode(adminUser.school) && (
                          <> • {formatSchoolNameWithCode(adminUser.school)}</>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
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
              <div className="space-y-2">
                {adminSessions.map((adminSession) => (
                  <div key={adminSession.session_id} className="flex min-w-0 flex-col gap-3 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between [&>div]:min-w-0 [&>div]:max-w-full [&>div:first-child]:flex-1 [&>div:last-child]:shrink-0">
                    <div>
                      <div className="font-medium flex flex-wrap items-center gap-2">
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
          <Button onClick={() => setShowAdminPanel(false)} className="w-full shrink-0">
            Close
          </Button>
        </AdminContent>
      </Dialog>

      <AdminSessionExport open={showSessionExport} onOpenChange={setShowSessionExport} accountKey={user?.id} />

      <Dialog open={showAccountManagement} onOpenChange={setShowAccountManagement}>
        <DialogContent className="flex max-h-[85dvh] flex-col overflow-y-hidden sm:max-w-2xl" dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle>Account Management</DialogTitle>
            <DialogDescription>
              Enable or disable school accounts.
            </DialogDescription>
          </DialogHeader>
          <div className="min-h-0 flex-1 space-y-4 overflow-x-hidden overflow-y-auto p-1">
            {allUsers.map((userAccount) => (
              <div key={userAccount.username} className="flex min-w-0 flex-col gap-3 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between [&>div]:min-w-0 [&>div]:max-w-full [&>div:first-child]:flex-1 [&>div:last-child]:shrink-0">
                <div>
                  <div className="font-medium">{userAccount.name}</div>
                  <div className="text-sm text-gray-500">
                    @{userAccount.username} • {userAccount.role}
                    {formatSchoolNameWithCode(userAccount.school) && (
                      <> • {formatSchoolNameWithCode(userAccount.school)}</>
                    )}
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
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
          <Button onClick={() => setShowAccountManagement(false)} className="w-full shrink-0">
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
          <div className="flex flex-wrap gap-2 mt-4">
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

      <Dialog open={showDeleteRequests} onOpenChange={setShowDeleteRequests}>
        <DialogContent className="flex max-h-[85dvh] flex-col overflow-y-hidden sm:max-w-2xl" dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle>Delete Requests</DialogTitle>
            <DialogDescription>
              Pending session deletion requests from users
            </DialogDescription>
          </DialogHeader>
          <div className="min-h-0 flex-1 space-y-4 overflow-x-hidden overflow-y-auto p-1">
            {deleteRequests.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                No pending delete requests
              </div>
            ) : (
              deleteRequests.map((request) => (
                <div key={request.id} className="flex min-w-0 flex-col gap-3 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between [&>div]:min-w-0 [&>div]:max-w-full [&>div:first-child]:flex-1 [&>div:last-child]:shrink-0">
                  <div>
                    <div className="font-medium">{request.session_name}</div>
                    <div className="text-sm text-gray-500">
                      Requested by: {request.requester_name} (@{request.requester}) • {request.total_records} records
                    </div>
                    <div className="text-xs text-gray-400">
                      Clean: {request.clean_records} • Dirty: {request.dirty_records} • Very dirty: {request.red_records} • Faculty: {request.faculty_clean_records || 0}
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
          <Button onClick={() => setShowDeleteRequests(false)} className="w-full shrink-0">
            Close
          </Button>
        </DialogContent>
      </Dialog>

      <Dialog open={showAccountRequests} onOpenChange={setShowAccountRequests}>
        <DialogContent className="flex max-h-[85dvh] flex-col overflow-y-hidden sm:max-w-2xl" dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle>Account Creation Requests</DialogTitle>
            <DialogDescription>
              Review account requests for your school.
            </DialogDescription>
          </DialogHeader>
          <div className="min-h-0 flex-1 space-y-4 overflow-x-hidden overflow-y-auto p-1">
            {accountRequestsLoading ? (
              <div className="text-center py-8 text-gray-500">
                Loading account requests...
              </div>
            ) : accountRequests.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                No account requests
              </div>
            ) : (
              accountRequests.map((request) => (
                <div key={request.id} className="flex min-w-0 flex-col gap-3 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between [&>div]:min-w-0 [&>div]:max-w-full [&>div:first-child]:flex-1 [&>div:last-child]:shrink-0">
                  <div>
                    <div className="font-medium">{request.display_name}</div>
                    <div className="text-sm text-gray-500">
                      Username: @{request.username}
                    </div>
                    <div className="text-xs text-gray-400">
                      Requested: {new Date(request.requested_at).toLocaleString()}
                    </div>
                    <Badge
                      variant={
                        request.status === 'pending' ? 'outline' :
                        request.status === 'approved' ? 'default' :
                        'destructive'
                      }
                      className="mt-1"
                    >
                      {request.status}
                    </Badge>
                    {request.rejection_reason && (
                      <div className="text-xs text-gray-500 mt-1">
                        Reason: {request.rejection_reason}
                      </div>
                    )}
                  </div>
                  {request.status === 'pending' && (
                    <div className="flex flex-col gap-2">
                      <Button
                        onClick={() => approveAccountRequest(request.id)}
                        variant="default"
                        size="sm"
                        className="bg-green-600 hover:bg-green-700"
                      >
                        <CheckCircle className="h-4 w-4 mr-1" />
                        Approve
                      </Button>
                      <Button
                        onClick={() => rejectAccountRequest(request.id)}
                        variant="outline"
                        size="sm"
                      >
                        <XCircle className="h-4 w-4 mr-1" />
                        Reject
                      </Button>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
          <Button onClick={() => setShowAccountRequests(false)} className="w-full shrink-0">
            Close
          </Button>
        </DialogContent>
      </Dialog>

      <SessionSwitcher app={app} />

      <Dialog open={showMergeDialog} onOpenChange={(open) => { if (!open) closeMergeDialog() }}>
        <DialogContent dismissOnOverlayClick={false}>
          <DialogHeader>
            <DialogTitle>Merge Session</DialogTitle>
            <DialogDescription>
              {mergeTargetSession
                ? `Merge "${mergeTargetSession.session_name}" as an extra session into a main session. Records will count toward the main session's draw. Draws will be disabled for this session.`
                : 'Select a main session to merge into.'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <Label htmlFor="merge-main-session">Main session</Label>
            <select
              id="merge-main-session"
              value={mergeMainSessionId}
              onChange={(e) => setMergeMainSessionId(e.target.value)}
              className="w-full border rounded-md px-3 py-2 text-sm"
              disabled={mergeActionLoading}
            >
              <option value="">-- Select a main session --</option>
              {sessions
                .filter((s) =>
                  mergeTargetSession
                    ? s.session_id !== mergeTargetSession.session_id && !s.main_session_id
                    : !s.main_session_id
                )
                .map((s) => (
                  <option key={s.session_id} value={s.session_id}>
                    {s.session_name}
                  </option>
                ))}
            </select>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={closeMergeDialog}
              disabled={mergeActionLoading}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              onClick={() => mergeTargetSession && mergeSession(mergeTargetSession.session_id, mergeMainSessionId)}
              disabled={mergeActionLoading || !mergeMainSessionId || !mergeTargetSession}
              className="flex-1"
            >
              {mergeActionLoading ? 'Merging...' : 'Merge'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

    </div>
  )
}

export default MainPortal
