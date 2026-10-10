import { createRecaptchaClient, RecaptchaError } from './recaptcha-client.js'

export const RECAPTCHA_SITE_KEY = import.meta.env.VITE_RECAPTCHA_SITE_KEY || ''
const client = createRecaptchaClient(RECAPTCHA_SITE_KEY)
export const prepareRecaptcha = client.load
export const getRecaptchaToken = client.getToken

export function recaptchaErrorMessage(error, fallback) {
  return error instanceof RecaptchaError ? error.message : fallback
}
