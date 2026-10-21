import { createCaptchaClient, CaptchaError } from './captcha-client.js'

export const CAPTCHA_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY || ''
const client = createCaptchaClient(CAPTCHA_SITE_KEY)
export const prepareCaptcha = client.load
export const registerCaptchaContainer = client.registerContainer
export const getCaptchaToken = client.getToken

export function captchaErrorMessage(error, fallback) {
  return error instanceof CaptchaError ? error.message : fallback
}
