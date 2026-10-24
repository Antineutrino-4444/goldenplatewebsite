import test from 'node:test';
import assert from 'node:assert/strict';
import recipe from '../recipes/registration.mjs';
import { ease, roundedPath, timeline, durationOf, sceneSnapshot, cursorAt, fitCamera, project, checkLayout } from '../engine/timeline.mjs';
import { plateLine, closingMotion } from '../engine/closing.mjs';

test('registration ends its walkthrough on Login, then closes with a next-video card', () => {
  const scenes = timeline(recipe);
  assert.equal(durationOf(recipe), 74.5);
  const lastInteraction = scenes.findLast(s => s.actions?.length);
  assert.equal(lastInteraction.id, 'login');
  assert.equal(lastInteraction.actions.at(-1).target, 'login');
  assert.equal(scenes.at(-1).kind, 'closing');
  assert.equal(scenes.at(-1).at, 65);
  assert.match(scenes.at(-1).title, /school account/);
  assert(scenes.some(s => s.id === 'approval' && /Wait for PLATE approval/.test(s.caption)));
  assert(!scenes.some(s => /portal|orientation|account-email/.test(s.id)));
  assert.equal(scenes.slice(0, -1).reduce((n, s) => n + s.duration, 0), scenes.at(-1).at);
});
test('closing line curls continuously into the plate and holds a stable signature', () => {
  for (const p of [0, 0.2, 0.5, 0.8, 1]) {
    const shape = plateLine(p);
    for (let i = 0; i < 3; i++) {
      const a = shape.segments[i], b = shape.segments[i + 1];
      assert(Math.abs((a.end.x - a.c2.x) - (b.c1.x - a.end.x)) < 1e-9);
      assert(Math.abs((a.end.y - a.c2.y) - (b.c1.y - a.end.y)) < 1e-9);
    }
  }
  for (let step = 0; step <= 100; step++) for (const segment of plateLine(step / 100).segments) {
    assert(Math.hypot(segment.end.x - segment.c2.x, segment.end.y - segment.c2.y) > 40, 'A zero-length tangent would create a cusp during the curl.');
  }
  const circle = plateLine(1);
  assert(Math.hypot(circle.start.x - circle.segments.at(-1).end.x, circle.start.y - circle.segments.at(-1).end.y) < 1e-9);
  assert.deepEqual(closingMotion(7.2), closingMotion(9.49));
  assert.equal(closingMotion(9).leaf, 1);
});
test('typing is repeatable at arbitrary frame order and cannot expose a real recording', () => {
  const scene = recipe.scenes.find(s => s.id === 'email');
  assert.equal(sceneSnapshot(scene, 0).state.schoolEmail, '');
  assert.equal(sceneSnapshot(scene, 4.2).state.schoolEmail, 'school@example.org');
  const halfway = sceneSnapshot(scene, 2.4);
  sceneSnapshot(scene, 7.5);
  assert.deepEqual(sceneSnapshot(scene, 2.4), halfway);
  assert.equal(sceneSnapshot(scene, 6.2).state.verificationLoading, true);
});
test('cursor reaches the element before the scheduled click with zero endpoint velocity', () => {
  const scene = { actions: [{ type: 'click', target: 'send', at: 2, travel: 1 }] };
  const bounds = { send: { x: 100, y: 200, width: 100, height: 40 } };
  const end = cursorAt(scene, 2, bounds, { x: 0, y: 0 });
  assert.equal(end.x, 150); assert.equal(end.y, 220);
  const last = cursorAt(scene, 1.999, bounds, { x: 0, y: 0 });
  assert(Math.hypot(last.x - end.x, last.y - end.y) < 0.001);
  assert.equal(ease(0), 0); assert.equal(ease(1), 1);
});
test('border geometry uses true circular CSS arcs, including asymmetric clipped tabs', () => {
  const r = { x: 20, y: 30, width: 200, height: 40, radii: [8, 0, 0, 8] };
  const path = roundedPath(r, 1);
  assert(path.includes('A7,7')); assert(!path.includes('Q')); assert(path.includes('L219,31'));
  assert.equal(path, roundedPath(r, 1));
});
test('layout rejects adjacent expanded outlines and clipped targets', () => {
  const panel = { x: 560, y: 144, width: 1296, height: 816 }, card = { x: 64, y: 425, width: 432, height: 262 };
  const a = { x: 700, y: 400, width: 300, height: 60 }, b = { x: 1008, y: 400, width: 100, height: 60 };
  assert.deepEqual(checkLayout({ a, b }, panel, card), []);
  assert(checkLayout({ a, b: { ...b, x: 999 } }, panel, card).some(s => /collide/.test(s)));
  assert(checkLayout({ a: { ...a, x: 550 } }, panel, card).some(s => /clipped/.test(s)));
});
test('camera fits a changed control layout and projects all four corner radii', () => {
  const panel = { x: 560, y: 144, width: 1296, height: 816 };
  const r = { x: 500, y: 1000, width: 620, height: 72, radii: [8, 8, 8, 8] };
  const camera = fitCamera([r], panel, { minWidth: 860, padding: 80 });
  const projected = project(r, camera, panel);
  assert(projected.x > panel.x && projected.y > panel.y);
  assert(projected.x + projected.width < panel.x + panel.width);
  assert.equal(projected.radii[0], 8 * camera.scale);
});
