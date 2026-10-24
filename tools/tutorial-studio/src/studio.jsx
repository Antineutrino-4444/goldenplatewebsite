import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { flushSync } from 'react-dom';
import { PlateMark } from '@/components/PublicHeader.jsx';
import recipe from 'virtual:tutorial-recipe';
import { clamp, ease, timeline, durationOf, sceneSnapshot, cursorAt, roundedPath, fitCamera, project, checkLayout } from '../engine/timeline.mjs';
import { closingMotion } from '../engine/closing.mjs';
import './studio.css';

const scenes = timeline(recipe), total = durationOf(recipe);
const panel = { x: 560, y: 144, width: 1296, height: 816 };
const cardBounds = { x: 64, y: 425, width: 432, height: 262 };
const params = new URLSearchParams(location.search), exporting = params.has('export');
let controller;
let targetCache = new Map();

function targetElement(doc, key) {
  const cached = targetCache.get(key);
  if (cached?.isConnected) return cached;
  const spec = recipe.targets[key];
  if (!spec) throw new Error(`Unknown target key: ${key}`);
  let element;
  if (spec.selector) element = doc.querySelector(spec.selector);
  else if (spec.role === 'button') {
    element = [...doc.querySelectorAll('button,[role="button"]')].find(e => (e.textContent || '').trim() === spec.name);
  }
  if (!element) throw new Error(`Target not found: ${key}`);
  targetCache.set(key, element);
  return element;
}
function box(element) {
  const r = element.getBoundingClientRect(), style = element.ownerDocument.defaultView.getComputedStyle(element);
  let radii = ['borderTopLeftRadius', 'borderTopRightRadius', 'borderBottomRightRadius', 'borderBottomLeftRadius'].map(k => parseFloat(style[k]) || 0);
  // Segment buttons inherit the shape of an overflow-clipping tab container.
  const parent = element.parentElement, ps = parent && element.ownerDocument.defaultView.getComputedStyle(parent), pr = parent?.getBoundingClientRect();
  if (parent && ['hidden', 'clip'].includes(ps.overflow) && radii.every(n => n === 0)) {
    const parentRadii = ['borderTopLeftRadius', 'borderTopRightRadius', 'borderBottomRightRadius', 'borderBottomLeftRadius'].map(k => Math.max(0, (parseFloat(ps[k]) || 0) - (parseFloat(ps.borderWidth) || 0)));
    radii = [Math.abs(r.left - pr.left) < 3 ? parentRadii[0] : 0, Math.abs(r.right - pr.right) < 3 ? parentRadii[1] : 0,
      Math.abs(r.right - pr.right) < 3 ? parentRadii[2] : 0, Math.abs(r.left - pr.left) < 3 ? parentRadii[3] : 0];
  }
  return { x: r.x, y: r.y, width: r.width, height: r.height, radii };
}
function targetBox(doc, key) {
  const spec = recipe.targets[key];
  if (spec?.union) {
    const parts = spec.union.map(id => targetBox(doc, id));
    const x = Math.min(...parts.map(r => r.x)), y = Math.min(...parts.map(r => r.y));
    return { x, y, width: Math.max(...parts.map(r => r.x + r.width)) - x, height: Math.max(...parts.map(r => r.y + r.height)) - y,
      radii: [parts[0].radii[0], parts.at(-1).radii[1], parts.at(-1).radii[2], parts[0].radii[3]] };
  }
  return box(targetElement(doc, key));
}
function leaderRoute(scene, target) {
  if (scene.leader === 'above') {
    const end = { x: target.x + target.width / 2, y: target.y };
    return { points: [[496, 556], [534, 556], [534, 131], [end.x, 131], [end.x, end.y]], end };
  }
  if (scene.leader === 'below') {
    const end = { x: target.x + target.width / 2, y: target.y + target.height };
    return { points: [[496, 556], [534, 556], [534, 942], [end.x, 942], [end.x, end.y]], end };
  }
  const end = { x: target.x, y: target.y + target.height / 2 };
  return { points: [[496, 556], [530, 556], [546, end.y], [end.x, end.y]], end };
}
function measureCamera(current, doc, raw) {
  if (current.camera?.fullPage) return { x: 0, y: 0, width: 1800, height: 1133.333333, scale: panel.width / 1800 };
  const card = box(doc.querySelector('[data-slot="card"]'));
  const contexts = current.camera?.card ? [card] : (current.camera?.targets || current.highlights).map(key => raw[key]);
  const camera = fitCamera(contexts, panel, current.camera);
  camera.x = Math.max(0, card.x + card.width / 2 - camera.width / 2);
  if (current.camera?.topAnchor) {
    const anchor = doc.querySelector(current.camera.topAnchor);
    if (!anchor) throw new Error(`Camera anchor not found: ${current.camera.topAnchor}`);
    camera.y = Math.max(0, box(anchor).y - (current.camera.topPadding ?? 20));
  }
  return camera;
}

