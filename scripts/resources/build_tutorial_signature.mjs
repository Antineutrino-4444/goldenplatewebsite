// Rebuild the companion assets for the selected 4K "quicker start" signature.
// Usage: node scripts/resources/build_tutorial_signature.mjs [output-directory] [dark-source.mp4]
// Default exports use the checked-in MP4s and PNGs directly, without a browser.
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { once } from 'node:events';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import path from 'node:path';

const { chromium } = createRequire(import.meta.url)('playwright');
const templates = path.resolve('src/services/templates');
const output = path.resolve(process.argv[2] || templates);
const master = path.resolve(process.argv[3] || path.join(templates, 'tutorial-signature-dark.mp4'));
const darkSource = await readFile(master);
const expected = 'bad223619751f92e550835242979dda3354472bcd41c5ec3236e3c5a53580e45';
if (createHash('sha256').update(darkSource).digest('hex') !== expected) {
  throw new Error('Expected the November 24, 02:22 quicker-start 4K dark master.');
}
await mkdir(output, { recursive: true });
const darkOutput = path.join(output, 'tutorial-signature-dark.mp4');
if (darkOutput !== master) await writeFile(darkOutput, darkSource);
const markCss = await readFile('frontend/src/components/LandingPage.css', 'utf8');

const fps = 60, duration = 2.6, playbackSpeed = 1.5;
const initialHead = -48, startSpeed = 180, curlSpeed = 1550;
const offscreenLead = 2048, wireWidth = 8;
const radius = 82, cx = 960, cy = 460, transitionLength = 180;
const theta = transitionLength / (2 * radius);
const join = { x: cx + radius * Math.sin(theta), y: cy + radius * Math.cos(theta) };
// A clothoid raises curvature gradually from zero to the plate's 1/radius.
// This makes both the tangent AND curvature continuous at the circular rim.
const samples = [{ x: 0, y: 0 }];
let x = 0, y = 0;
const step = 0.5;
for (let distance = step; distance <= transitionLength; distance += step) {
  const midpoint = distance - step / 2;
  const heading = -(midpoint * midpoint) / (2 * radius * transitionLength);
  x += step * Math.cos(heading);
  y += step * Math.sin(heading);
  samples.push({ x, y });
}
const start = { x: join.x - x, y: join.y - y };
const straightLength = start.x + 12;
const entryLength = straightLength + transitionLength;
const circumference = 2 * Math.PI * radius;
const strandLength = circumference * 1.1;
const wrapLength = strandLength;
const totalLength = entryLength + wrapLength;
// Start entirely offscreen, including the rounded tip. The wire's velocity
// increases monotonically from a small initial speed to the curl speed, never exceeding
// that speed. Acceleration reaches zero exactly at the circular rim handoff.
const accelerationDuration = (entryLength - initialHead) / (startSpeed + (curlSpeed - startSpeed) * 2 / 3);
function headDistanceAt(t) {
  if (t <= 0) return initialHead;
  if (t >= accelerationDuration) return entryLength + (t - accelerationDuration) * curlSpeed;
  const u = t / accelerationDuration;
  return initialHead + accelerationDuration * (startSpeed * u + (curlSpeed - startSpeed) * (u * u - u * u * u / 3));
}
const finish = accelerationDuration + wrapLength / curlSpeed;
// A real finite strand, 10% longer than the rim, moves as one piece. Its tail
// naturally enters before the head wraps. The small surplus travels over the
// same circular path, completing the rim without shortening or thickening it.
const points = [{ x: -12 - offscreenLead, y: start.y }, { x: -12, y: start.y }, ...samples.map(p => ({ x: start.x + p.x, y: start.y + p.y }))];
for (let distance = step; distance < wrapLength; distance += step) {
  const angle = theta + distance / radius;
  points.push({ x: cx + radius * Math.sin(angle), y: cy + radius * Math.cos(angle) });
}
points.push({ x:cx+radius*Math.sin(theta+wrapLength/radius), y:cy+radius*Math.cos(theta+wrapLength/radius) });
const trajectory = points.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(5)},${p.y.toFixed(5)}`).join(' ');
const circle = `M${join.x},${join.y} A82,82 0 1 0 ${cx - radius * Math.sin(theta)},${cy - radius * Math.cos(theta)} A82,82 0 1 0 ${join.x},${join.y}`;
function scene(paper) {
  return `<html><head><style>${markCss}
  *{box-sizing:border-box}html,body{margin:0;width:1920px;height:1080px;overflow:hidden;background:${paper};--site-paper:${paper}}
  svg{position:absolute;inset:0;width:1920px;height:1080px;fill:none;stroke:#bf9341;stroke-linecap:round;stroke-linejoin:round}
  #leaf{position:absolute;left:874px;top:374px;width:172px;height:172px}
  #leaf .plate-mark{position:absolute;width:43px;height:43px;transform:scale(4);transform-origin:top left;border-color:transparent}
  #leaf .plate-mark>span{border-color:transparent}
  #leaf .plate-mark i{transform:rotate(20deg) scale(var(--growth,0));transform-origin:bottom left}
</style></head><body><svg viewBox="0 0 1920 1080">
  <path id="wire" d="${trajectory}" stroke-width="${wireWidth}"/>
  <path id="rim" d="${circle}" stroke-width="${wireWidth}" visibility="hidden"/>
  <circle id="inner" cx="960" cy="460" r="60" transform="rotate(-45 960 460)" stroke-width="4"/>
  </svg><div id="leaf"><span class="plate-mark"><span></span><i></i></span></div>
  <script>
  function smooth(progress) {
    const u = Math.max(0, Math.min(1, progress));
    return u * u * u * (10 + u * (-15 + 6 * u));
  }
  const wire = document.querySelector('#wire');
  const rim = document.querySelector('#rim');
  const inner = document.querySelector('#inner');
  const leaf = document.querySelector('#leaf');
  const length = wire.getTotalLength(), innerLength = inner.getTotalLength();
  const initialHead = ${initialHead}, startSpeed = ${startSpeed}, entryLength = ${entryLength};
  const curlSpeed = ${curlSpeed}, accelerationDuration = ${accelerationDuration};
  ${headDistanceAt.toString()}
  window.seek = t => {
    const head = Math.min(${totalLength}, headDistanceAt(t));
    const tailDistance = head - ${strandLength};
    const tail = ${offscreenLead} + tailDistance;
    // Head and tail share the exact same speed, with constant strand length.
    wire.style.strokeDasharray = '${strandLength} ' + (length + 20);
    wire.style.strokeDashoffset = -tail;
    wire.style.visibility = t < ${finish} ? 'visible' : 'hidden';
    rim.style.visibility = t >= ${finish} ? 'visible' : 'hidden';
    const innerProgress = smooth((t - (${finish} - 0.23)) / 0.56);
    inner.style.strokeDasharray = innerLength;
    inner.style.strokeDashoffset = (1 - innerProgress) * innerLength;
    inner.style.visibility = innerProgress > 0 ? 'visible' : 'hidden';
    leaf.style.setProperty('--growth', smooth((t - (${finish} - 0.04)) / 0.5));
  };
  window.seek(0);
  </script></body></html>`;
}

async function renderLightFilm(page) {
  const encoder = spawn('ffmpeg', [
    '-y', '-hide_banner', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps),
    '-i', 'pipe:0', '-an', '-c:v', 'libx264', '-crf', '15', '-preset', 'fast',
    '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p',
    '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
    '-movflags', '+faststart', path.join(output, 'tutorial-signature-light.mp4'),
  ], { stdio: ['pipe', 'ignore', 'inherit'] });
  const completed = once(encoder, 'close');
  const frames = Math.round(duration * fps / playbackSpeed);
  for (let frame = 0; frame < frames; frame++) {
    await page.evaluate(t => window.seek(t), frame / fps * playbackSpeed);
    if (!encoder.stdin.write(await page.screenshot())) await once(encoder.stdin, 'drain');
  }
  encoder.stdin.end();
  const [status] = await completed;
  if (status !== 0) throw new Error(`ffmpeg exited with status ${status}.`);
}

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
try {
  for (const [theme, paper] of [['dark', '#101a16'], ['light', '#f8f7f0']]) {
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 });
    await page.setContent(scene(paper));
    if (theme === 'light') await renderLightFilm(page);
    await page.evaluate(t => window.seek(t), duration);
    await page.addStyleTag({ content: 'html,body{background:transparent}' });
    await page.screenshot({ path: path.join(output, `tutorial-plate-${theme}.png`),
      omitBackground: true, clip: { x: 848, y: 348, width: 224, height: 224 } });
    await page.close();
  }
} finally {
  await browser.close();
}
