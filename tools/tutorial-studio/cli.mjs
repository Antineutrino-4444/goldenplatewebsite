#!/usr/bin/env node
import { mkdir, writeFile, readFile, stat, readdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { resolve, dirname, basename } from 'node:path';
import { pathToFileURL } from 'node:url';
import { spawn, spawnSync } from 'node:child_process';
import { once } from 'node:events';
import { createHash } from 'node:crypto';
import { startServer, launchBrowser, openRenderer, setFrame, screenshot, browserOptions, playwrightRuntime, toolRoot, repoRoot } from './engine/runtime.mjs';
import { timeline, durationOf, validateRecipe, timecode } from './engine/timeline.mjs';

const [command = 'help', ...rest] = process.argv.slice(2);
const args = {};
for (let i = 0; i < rest.length; i++) { if (!rest[i].startsWith('--')) throw new Error(`Unexpected argument: ${rest[i]}`); args[rest[i].slice(2)] = rest[i + 1] && !rest[i + 1].startsWith('--') ? rest[++i] : true; }
const recipePath = resolve(args.recipe || resolve(toolRoot, 'recipes/registration.mjs'));
const recipe = validateRecipe((await import(pathToFileURL(recipePath).href)).default);
const scenes = timeline(recipe), fps = Number(args.fps || recipe.fps), width = Number(args.width || recipe.width), height = Number(args.height || recipe.height);
const quality = args.quality === 'draft' ? 'draft' : 'final';
const defaultOutput = resolve(repoRoot, 'output/tutorial-studio', `${recipe.id}-${width}x${height}-${fps}fps.mp4`);
const output = resolve(args.out || defaultOutput);
if (['render', 'verify'].includes(command) && !/\.mp4$/i.test(output)) throw new Error('Choose an output filename ending in .mp4.');
const ffmpeg = process.env.TUTORIAL_FFMPEG || 'ffmpeg', ffprobe = process.env.TUTORIAL_FFPROBE || 'ffprobe';
const selected = args.scenes ? scenes.filter(s => String(args.scenes).split(',').includes(s.id)) : scenes;
if (!selected.length) throw new Error('No requested scene exists in the recipe.');
// Cache validity includes the renderer and the actual frontend, not only the scene recipe.
async function sourceFingerprint() {
  const digest = createHash('sha256').update(await readFile(recipePath));
  for (const root of [resolve(toolRoot, 'engine'), resolve(toolRoot, 'src'), resolve(repoRoot, 'frontend/src'), resolve(repoRoot, 'frontend/public')]) {
    const files = (await readdir(root, { recursive: true, withFileTypes: true })).filter(f => f.isFile()).map(f => resolve(f.parentPath, f.name)).sort();
    for (const file of files) digest.update(file.slice(repoRoot.length)).update(await readFile(file));
  }
  digest.update(await readFile(resolve(toolRoot, 'cli.mjs'))).update(await readFile(resolve(toolRoot, 'demo.html')));
  for (const file of [resolve(toolRoot, 'package-lock.json'), resolve(repoRoot, 'frontend/package-lock.json')]) if (existsSync(file)) digest.update(await readFile(file));
  return digest.digest('hex').slice(0, 16);
}
const hash = await sourceFingerprint();
const scratch = resolve(args.work || resolve(repoRoot, '.tmp/tutorial-studio', `${recipe.id}-${hash}-${width}x${height}-${fps}-${quality}`));
let cancelled = false;
const runningChildren = new Set();
if (['render', 'storyboard'].includes(command)) process.on('SIGINT', () => {
  cancelled = true;
  for (const child of runningChildren) child.kill('SIGTERM');
  console.error('Stopping the render; completed scenes remain available for --resume.');
});

function run(program, argv, options = {}) {
  return new Promise((success, reject) => {
    const child = spawn(program, argv, { stdio: ['ignore', 'pipe', 'pipe'], ...options }); let stdout = '', stderr = '';
    runningChildren.add(child); child.on('close', () => runningChildren.delete(child));
    child.stdout?.on('data', b => { stdout += b; }); child.stderr?.on('data', b => { stderr += b; });
    child.on('error', reject); child.on('close', code => code === 0 ? success(stdout) : reject(new Error(`${program} failed (${code}): ${stderr.slice(-8000)}`)));
  });
}
function subtitles() {
  let vtt = 'WEBVTT\n\n', srt = '', at = 0;
  for (let i = 0; i < selected.length; i++) { const s = selected[i]; vtt += `${timecode(at)} --> ${timecode(at + s.duration)}\n${s.caption}\n\n`; srt += `${i + 1}\n${timecode(at, ',')} --> ${timecode(at + s.duration, ',')}\n${s.caption}\n\n`; at += s.duration; }
  return { vtt, srt };
}
async function withRenderer(fn) {
  const local = await startServer(recipePath, Number(args.port || 0)); let browser;
  try { browser = await launchBrowser(); return await fn(browser, local.url); }
  finally { await browser?.close(); await local.server.close(); }
}

async function storyboard() {
  const destination = args.out ? output : resolve(repoRoot, 'output/tutorial-studio/storyboard'); await mkdir(destination, { recursive: true });
  await withRenderer(async (browser, url) => {
    const renderer = await openRenderer(browser, url, { width, height }); const audits = [];
    for (const scene of selected) {
      const times = args.time ? [Number(args.time)] : [...new Set([0.65, 1.2, 2, ...(scene.actions || []).map(a => a.at + 0.12), scene.duration - 0.15])].filter(t => t < scene.duration);
      for (const t of times) {
        if (cancelled) throw new Error('Storyboard cancelled.');
        const frame = Math.round(t * fps), audit = await setFrame(renderer, scene.index, frame, fps);
        const file = `${String(scene.index + 1).padStart(2, '0')}-${scene.id}-${frame}.png`;
        await writeFile(resolve(destination, file), await screenshot(renderer));
        audits.push({ scene: scene.id, frame, seconds: frame / fps, file, camera: audit.camera, bounds: audit.bounds, issues: audit.issues, clicks: audit.clicks });
      }
      console.log(`Reviewed ${scene.id}`);
    }
    await writeFile(resolve(destination, 'audit.json'), JSON.stringify({ recipe: recipe.id, width, height, fps, audits, blocked: renderer.blocked, pageErrors: renderer.errors }, null, 2));
    await renderer.context.close();
  });
  console.log(`Storyboard: ${destination}`);
}

async function renderScene(browser, url, scene) {
  const destination = resolve(scratch, `${scene.id}.mp4`), manifest = resolve(scratch, `${scene.id}.json`);
  if (args.resume && existsSync(destination) && existsSync(manifest)) {
    const saved = JSON.parse(await readFile(manifest));
    const encodedHash = createHash('sha256').update(await readFile(destination)).digest('hex');
    if (saved.complete && saved.quality === quality && saved.width === width && saved.height === height && saved.fps === fps && saved.recipeHash === hash && saved.browser === browser.version() && saved.encodedSha256 === encodedHash) { console.log(`Reusing ${scene.id}`); return saved; }
  }
  const renderer = await openRenderer(browser, url, { width, height });
  const sceneDuration = scene.index === scenes.length - 1 ? scene.duration : scene.renderDuration;
  const frameCount = Math.round(sceneDuration * fps);
  const encoder = spawn(ffmpeg, ['-y', '-v', 'error', '-f', 'image2pipe', '-vcodec', 'png', '-framerate', String(fps), '-i', 'pipe:0', '-an', '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p,setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709', '-c:v', 'libx264', '-preset', args.quality === 'draft' ? 'ultrafast' : 'fast', '-crf', args.quality === 'draft' ? '20' : '12', '-threads', '2', '-r', String(fps), '-fps_mode', 'cfr', '-video_track_timescale', String(fps * 1000), '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-movflags', '+faststart', destination], { stdio: ['pipe', 'ignore', 'pipe'] });
  let stderr = ''; encoder.stderr.on('data', b => { stderr += b; });
  runningChildren.add(encoder); encoder.on('close', () => runningChildren.delete(encoder));
  const completion = once(encoder, 'close'); const errors = []; encoder.on('error', e => errors.push(e)); encoder.stdin.on('error', e => errors.push(e));
  let checked = 0, clicks = 0, firstAudit, lastAudit, previousClick = '';
  const started = Date.now();
  try {
    for (let frame = 0; frame < frameCount; frame++) {
      if (cancelled) throw new Error('Render cancelled.');
      if (errors.length) throw errors[0];
      const audit = await setFrame(renderer, scene.index, frame, fps); checked++; firstAudit ??= audit; lastAudit = audit;
      const click = audit.clicks.map(c => c.target).join(','); if (click && click !== previousClick) clicks++; previousClick = click;
      if (!encoder.stdin.write(await screenshot(renderer))) await once(encoder.stdin, 'drain');
      if (frame && frame % (fps * 2) === 0) console.log(`${scene.id}: ${Math.round(frame / frameCount * 100)}% (${frame}/${frameCount})`);
    }
    encoder.stdin.end(); const [code] = await completion;
    if (code !== 0) throw new Error(`Scene encoder failed: ${stderr}`);
    const report = { scene: scene.id, complete: true, quality, recipeHash: hash, browser: browser.version(), encodedSha256: createHash('sha256').update(await readFile(destination)).digest('hex'), width, height, fps, frames: frameCount, checkedFrames: checked, visibleClickEvents: clicks, seconds: sceneDuration,
      renderSeconds: (Date.now() - started) / 1000, first: { bounds: firstAudit.bounds, camera: firstAudit.camera }, last: { bounds: lastAudit.bounds, camera: lastAudit.camera }, blocked: renderer.blocked, pageErrors: renderer.errors };
    await writeFile(manifest, JSON.stringify(report, null, 2)); console.log(`Rendered ${scene.id}: ${frameCount} checked frames`); return report;
  } catch (error) { encoder.kill('SIGTERM'); throw error; }
  finally { await renderer.context.close(); }
}

async function render() {
  if (width % 2 || height % 2 || width / height !== 16 / 9 || !Number.isInteger(fps) || fps < 1 || fps > 120) throw new Error('Use even 16:9 dimensions and an integer frame rate from 1 to 120.');
  await mkdir(scratch, { recursive: true }); await mkdir(dirname(output), { recursive: true });
  const reports = await withRenderer(async (browser, url) => {
    let next = 0; const results = [];
    const workers = Math.max(1, Math.min(6, Number(args.workers || 2)));
    await Promise.all(Array.from({ length: Math.min(workers, selected.length) }, async () => {
      while (next < selected.length) { const index = next++; results[index] = await renderScene(browser, url, selected[index]); }
    }));
    return results;
  });
  const argv = ['-y', '-v', 'error', '-filter_complex_threads', '1'];
  for (const s of selected) argv.push('-i', resolve(scratch, `${s.id}.mp4`));
  const graph = selected.map((_, i) => `[${i}:v]settb=AVTB,setpts=PTS-STARTPTS,format=yuv420p[v${i}]`);
  let previous = 'v0', offset = 0;
  for (let i = 1; i < selected.length; i++) { offset += selected[i - 1].duration; graph.push(`[${previous}][v${i}]xfade=transition=fade:duration=${recipe.transition}:offset=${offset}[x${i}]`); previous = `x${i}`; }
  const total = selected.reduce((n, s) => n + s.duration, 0);
  graph.push(`[${previous}]trim=duration=${total},setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709,format=yuv420p[final]`);
  const temp = output.replace(/\.mp4$/i, '') + '.rendering.mp4';
  argv.push('-filter_complex', graph.join(';'), '-map', '[final]', '-t', String(total), '-an', '-r', String(fps), '-fps_mode', 'cfr', '-c:v', 'libx264', '-preset', args.quality === 'draft' ? 'ultrafast' : 'slow', '-crf', args.quality === 'draft' ? '20' : '14', '-threads', '6', '-video_track_timescale', String(fps * 1000), '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-movflags', '+faststart', temp);
  console.log('Composing smooth transitions…'); await run(ffmpeg, argv);
  const { rename } = await import('node:fs/promises'); await rename(temp, output);
  const { vtt, srt } = subtitles(); await writeFile(output.replace(/\.mp4$/i, '.vtt'), vtt); await writeFile(output.replace(/\.mp4$/i, '.srt'), srt);
  await writeFile(output.replace(/\.mp4$/i, '.audit.json'), JSON.stringify({ recipe: recipe.id, recipePath, recipeHash: hash, width, height, fps, duration: total, expectedFrames: Math.round(total * fps), source: 'real frontend components; no screen recording', renderer: 'Golden Plate tutorial studio', scenes: reports }, null, 2));
  await verify(output); console.log(`VIDEO: ${output}`);
}
async function verify(path = output) {
  const meta = JSON.parse(await run(ffprobe, ['-v', 'error', '-show_streams', '-show_format', '-of', 'json', path]));
  const streams = meta.streams; if (streams.length !== 1 || streams[0].codec_type !== 'video') throw new Error('Expected one video stream and no audio.');
  const stream = streams[0], auditPath = path.replace(/\.mp4$/i, '.audit.json');
  const audit = JSON.parse(await readFile(auditPath));
  if (stream.width !== audit.width || stream.height !== audit.height || stream.r_frame_rate !== `${audit.fps}/1` || Number(stream.nb_frames) !== audit.expectedFrames) throw new Error('Export dimensions, frame rate or frame count do not match the render audit.');
  if (['color_space', 'color_transfer', 'color_primaries'].some(k => stream[k] !== 'bt709')) throw new Error('Export must use consistent SDR Rec.709.');
  if (Math.abs(Number(meta.format.duration) - audit.duration) > 1 / audit.fps) throw new Error('Unexpected video duration.');
  if (audit.scenes.some(s => s.checkedFrames !== s.frames || s.pageErrors.length)) throw new Error('Some rendered frames were not checked or had page errors.');
  await run(ffmpeg, ['-v', 'error', '-i', path, '-f', 'null', '-']);
  const result = { resolution: `${stream.width}×${stream.height}`, fps: audit.fps, frames: Number(stream.nb_frames), duration: Number(meta.format.duration), audioStreams: 0, color: 'SDR Rec.709', decode: 'pass', layout: 'every rendered frame checked', bytes: (await stat(path)).size };
  await writeFile(path.replace(/\.mp4$/i, '.verified.json'), JSON.stringify(result, null, 2)); console.log(JSON.stringify(result, null, 2));
}

if (command === 'doctor') {
  console.log(JSON.stringify({ node: process.version, frontendDependencies: existsSync(resolve(repoRoot, 'frontend/node_modules/vite')), playwright: playwrightRuntime().path, browser: browserOptions(), ffmpeg: spawnSync(ffmpeg, ['-version'], { encoding: 'utf8' }).stdout?.split('\n')[0], recipe: recipe.id, duration: durationOf(recipe), scenes: scenes.map(s => s.id), defaultOutput }, null, 2));
} else if (command === 'preview') {
  const local = await startServer(recipePath, Number(args.port || 5199)); console.log(`PREVIEW: ${local.url}`);
  const close = async () => { await local.server.close(); process.exit(0); }; process.on('SIGINT', close); process.on('SIGTERM', close);
} else if (command === 'storyboard') await storyboard();
else if (command === 'render') await render();
else if (command === 'verify') await verify(args.out ? output : defaultOutput);
else {
  console.log(`Golden Plate tutorial studio\n\nnode tools/tutorial-studio/cli.mjs doctor\nnode tools/tutorial-studio/cli.mjs preview [--port 5199]\nnode tools/tutorial-studio/cli.mjs storyboard [--out directory] [--scenes email,school] [--time 2]\nnode tools/tutorial-studio/cli.mjs render [--out video.mp4] [--workers 2] [--resume]\nnode tools/tutorial-studio/cli.mjs verify --out video.mp4\n\nAll commands accept --recipe path/to/recipe.mjs. Render also accepts --width 3840 --height 2160 --fps 60, --scenes, --work, and --quality draft.\nThe preview/render server serves only local frontend assets and starts no backend.`);
}
