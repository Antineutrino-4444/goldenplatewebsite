// Run before the first paint, including when storage is blocked or unavailable.
;(() => {
  let preference
  try {
    preference = localStorage.getItem('goldenplate.theme')
    if (preference && !['light', 'dark', 'system'].includes(preference)) {
      localStorage.removeItem('goldenplate.theme')
      preference = null
    }
  } catch { /* Use the device setting. */ }
  const dark = preference === 'dark' || (preference !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.classList.toggle('dark', dark)
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light'
  const browserColor = document.querySelector('meta[name="theme-color"]')
  const lightColor = browserColor.content
  const syncBrowserColor = () => {
    browserColor.content = document.documentElement.classList.contains('dark') ? browserColor.dataset.dark : lightColor
  }
  syncBrowserColor()
  new MutationObserver(syncBrowserColor).observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
})()
