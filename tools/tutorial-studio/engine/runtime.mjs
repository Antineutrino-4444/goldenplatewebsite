import { createRequire } from 'node:module';
import { existsSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const toolRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
export const repoRoot = resolve(toolRoot, '../..');
export const frontendRoot = resolve(repoRoot, 'frontend');
const frontendRequire = createRequire(resolve(frontendRoot, 'package.json'));
const toolRequire = createRequire(resolve(toolRoot, 'package.json'));

export async function startServer(recipePath, port = 0) {
  const { createServer } = await import(pathToFileURL(resolve(frontendRoot, 'node_modules/vite/dist/node/index.js')).href);
  const react = (await import(pathToFileURL(frontendRequire.resolve('@vitejs/plugin-react')).href)).default;
  const tailwind = (await import(pathToFileURL(resolve(frontendRoot, 'node_modules/@tailwindcss/vite/dist/index.mjs')).href)).default;
  const server = await createServer({
    configFile: false, root: toolRoot, publicDir: resolve(frontendRoot, 'public'), envDir: toolRoot, envPrefix: 'TUTORIAL_',
    define: { 'import.meta.env.VITE_TURNSTILE_SITE_KEY': '""', 'import.meta.env.VITE_RECAPTCHA_SITE_KEY': '""' },
    plugins: [
      { name: 'tutorial-recipe', resolveId(id) { if (id === 'virtual:tutorial-recipe') return '\0tutorial-recipe'; },
        load(id) { if (id === '\0tutorial-recipe') return `export { default } from ${JSON.stringify('/@fs/' + recipePath)};`; } },
      { name: 'tutorial-css-sources', enforce: 'pre', transform(code, id) {
        if (id === resolve(frontendRoot, 'src/App.css')) return `${code}\n@source ${JSON.stringify(resolve(frontendRoot, 'src'))};\n`;
      } },
      react(), tailwind(),
    ],
    resolve: { alias: {
      '@': resolve(frontendRoot, 'src'),
      react: resolve(frontendRoot, 'node_modules/react'),
      'react-dom': resolve(frontendRoot, 'node_modules/react-dom'),
      'react-router-dom': resolve(frontendRoot, 'node_modules/react-router-dom'),
      'next-themes': resolve(frontendRoot, 'node_modules/next-themes'),
    }, dedupe: ['react', 'react-dom'] },
    optimizeDeps: { exclude: ['mapbox-gl/esm'] },
    // Rendering must not reconnect Vite HMR sockets or reload midway through a scene.
    server: { host: '127.0.0.1', port, strictPort: Boolean(port), hmr: false, watch: null, fs: { allow: [repoRoot] } },
    logLevel: 'error',
  });
  await server.listen();
  const address = server.httpServer.address();
  return { server, url: `http://127.0.0.1:${address.port}` };
}

export function playwrightRuntime() {
  const candidates = [process.env.TUTORIAL_PLAYWRIGHT_PATH, 'playwright', resolve(homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')].filter(Boolean);
  for (const candidate of candidates) {
    try { return { api: toolRequire(candidate), path: toolRequire.resolve(candidate) }; } catch { /* Try the next configured runtime. */ }
  }
  throw new Error('Playwright is missing. Run npm install in tools/tutorial-studio, then npx playwright install chromium (or use installed Edge/Chrome).');
}
export function browserOptions() {
  if (process.env.TUTORIAL_BROWSER_PATH) return { executablePath: process.env.TUTORIAL_BROWSER_PATH };
  const { api } = playwrightRuntime();
  if (existsSync(api.chromium.executablePath())) return {};
  const candidates = ['/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome'];
  const executablePath = candidates.find(existsSync);
  if (!executablePath) throw new Error('No Chromium browser found. Run npx playwright install chromium in tools/tutorial-studio.');
  return { executablePath };
}
export async function launchBrowser() {
  return playwrightRuntime().api.chromium.launch({ headless: true, ...browserOptions(), args: ['--force-color-profile=srgb', '--disable-lcd-text'] });
}

export async function openRenderer(browser, url, { width = 3840, height = 2160, exportMode = true } = {}) {
  if (exportMode && width / height !== 16 / 9) throw new Error('Video output must have a 16:9 aspect ratio.');
  const blocked = [], errors = [];
  const context = await browser.newContext({ viewport: { width: exportMode ? 1920 : width, height: exportMode ? 1080 : height }, deviceScaleFactor: exportMode ? width / 1920 : 1, colorScheme: 'dark', reducedMotion: 'reduce' });
  await context.route('**/*', async route => {
    const u = new URL(route.request().url());
    if (u.origin !== new URL(url).origin || u.pathname.startsWith('/api/')) {
      blocked.push({ path: u.pathname, origin: u.origin });
      return route.abort();
    }
    return route.continue();
  });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`${url}/${exportMode ? '?export=1' : ''}`, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForFunction(() => window.__studio?.ready(), { timeout: 60000 });
  await page.evaluate(async () => {
    await document.fonts.ready;
    const child = document.querySelector('iframe').contentDocument;
    await child.fonts.ready;
    await Promise.all([...child.images].filter(img => !img.loading || img.loading !== 'lazy').map(img => img.decode().catch(() => {})));
  });
  const cdp = await context.newCDPSession(page);
  return { context, page, cdp, blocked, errors, capture: { width, height, scale: exportMode ? width / 1920 : 1, cssWidth: exportMode ? 1920 : width, cssHeight: exportMode ? 1080 : height } };
}
export async function setFrame(renderer, scene, frame, fps) {
  const audit = await renderer.page.evaluate(({ scene, frame, fps }) => window.__studio.setFrame(scene, frame, fps), { scene, frame, fps });
  if (audit.issues.length) throw new Error(`${audit.scene} @ ${audit.seconds.toFixed(3)}s: ${audit.issues.join('; ')}`);
  if (renderer.errors.length) throw new Error(renderer.errors.join('\n'));
  return audit;
}
export async function screenshot(renderer) {
  const c = renderer.capture;
  // Chromium's CDP default can capture CSS pixels even when deviceScaleFactor is 2.
  // Explicit clip scaling asks the browser to rasterize at the export resolution.
  const { data } = await renderer.cdp.send('Page.captureScreenshot', { format: 'png', fromSurface: true, captureBeyondViewport: false, optimizeForSpeed: true,
    clip: { x: 0, y: 0, width: c.cssWidth, height: c.cssHeight, scale: c.scale } });
  const buffer = Buffer.from(data, 'base64');
  if (buffer.readUInt32BE(16) !== c.width || buffer.readUInt32BE(20) !== c.height) throw new Error(`Browser returned the wrong PNG dimensions; expected ${c.width}×${c.height}.`);
  return buffer;
}
