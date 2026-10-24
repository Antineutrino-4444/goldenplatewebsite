export const clamp = (n, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, n));
export const ease = (n) => { const p = clamp(n); return p * p * p * (10 + p * (-15 + 6 * p)); };
export const lerp = (a, b, t) => a + (b - a) * t;

export function validateRecipe(recipe) {
  if (!recipe?.id || !Array.isArray(recipe.scenes) || !recipe.scenes.length) throw new Error('Recipe requires an id and scenes.');
  const ids = new Set();
  for (const scene of recipe.scenes) {
    if (!scene.id || ids.has(scene.id)) throw new Error(`Duplicate/missing scene id: ${scene.id}`);
    ids.add(scene.id);
    if (!Number.isFinite(scene.duration) || scene.duration <= 0) throw new Error(`Invalid duration: ${scene.id}`);
    if (!scene.kind && !['home', 'register', 'login'].includes(scene.page)) throw new Error(`Unknown page provider: ${scene.page}. Add it to src/demo.jsx before using it in a recipe.`);
    for (const key of [...(scene.highlights || []), ...(scene.camera?.targets || []), ...(scene.actions || []).map(a => a.target)]) {
      if (!recipe.targets?.[key]) throw new Error(`Unknown element target ${key} in ${scene.id}`);
    }
    for (const action of scene.actions || []) {
      if (!Number.isFinite(action.at) || action.at < 0 || action.at >= scene.duration) throw new Error(`Action outside scene: ${scene.id}`);
      if (!['type', 'click', 'focus', 'move'].includes(action.type)) throw new Error(`Unknown action: ${action.type}`);
      if (!action.target) throw new Error(`Action needs an element target: ${scene.id}`);
      if (action.type === 'type' && (!action.field || typeof action.value !== 'string' || !action.duration)) throw new Error(`Invalid typing action: ${scene.id}`);
      if (action.type === 'type' && (action.duration <= 0 || action.at + action.duration > scene.duration)) throw new Error(`Typing extends outside scene: ${scene.id}`);
    }
  }
  return recipe;
}

export function timeline(recipe) {
  validateRecipe(recipe);
  let at = 0;
  return recipe.scenes.map((scene, index) => {
    const item = { ...scene, index, at, renderDuration: scene.duration + (index < recipe.scenes.length - 1 ? recipe.transition : 0) };
    at += scene.duration;
    return item;
  });
}
export const durationOf = recipe => recipe.scenes.reduce((total, s) => total + s.duration, 0);

export function sceneSnapshot(scene, seconds) {
  const state = structuredClone(scene.state || {});
  let focus = scene.focus || null;
  const clicks = [];
  for (const action of scene.actions || []) {
    if (seconds < action.at) continue;
    if (action.type === 'type') {
      const progress = clamp((seconds - action.at) / action.duration);
      state[action.field] = action.value.slice(0, Math.floor(action.value.length * progress + 1e-7));
      focus = action.target;
    } else if (action.type === 'focus') focus = action.target;
    else if (action.type === 'click') {
      clicks.push({ ...action, age: seconds - action.at });
      focus = action.keepFocus ? focus : null;
      if (seconds >= action.at + (action.after || 0.3)) Object.assign(state, action.set || {});
    }
  }
  return { state, focus, clicks, seconds };
}

export function cursorAt(scene, seconds, bounds, initial = { x: 1770, y: 900 }) {
  const moves = [];
  for (const action of scene.actions || []) {
    const rect = bounds[action.target];
    if (!rect) continue;
    const end = action.at;
    const travel = action.travel ?? (action.type === 'type' ? 0.65 : 0.75);
    const position = action.position || (action.type === 'type' || action.type === 'focus' ? [0.18, 0.5] : [0.5, 0.5]);
    moves.push({ start: Math.max(0.35, end - travel), end, to: { x: rect.x + rect.width * position[0], y: rect.y + rect.height * position[1] } });
  }
  let from = initial;
  for (const move of moves) {
    if (seconds < move.start) return { ...from, visible: seconds > 0.35 };
    if (seconds < move.end) {
      const t = ease((seconds - move.start) / Math.max(0.001, move.end - move.start));
      return { x: lerp(from.x, move.to.x, t), y: lerp(from.y, move.to.y, t), visible: true };
    }
    from = move.to;
  }
  return { ...from, visible: seconds > 0.35 };
}

export function roundedPath(rect, inset = 0) {
  const x = rect.x + inset, y = rect.y + inset, w = rect.width - 2 * inset, h = rect.height - 2 * inset;
  const corners = rect.radii || [0, 0, 0, 0];
  const [tl, tr, br, bl] = corners.map(r => clamp(r - inset, 0, Math.min(w, h) / 2));
  const arc = (r, endX, endY) => r ? `A${r},${r} 0 0 1 ${endX},${endY}` : `L${endX},${endY}`;
  return `M${x + tl},${y} H${x + w - tr} ${arc(tr, x + w, y + tr)} V${y + h - br} ${arc(br, x + w - br, y + h)} H${x + bl} ${arc(bl, x, y + h - bl)} V${y + tl} ${arc(tl, x + tl, y)} Z`;
}

export function fitCamera(rects, panel, options = {}) {
  if (!rects.length) throw new Error('Camera has no visible elements.');
  const padding = options.padding ?? 64;
  const left = Math.min(...rects.map(r => r.x)) - padding;
  const top = Math.min(...rects.map(r => r.y)) - padding;
  const right = Math.max(...rects.map(r => r.x + r.width)) + padding;
  const bottom = Math.max(...rects.map(r => r.y + r.height)) + padding;
  const aspect = panel.width / panel.height;
  const width = Math.max(options.minWidth || 860, right - left, (bottom - top) * aspect);
  const height = width / aspect;
  return { x: Math.max(0, (left + right - width) / 2), y: Math.max(0, (top + bottom - height) / 2), width, height, scale: panel.width / width };
}

export function project(rect, camera, panel) {
  return { ...rect, x: panel.x + (rect.x - camera.x) * camera.scale, y: panel.y + (rect.y - camera.y) * camera.scale,
    width: rect.width * camera.scale, height: rect.height * camera.scale, radii: rect.radii?.map(r => r * camera.scale) };
}

export function rectGap(a, b) {
  return Math.max(b.x - (a.x + a.width), a.x - (b.x + b.width), b.y - (a.y + a.height), a.y - (b.y + b.height));
}
export function checkLayout(targets, panel, card) {
  const issues = [];
  for (const [id, r] of Object.entries(targets)) {
    if (r.x < panel.x + 2 || r.y < panel.y + 2 || r.x + r.width > panel.x + panel.width - 2 || r.y + r.height > panel.y + panel.height - 2) issues.push(`Target clipped: ${id}`);
    if (rectGap(r, card) < 2) issues.push(`Instruction overlaps target: ${id}`);
  }
  const entries = Object.entries(targets);
  for (let i = 0; i < entries.length; i++) for (let j = i + 1; j < entries.length; j++) {
    if (rectGap(entries[i][1], entries[j][1]) < 2) issues.push(`Highlights collide: ${entries[i][0]} / ${entries[j][0]}`);
  }
  return issues;
}

export function timecode(seconds, separator = '.') {
  let ms = Math.round(seconds * 1000);
  const h = Math.floor(ms / 3600000); ms %= 3600000;
  const m = Math.floor(ms / 60000); ms %= 60000;
  const s = Math.floor(ms / 1000); ms %= 1000;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}${separator}${String(ms).padStart(3, '0')}`;
}
