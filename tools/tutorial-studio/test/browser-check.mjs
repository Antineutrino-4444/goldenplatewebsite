import assert from 'node:assert/strict';
import { writeFile, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { startServer, launchBrowser, openRenderer, setFrame, screenshot, repoRoot, toolRoot } from '../engine/runtime.mjs';
import recipe from '../recipes/registration.mjs';
import { timeline } from '../engine/timeline.mjs';

const output = resolve(repoRoot, 'output/tutorial-studio/browser-verification'); await mkdir(output, { recursive: true });
const local = await startServer(resolve(toolRoot, 'recipes/registration.mjs'));
let browser;
try {
  browser = await launchBrowser();
  const renderer = await openRenderer(browser, local.url);
  const frames = [], measured = [];
  for (const scene of timeline(recipe)) {
    for (const time of [0, 0.65, 1.2, 1.8, 2, ...(scene.kind === 'closing' ? [4.8, 5.2, 5.55, 5.9, 6.25, 6.6, 7.2] : []), ...(scene.actions || []).flatMap(a => [a.at + 0.1, a.at + (a.duration || 0.4) + 0.1]), scene.duration - 0.02]) {
      if (time >= scene.renderDuration) continue;
      const audit = await setFrame(renderer, scene.index, Math.round(time * recipe.fps), recipe.fps);
      assert.equal(audit.issues.length, 0);
      for (const click of audit.clicks) {
        const rect = audit.bounds[click.target];
        assert(click.x >= rect.x - 12 && click.x <= rect.x + rect.width + 12, `Click x outside target: ${scene.id}`);
        assert(click.y >= rect.y - 12 && click.y <= rect.y + rect.height + 12, `Click y outside target: ${scene.id}`);
      }
      measured.push({ scene: scene.id, time, bounds: audit.bounds, camera: audit.camera, clicks: audit.clicks });
    }
    const click = scene.actions?.at(-1);
    if (click?.type === 'click') {
      await setFrame(renderer, scene.index, Math.round((click.at + 0.12) * recipe.fps), recipe.fps);
      assert(await renderer.page.locator(`[data-click-indicator="${click.target}"]`).count());
      await writeFile(resolve(output, `${scene.id}-click.png`), await screenshot(renderer));
    }
  }
  // Arbitrary seek order must reproduce exactly the same 4K pixels, including caret state.
  await setFrame(renderer, 3, 144, 60); const first = await screenshot(renderer);
  assert.equal(first.readUInt32BE(16), 3840, 'Native PNG width must be 4K.');
  assert.equal(first.readUInt32BE(20), 2160, 'Native PNG height must be 4K.');
  await setFrame(renderer, 9, 520, 60); await setFrame(renderer, 3, 144, 60); const repeated = await screenshot(renderer);
  const digest = value => createHash('sha256').update(value).digest('hex');
  assert.equal(digest(first), digest(repeated), 'The same frame changed after seeking.');
  // Exercise the development client's 30-second ping boundary as well as short scenes.
  await renderer.page.waitForTimeout(31000);
  await setFrame(renderer, 3, 144, 60);
  const afterIdle = await screenshot(renderer);
  await writeFile(resolve(output, 'repeatability-first.png'), first);
  await writeFile(resolve(output, 'repeatability-after-idle.png'), afterIdle);
  assert.equal(digest(first), digest(afterIdle), 'An idle browser changed the frame or emitted an error.');
  assert(await renderer.page.evaluate(() => CSS.supports('caret-animation', 'manual')));
  const last = await setFrame(renderer, 9, Math.round(recipe.scenes[9].duration * 60) - 1, 60);
  const child = renderer.page.frames().find(f => f.url().endsWith('/demo.html'));
  assert(await child.getByRole('button', { name: 'Logging in...', exact: true }).count());
  assert.equal(last.clicks.length, 0); // The walkthrough still ends after the Login click.
  await writeFile(resolve(output, 'login-hold.png'), await screenshot(renderer));
  const closing = recipe.scenes.findIndex(s => s.kind === 'closing');
  await setFrame(renderer, closing, 180, 60);
  assert(await renderer.page.getByRole('heading', { name: 'Getting started in your school account.', exact: true }).count());
  assert.equal(await renderer.page.locator('.studio-pointer-layer').count(), 0);
  const intro = await renderer.page.locator('[data-closing-part="intro"]').boundingBox();
  const arrow = await renderer.page.locator('[data-ending-plate]').boundingBox();
  assert(intro.y + intro.height < arrow.y, 'The closing arrow overlaps its title.');
  await writeFile(resolve(output, 'closing-hold.png'), await screenshot(renderer));
  await setFrame(renderer, closing, Math.round(recipe.scenes[closing].duration * 60) - 1, 60);
  assert.equal(await renderer.page.locator('.studio-ending-fade').count(), 0);
  assert.equal(await renderer.page.locator('.studio-signoff').evaluate(e => getComputedStyle(e).visibility), 'visible');
  const leaf = await renderer.page.locator('.studio-signoff .plate-mark i').boundingBox();
  assert(leaf.width > 30 && leaf.height > 50, 'The final native leaf must remain a full leaf shape.');
  assert.equal(await renderer.page.locator('.studio-website').evaluate(e => getComputedStyle(e).opacity), '0');
  await writeFile(resolve(output, 'final-frame.png'), await screenshot(renderer));
  for (const time of [4.8, 5.2, 5.55, 5.9, 6.25, 6.6, 7.2]) {
    await setFrame(renderer, closing, Math.round(time * 60), 60);
    await writeFile(resolve(output, `closing-motion-${time}.png`), await screenshot(renderer));
  }
  await renderer.context.close();

  // Drive the actual frontend handlers in an interactive demo, rather than only rendering props.
  const context = await browser.newContext({ viewport: { width: 1800, height: 1200 }, colorScheme: 'dark' });
  const delivered = [];
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin !== local.url || url.pathname.startsWith('/api/')) { delivered.push(url.pathname); return route.abort(); }
    return route.continue();
  });
  const page = await context.newPage(); await page.goto(`${local.url}/demo.html`, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => window.__demo?.ready());
  await page.evaluate(() => window.__demo.apply({ page: 'register', state: {}, caretVisible: true }));
  await page.locator('#school-email').fill('school@example.org');
  await page.getByRole('button', { name: 'Send Code', exact: true }).click();
  for (let i = 1; i <= 6; i++) await page.getByLabel(`Verification code digit ${i}`, { exact: true }).fill(String(i));
  await page.getByRole('button', { name: 'Verify Code', exact: true }).click();
  await page.locator('#school-name').fill(recipe.example.schoolName); await page.locator('#school-code').fill(recipe.example.schoolCode);
  await page.locator('#admin-display-name').fill(recipe.example.schoolAdminDisplayName); await page.locator('#admin-username').fill(recipe.example.schoolAdminUsername); await page.locator('#admin-password').fill(recipe.example.schoolAdminPassword);
  await page.getByRole('button', { name: 'Submit Registration Request', exact: true }).click();
  assert(await page.getByRole('button', { name: 'Submitting...', exact: true }).count());
  const audit = await page.evaluate(() => window.__demo.audit());
  assert.deepEqual(audit.events.map(e => e.action), ['sendCode', 'verifyCode', 'register']);
  await page.evaluate(() => window.__demo.apply({ page: 'login', state: {}, caretVisible: true }));
  await page.locator('#username').fill(recipe.example.schoolAdminUsername); await page.locator('#password').fill(recipe.example.schoolAdminPassword);
  await page.getByRole('button', { name: 'Login', exact: true }).click();
  assert(await page.getByRole('button', { name: 'Logging in...', exact: true }).count());
  assert.equal(delivered.length, 0, 'A demonstration attempted a backend or external request.');
  await context.close();

  // The playback shell remains usable at each required preview width.
  for (const width of [390, 768, 1440]) {
    const preview = await openRenderer(browser, local.url, { width, height: Math.round(width * 9 / 16), exportMode: false });
    await setFrame(preview, 3, 120, 60);
    assert.equal(await preview.page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await preview.page.screenshot({ path: resolve(output, `preview-${width}.png`), fullPage: true });
    await preview.context.close();
  }
  await writeFile(resolve(output, 'report.json'), JSON.stringify({ checkedStates: measured.length, actualFrontendWorkflow: 'pass', externalOrBackendRequests: delivered, deterministicFrameSha256: digest(first), viewportWidths: [390, 768, 1440], frames: measured }, null, 2));
  console.log(`Browser checks passed: ${measured.length} rendered states, actual registration/login handlers, deterministic 4K pixels, click indicators, and 3 preview widths.`);
} finally { await browser?.close(); await local.server.close(); }
