import { ease, lerp } from './timeline.mjs';

// Four continuous cubic segments bend through circular arcs from line to plate.
// The final 82px centreline and 8px stroke match the real 43px PlateMark at scale 4.
export function plateLine(progress) {
  const p = Math.min(1, Math.max(0, progress)), angle = 2 * Math.PI * p, length = lerp(1098, 2 * Math.PI * 82, p), rotation = -3 * Math.PI / 4 * p;
  const rotate = v => ({ x: v.x * Math.cos(rotation) - v.y * Math.sin(rotation), y: v.x * Math.sin(rotation) + v.y * Math.cos(rotation) });
  const point = fraction => {
    if (!p) return { x: length * (fraction - 0.5), y: 0 };
    const u = angle * (fraction - 0.5);
    return rotate({ x: length / angle * Math.sin(u), y: length / angle * 2 * Math.sin(u / 2) ** 2 });
  };
  // Translate the arc by its exact bounds, keeping the curl on a direct centre path.
  // This avoids the cusp caused by interpolating a straight line's controls into a circle.
  const extrema = [point(0), point(1)];
  if (p) for (let quadrant = -8; quadrant <= 8; quadrant++) {
    const fraction = (quadrant * Math.PI / 2 + Math.PI / 2 - rotation) / angle + 0.5;
    if (fraction > 0 && fraction < 1) extrema.push(point(fraction));
  }
  const offset = { x: lerp(651, 960, p) - (Math.min(...extrema.map(v => v.x)) + Math.max(...extrema.map(v => v.x))) / 2,
    y: lerp(673.8, 460, p) - (Math.min(...extrema.map(v => v.y)) + Math.max(...extrema.map(v => v.y))) / 2 };
  const world = v => ({ x: v.x + offset.x, y: v.y + offset.y });
  const controlLength = p ? length / angle * (4 / 3 * Math.tan(angle / 16)) : length / 12;
  const start = world(point(0)), segments = [];
  for (let i = 0; i < 4; i++) {
    const from = point(i / 4), to = point((i + 1) / 4);
    const tangent = fraction => rotate({ x: controlLength * Math.cos(angle * (fraction - 0.5)), y: controlLength * Math.sin(angle * (fraction - 0.5)) });
    const a = tangent(i / 4), b = tangent((i + 1) / 4);
    segments.push({ c1: world({ x: from.x + a.x, y: from.y + a.y }), c2: world({ x: to.x - b.x, y: to.y - b.y }), end: world(to) });
  }
  const xy = v => `${Number(v.x.toFixed(4))},${Number(v.y.toFixed(4))}`;
  return { start, segments, path: `M${xy(start)} ${segments.map(s => `C${xy(s.c1)} ${xy(s.c2)} ${xy(s.end)}`).join(' ')}` };
}

export function closingMotion(seconds) {
  const retract = ease((seconds - 5) / 0.7), morph = ease((seconds - 5.2) / 1.15);
  return { retract, morph, ...plateLine(morph), headRetraction: ease((seconds - 4.85) / 0.4),
    inner: ease((seconds - 6.05) / 0.6), leaf: ease((seconds - 6.25) / 0.6),
    wordmark: ease((seconds - 6.3) / 0.5), guide: ease((seconds - 6.45) / 0.5), lesson: ease((seconds - 6.6) / 0.5),
    stroke: lerp(2.5, 8, morph), color: `rgb(${[221, 195, 138].map((v, i) => Math.round(lerp(v, [191, 147, 65][i], morph))).join(',')})` };
}
