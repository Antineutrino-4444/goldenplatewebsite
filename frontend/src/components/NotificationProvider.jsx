import React, { createContext, useContext, useState } from 'react'
import { createPortal } from 'react-dom'

const NotificationContext = createContext(null)

export function NotificationProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const [modalContent, setModalContent] = useState(null)

  const showToast = (text, type = 'info', duration = 3000) => {
    const id = Date.now()
    setToasts((prev) => [...prev, { id, text, type }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, duration)
  }

  const showModal = (content) => setModalContent(content)
  const closeModal = () => setModalContent(null)

  const typeClass = (type) => {
    switch (type) {
      case 'success':
        return 'bg-green-600'
      case 'error':
        return 'bg-red-600'
      default:
        return 'bg-blue-600'
    }
  }

  return (
    <NotificationContext.Provider value={{ showToast, showModal, closeModal }}>
      {children}
      {createPortal(
        <div className="fixed top-4 right-4 z-[10000] space-y-2 pointer-events-none">
          {toasts.map((t) => (
            <div
              key={t.id}
              className={`pointer-events-auto px-4 py-2 rounded text-white shadow ${typeClass(t.type)}`}
            >
              {t.text}
            </div>
          ))}
        </div>,
        document.body
      )}
      {modalContent &&
        createPortal(
          <div
            className="fixed inset-0 z-[10001] flex items-center justify-center bg-black/50"
            onClick={closeModal}
          >
            <div
              className="bg-white p-6 rounded-lg shadow-lg max-h-[90vh] overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              {modalContent}
            </div>
          </div>,
          document.body
        )}
    </NotificationContext.Provider>
  )
}

export function useNotification() {
  return useContext(NotificationContext)
}

export default NotificationProvider

