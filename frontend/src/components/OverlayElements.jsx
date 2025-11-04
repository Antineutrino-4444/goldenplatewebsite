import React from 'react'
import { createPortal } from 'react-dom'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import Modal from '@/components/Modal.jsx'
import { Copy } from 'lucide-react'

function OverlayElements({ app }) {
  const {
    notification,
    setNotification,
    modal,
    setModal,
    inviteCode,
    setInviteCode,
    copyInviteCode,
    copySchoolInvite
  } = app

  const schoolInvitePayload = modal?.type === 'school-invite' ? modal.payload : null

  return (
    <>
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
          onClose={() => {
            setModal(null)
            setInviteCode('')
          }}
          dismissOnOverlayClick={false}
        >
          <h2 className="text-lg font-semibold mb-4">Invite Code</h2>
          <div className="flex items-center gap-2 mb-4">
            <Input value={inviteCode} readOnly className="flex-1" />
            <Button onClick={copyInviteCode}>
              Copy
            </Button>
          </div>
          <Button onClick={() => {
            setModal(null)
            setInviteCode('')
          }}>Close</Button>
        </Modal>
      )}

      {schoolInvitePayload && (
        <Modal
          open
          onClose={() => setModal(null)}
          dismissOnOverlayClick={false}
        >
          <h2 className="text-lg font-semibold mb-2">School Invite Generated</h2>
          <p className="text-sm text-gray-600 mb-4">
            Share this code and school ID with the partner school's primary administrator. Each code can be used once.
          </p>
          <div className="space-y-3 mb-4">
            <div>
              <Label className="text-xs font-semibold uppercase text-gray-500">Invite Code</Label>
              <Input value={schoolInvitePayload.code || ''} readOnly className="mt-1 font-mono tracking-wide" />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase text-gray-500">School ID</Label>
              <Input value={schoolInvitePayload.schoolId || ''} readOnly className="mt-1 font-mono tracking-wide" />
            </div>
            {schoolInvitePayload.issuedAt && (
              <div className="text-xs text-gray-500">
                Generated {new Date(schoolInvitePayload.issuedAt).toLocaleString()}
              </div>
            )}
          </div>
          <div className="flex flex-wrap gap-2 justify-end">
            <Button onClick={() => copySchoolInvite(schoolInvitePayload, 'code')}>
              <Copy className="h-4 w-4 mr-2" />
              Copy Code
            </Button>
            <Button variant="outline" onClick={() => copySchoolInvite(schoolInvitePayload, 'details')}>
              <Copy className="h-4 w-4 mr-2" />
              Copy Details
            </Button>
            <Button variant="ghost" onClick={() => setModal(null)}>
              Close
            </Button>
          </div>
        </Modal>
      )}
    </>
  )
}

export default OverlayElements
