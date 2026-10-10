import { useEffect } from 'react'
import { prepareRecaptcha, RECAPTCHA_SITE_KEY } from '@/lib/recaptcha.js'

export default function RecaptchaNotice() {
  useEffect(() => {
    // Give v3 context while the form is completed. Errors are surfaced on submit.
    prepareRecaptcha().catch(() => {})
  }, [])
  if (!RECAPTCHA_SITE_KEY) return null
  return (
    <p className="text-center text-xs text-gray-500">
      Protected by reCAPTCHA. Google’s{' '}
      <a href="https://policies.google.com/privacy" target="_blank" rel="noreferrer" className="underline">Privacy Policy</a>
      {' '}and{' '}
      <a href="https://policies.google.com/terms" target="_blank" rel="noreferrer" className="underline">Terms of Service</a>
      {' '}apply.
    </p>
  )
}
