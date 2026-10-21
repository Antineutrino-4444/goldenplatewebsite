import { useEffect, useRef } from 'react'
import { CAPTCHA_SITE_KEY, prepareCaptcha, registerCaptchaContainer } from '@/lib/captcha.js'

export default function CaptchaVerification({ actions }) {
  const container = useRef(null)
  useEffect(() => {
    if (!CAPTCHA_SITE_KEY) return
    const unregister = registerCaptchaContainer(container.current, actions.split(/\s+/))
    prepareCaptcha().catch(() => {}) // Submit reports loading failures and allows retry.
    return unregister
  }, [actions])
  if (!CAPTCHA_SITE_KEY) return null
  // Keep the interactive iframe inside the form/dialog's focus boundary.
  return <div ref={container} className="flex w-full justify-center empty:hidden" />
}
