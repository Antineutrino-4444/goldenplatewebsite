import React from 'react'
import { createPortal } from 'react-dom'

/**
 * Generic popup/modal component rendered via portal.
 * Blocks interactions with underlying content by covering the viewport.
 */
export default function Popup({ open, onClose, children }) {
  if (!open) return null
  return createPortal(
    <div
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className="bg-white p-6 rounded-lg shadow-lg relative max-w-sm w-full"
        onClick={e => e.stopPropagation()}
      >
        {children}
      </div>
    </div>,
    document.body
  )
}