function Studio() {
  const iframe = useRef(null), shell = useRef(null), playback = useRef(null);
  const [model, setModel] = useState({ index: 0, seconds: 0, snapshot: null, camera: null, bounds: {}, issues: [], clicks: [], cursor: { visible: false } });
  const [loaded, setLoaded] = useState(false), [playing, setPlaying] = useState(false), [previewScale, setPreviewScale] = useState(1);
  const [error, setError] = useState('');
  const previousScene = useRef(-1), cameraCache = useRef(null), originalBounds = useRef({});
  const scene = scenes[model.index], local = model.seconds;

  async function setFrame(index, frame, fps = recipe.fps) {
    const current = scenes[index];
    if (!current) throw new Error(`Scene index out of range: ${index}`);
    const seconds = Math.max(0, frame / fps), snapshot = sceneSnapshot(current, seconds);
    let camera = null, bounds = {}, issues = [], cursor = { visible: false }, clicks = [];
    if (!current.kind) {
      const child = iframe.current.contentWindow, doc = child.document;
      if (!child.__demo?.ready()) throw new Error('Website renderer is not ready.');
      const needed = new Set([...(current.highlights || []), ...(current.actions || []).map(a => a.target), ...(current.camera?.targets || [])]);
      if (previousScene.current !== index) {
        targetCache = new Map(); cameraCache.current = null; originalBounds.current = {};
        child.__demo.apply({ page: current.page, state: sceneSnapshot(current, 0).state, caretVisible: false });
        const initial = Object.fromEntries([...needed].map(key => [key, targetBox(doc, key)]));
        cameraCache.current = measureCamera(current, doc, initial);
        originalBounds.current = Object.fromEntries(Object.entries(initial).map(([key, value]) => [key, project(value, cameraCache.current, panel)]));
      }
      child.__demo.apply({ page: current.page, state: snapshot.state, caretVisible: Math.floor(seconds * 2) % 2 === 0 });
      const raw = {};
      for (const key of needed) raw[key] = targetBox(doc, key);
      if (!cameraCache.current) cameraCache.current = measureCamera(current, doc, raw);
      camera = cameraCache.current;
      for (const [key, value] of Object.entries(raw)) bounds[key] = project(value, camera, panel);
      if (!Object.keys(originalBounds.current).length) originalBounds.current = structuredClone(bounds);
      if (snapshot.focus) {
        let key = snapshot.focus;
        if (key === 'code1') {
          const digit = Math.min((snapshot.state.emailVerificationCode || '').length + 1, 6);
          doc.querySelector(`[aria-label="Verification code digit ${digit}"]`)?.focus({ preventScroll: true });
        } else {
          const element = targetElement(doc, key); element.focus({ preventScroll: true });
          if (typeof element.setSelectionRange === 'function' && !['email', 'number'].includes(element.type)) {
            try { element.setSelectionRange(element.value.length, element.value.length); } catch { /* Some native input types have no selection. */ }
          }
        }
      } else doc.activeElement?.blur?.();
      const highlights = Object.fromEntries((current.highlights || []).map(key => [key, bounds[key]]));
      issues = checkLayout(highlights, panel, cardBounds);
      for (const key of current.highlights || []) {
        const spec = recipe.targets[key];
        if (!spec?.selector?.startsWith('#')) continue;
        const label = doc.querySelector(`label[for="${spec.selector.slice(1)}"]`);
        if (!label) continue;
        const r = project(box(label), camera, panel);
        if (r.y < panel.y + 2 || r.y + r.height > panel.y + panel.height - 2) issues.push(`Target label clipped: ${key}`);
      }
      cursor = cursorAt(current, seconds, originalBounds.current);
      clicks = (current.actions || []).filter(a => ['type', 'click', 'focus'].includes(a.type) && seconds >= a.at && seconds < a.at + 0.75).map(a => {
        const r = originalBounds.current[a.target], position = a.position || (a.type === 'click' ? [0.5, 0.5] : [0.18, 0.5]);
        return { target: a.target, age: seconds - a.at, x: r.x + r.width * position[0], y: r.y + r.height * position[1] };
      });
    }
    previousScene.current = index;
    const next = { index, seconds, snapshot, camera, bounds, issues, cursor, clicks };
    flushSync(() => setModel(next));
    if (iframe.current) { iframe.current.parentElement.scrollTop = 0; iframe.current.parentElement.scrollLeft = 0; iframe.current.contentWindow.scrollTo(0, 0); }
    if (camera) {
      const observed = iframe.current.getBoundingClientRect(), stage = document.querySelector('.studio-stage').getBoundingClientRect(), scale = stage.width / 1920;
      const x = (observed.x - stage.x) / scale, y = (observed.y - stage.y) / scale;
      if (Math.abs(x - (panel.x - camera.x * camera.scale)) > 0.5 || Math.abs(y - (panel.y - camera.y * camera.scale)) > 0.5) issues.push('Website viewport scrolled away from its highlights.');
    }
    const card = document.querySelector('.studio-instruction');
    if (card && card.scrollHeight > card.clientHeight + 1) issues.push(`Instruction text clipped: ${current.id}`);
    const caption = document.querySelector('.studio-caption');
    if (caption && caption.scrollHeight > 64) issues.push(`Subtitle exceeds two lines: ${current.id}`);
    const stageRect = document.querySelector('.studio-stage').getBoundingClientRect();
    for (const part of document.querySelectorAll('[data-closing-part]')) {
      const r = part.getBoundingClientRect(), scale = stageRect.width / 1920;
      if (r.left < stageRect.left + 64 * scale || r.right > stageRect.right - 64 * scale || r.top < stageRect.top + 144 * scale || r.bottom > stageRect.top + 960 * scale) issues.push(`Closing content clipped: ${part.dataset.closingPart}`);
    }
    const platePath = document.querySelector('[data-ending-plate]');
    if (platePath) {
      const r = platePath.getBoundingClientRect(), scale = stageRect.width / 1920;
      if (r.left < stageRect.left + 64 * scale || r.right > stageRect.right - 64 * scale || r.top < stageRect.top + 144 * scale || r.bottom > stageRect.top + 960 * scale) issues.push('Animated plate leaves the safe composition area.');
    }
    return { scene: current.id, seconds, bounds, camera, issues, cursor, clicks, state: snapshot.state };
  }
  controller = { setFrame, scenes, recipe: { id: recipe.id, fps: recipe.fps, width: recipe.width, height: recipe.height, duration: total }, loaded };

  useEffect(() => {
    const resize = () => setPreviewScale(exporting ? 1 : Math.min(1, shell.current.clientWidth / 1920));
    const observer = new ResizeObserver(resize); observer.observe(shell.current); resize(); return () => observer.disconnect();
  }, []);
  useEffect(() => { if (loaded) setFrame(Number(params.get('scene') || 0), Number(params.get('frame') || 0)).catch(e => setError(e.message)); }, [loaded]);
  useEffect(() => {
    if (!playing) return;
    let cancelled = false, last = performance.now(), global = scenes[model.index].at + model.seconds;
    async function tick(now) {
      if (cancelled) return;
      global += (now - last) / 1000; last = now;
      if (global >= total) { setPlaying(false); return; }
      const active = scenes.findLast(s => s.at <= global);
      try { await setFrame(active.index, Math.round((global - active.at) * recipe.fps)); } catch (e) { setError(e.message); setPlaying(false); }
      playback.current = requestAnimationFrame(tick);
    }
    playback.current = requestAnimationFrame(tick); return () => { cancelled = true; cancelAnimationFrame(playback.current); };
  }, [playing]);

  const enter = ease((local - 0.35) / 0.65), leave = scene.index === scenes.length - 1 ? 0 : ease((local - scene.duration + 0.05) / 0.3);
  const appear = enter * (1 - leave), editorial = (model.index ? clamp((local - 0.3) / 0.2) : 1) * (scene.index === scenes.length - 1 ? 1 : 1 - clamp((local - scene.duration + 0.05) / 0.25));
  const visibleTargets = (scene.highlights || []).filter(key => model.bounds[key]);
  const leader = visibleTargets.length ? leaderRoute(scene, model.bounds[visibleTargets[0]]) : null;
  const press = model.clicks.some(c => c.age < 0.14);
  const closingIntro = ease((local - 0.35) / 0.65);
  const finish = closingMotion(local), closing = scene.kind === 'closing';
  return <div className={`studio-app ${exporting ? 'studio-export' : ''}`}>
    {!exporting && <div className="studio-preview-title"><span>Golden Plate · Tutorial studio</span><span>Registration & first login</span></div>}
    <div ref={shell} className="studio-player" style={{ height: exporting ? 1080 : 1080 * previewScale }}>
      <div className="studio-stage" style={{ transform: `scale(${previewScale})` }}>
        <header className="studio-header" style={closing ? { clipPath: `inset(0 ${finish.retract * 100}% 0 0)` } : undefined}><div className="studio-brand"><PlateMark /><div>golden plate<small>The school guide</small></div></div><span>SCHOOL REGISTRATION&nbsp; / &nbsp;FIRST LOGIN</span></header>
        <div className="studio-website" style={{ left: panel.x, top: panel.y, width: panel.width, height: panel.height, opacity: scene.kind ? 0 : 1 }}>
          <iframe ref={iframe} title="Golden Plate demonstration" src="/demo.html" onLoad={async () => {
            const doc = iframe.current.contentDocument;
            await doc.fonts.ready;
            const wait = () => { if (iframe.current.contentWindow.__demo?.ready()) setLoaded(true); else setTimeout(wait, 30); }; wait();
          }} style={{ transform: model.camera ? `translate(${-model.camera.x * model.camera.scale}px,${-model.camera.y * model.camera.scale}px) scale(${model.camera.scale})` : 'none' }} />
        </div>
        {!scene.kind && <div className="studio-website-frame" style={{ left: panel.x, top: panel.y, width: panel.width, height: panel.height }} />}
        <div className="studio-editorial" style={{ opacity: editorial }}>
          {scene.kind === 'closing' ? <div className="studio-closing">
            <div data-closing-part="intro">
              <p className="studio-closing-label" style={{ opacity: closingIntro, clipPath: `inset(0 ${finish.retract * 100}% 0 0)` }}>{scene.subtitle}</p>
              <h1>{scene.title.split('\n').map((line, i) => {
                const reveal = ease((local - 0.4 - i * 0.18) / 0.72);
                const exit = ease((local - 5 - i * 0.1) / 0.6);
                return <span className="studio-closing-line" key={i}><span style={{ opacity: reveal, transform: `translateY(${28 * (1 - reveal) - 110 * exit}px)` }}>{line}</span></span>;
              })}</h1>
              <p className="studio-closing-description" style={{ opacity: ease((local - 1.1) / 0.55), clipPath: `inset(0 0 ${finish.retract * 100}% 0)` }}>{scene.description}</p>
            </div>
          </div> : scene.kind ? <div className={`studio-chapter studio-chapter-${scene.kind}`}>
            <p>{scene.kind === 'approval' ? 'BEFORE YOU SIGN IN' : scene.subtitle}</p>
            <h1>{scene.title}</h1><div className="studio-chapter-rule" />
            {scene.kind === 'approval' ? <><div className="studio-chapter-description">{scene.subtitle}</div><div className="studio-approval-strip" style={{ opacity: appear, transform: `translateX(${-20 * (1 - appear)}px)` }}>Request submitted&nbsp;&nbsp; / &nbsp;&nbsp;PLATE approval&nbsp;&nbsp; / &nbsp;&nbsp;Login</div></> : <div className="studio-chapter-description">Email verification&nbsp; · &nbsp;School approval&nbsp; · &nbsp;First login</div>}
          </div> : <>
            <div className="studio-sidebar-label">{scene.label}</div><h1 className="studio-sidebar-title">{scene.title}</h1>
            <div className="studio-instruction" style={{ opacity: appear, transform: `translate(${-20 * (1 - appear)}px,${8 * (1 - appear)}px)` }}><div>WHAT TO DO</div><p>{scene.instruction}</p></div>
            <svg className="studio-overlay" viewBox="0 0 1920 1080" aria-hidden="true">
              {visibleTargets.map((key, i) => <path key={key} d={roundedPath(model.bounds[key], 0.75)} pathLength="1" strokeDasharray="1" strokeDashoffset={1 - ease((local - 0.85 - i * 0.07) / 0.55)} fill="none" stroke="var(--studio-gold)" strokeWidth="1.5" />)}
              {leader && <g opacity={ease((local - 1.43) / 0.18)}><polyline points={leader.points.map(p => p.join(',')).join(' ')} fill="none" stroke="var(--studio-gold)" strokeWidth="1.5" strokeLinejoin="round" /><circle cx={leader.end.x} cy={leader.end.y} r="2.5" fill="var(--studio-gold)" /></g>}
            </svg>
          </>}
          <div className="studio-caption" style={closing ? { clipPath: `inset(0 0 ${finish.retract * 100}% 0)` } : undefined}>{scene.caption}</div>
        </div>
        {closing && <>
          <svg className="studio-closing-morph" viewBox="0 0 1920 1080" aria-hidden="true">
            <path data-ending-plate d={finish.path} pathLength="1" strokeDasharray="1" strokeDashoffset={1 - ease((local - 0.85) / 0.85)} style={{ stroke: finish.color, strokeWidth: finish.stroke, visibility: local < 0.85 ? 'hidden' : 'visible' }} />
            <path d="M1174 647.8 L1200 673.8 L1174 699.8" pathLength="1" strokeDasharray="1" strokeDashoffset={1 - ease((local - 1.5) / 0.45) * (1 - finish.headRetraction)} visibility={local > 1.5 && finish.headRetraction < 1 ? 'visible' : 'hidden'} />
            <circle cx="960" cy="460" r="60" pathLength="1" strokeDasharray="1" strokeDashoffset={1 - finish.inner} transform="rotate(-45 960 460)" visibility={finish.inner > 0 ? 'visible' : 'hidden'} style={{ stroke: '#bf9341', strokeWidth: 4 }} />
          </svg>
          <div className="studio-signoff" data-closing-part="signature" style={{ visibility: local < 6.25 ? 'hidden' : 'visible' }}>
            <div className="studio-signoff-mark" style={{ '--leaf-growth': finish.leaf }}><PlateMark /></div>
            <div className="studio-signoff-wordmark"><span style={{ transform: `translateY(${74 * (1 - finish.wordmark)}px)` }}>golden plate</span></div>
            <div className="studio-signoff-guide"><span style={{ transform: `translateY(${36 * (1 - finish.guide)}px)` }}>The school guide</span></div>
            <div className="studio-signoff-next" data-closing-part="next title"><span style={{ transform: `translateY(${40 * (1 - finish.lesson)}px)` }}>Up next: {scene.title.replaceAll('\n', ' ').replace(/\.$/, '')}</span></div>
          </div>
        </>}
        {!scene.kind && <svg className="studio-pointer-layer" viewBox="0 0 1920 1080" aria-hidden="true" style={{ opacity: scene.index === scenes.length - 1 ? 1 : 1 - clamp((local - scene.duration + 0.05) / 0.25) }}>
          {model.clicks.map((click, i) => {
            const age = clamp(click.age / 0.65), rect = model.bounds[click.target];
            return <g key={i} data-click-indicator={click.target}><path d={roundedPath(rect, 1)} fill="var(--studio-gold)" opacity={0.17 * (1 - age)} /><circle cx={click.x} cy={click.y} r={12 + 24 * ease(age)} fill="none" stroke="var(--studio-gold)" strokeWidth={2.2 - age} opacity={1 - age} /><circle cx={click.x} cy={click.y} r={4} fill="var(--studio-gold)" opacity={(1 - age) * 0.8} /></g>;
          })}
          {model.cursor.visible && <g transform={`translate(${model.cursor.x},${model.cursor.y}) scale(${press ? 0.88 : 1})`} opacity={Math.min(1, (local - 0.35) * 3)} filter="url(#cursor-shadow)"><path d="M0 0 L0 26 L7 19 L12 30 L17 27 L12 17 L23 17 Z" fill="#f8f7f0" stroke="#101a16" strokeWidth="1.6" strokeLinejoin="round" /></g>}
          <defs><filter id="cursor-shadow" x="-60%" y="-60%" width="240%" height="240%"><feDropShadow dx="0" dy="1.5" stdDeviation="1.3" floodOpacity="0.5" /></filter></defs>
        </svg>}
        <div className="studio-bottom-rule" style={closing ? { transform: `scaleX(${1 - finish.retract})`, transformOrigin: 'right' } : undefined} /><div className="studio-progress" style={closing ? { transform: `scaleX(${1 - finish.retract})`, transformOrigin: 'left' } : undefined}><div style={{ width: `${clamp((scene.at + local) / total) * 100}%` }} /></div>
      </div>
    </div>
    {!exporting && <div className="studio-controls"><button type="button" onClick={() => setPlaying(!playing)} disabled={!loaded}>{playing ? 'Pause' : 'Play'}</button><label>Scene <select value={model.index} onChange={e => { setPlaying(false); setFrame(Number(e.target.value), 0).catch(e => setError(e.message)); }}>{scenes.map(s => <option key={s.id} value={s.index}>{s.title?.replaceAll('\n', ' ')}</option>)}</select></label><input aria-label="Video timeline" type="range" min="0" max={total} step={1 / recipe.fps} value={scene.at + local} onChange={e => { setPlaying(false); const at = Math.min(total - 1 / recipe.fps, Number(e.target.value)), active = scenes.findLast(s => s.at <= at); setFrame(active.index, Math.round((at - active.at) * recipe.fps)).catch(e => setError(e.message)); }} /><output>{(scene.at + local).toFixed(1)} / {total.toFixed(1)}s</output></div>}
    {!exporting && (error || model.issues.length > 0) && <p className="studio-error" role="alert">{error || model.issues.join(' · ')}</p>}
  </div>;
}
window.__studio = { setFrame: (...args) => controller.setFrame(...args), ready: () => controller?.loaded, info: () => ({ ...controller.recipe, scenes: controller.scenes }) };
createRoot(document.getElementById('root')).render(<Studio />);
