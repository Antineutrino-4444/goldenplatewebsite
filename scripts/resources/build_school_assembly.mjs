// Run from the repository root: node scripts/resources/build_school_assembly.mjs [light.pptx] [preview-folder].
// Authoring dependencies (local installation or NODE_PATH): @oai/artifact-tool, playwright, sharp, jszip.
// Install Playwright's Chromium, or set CHROMIUM_PATH to an installed Chromium executable.
import fs from 'node:fs/promises';
import { createRequire } from 'node:module';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const sharp = require('sharp');
const JSZip = require('jszip');
const { Presentation, PresentationFile } = await import(pathToFileURL(require.resolve('@oai/artifact-tool')));
const root = process.cwd();
const frontend = path.join(root, 'frontend');
const fontDir = path.join(root, 'src/services/templates/fonts');
const entry = '/print/school-assembly/index.html';
const origin = 'https://assembly.invalid';
const light = path.resolve(process.argv[2] || 'src/services/templates/school-assembly.pptx');
const dark = path.join(path.dirname(light), path.parse(light).name + '-dark.pptx');
const previews = process.argv[3] && path.resolve(process.argv[3]);
const dimensions = { width: 1280, height: 720 };
const noLine = { style: 'solid', fill: 'none', width: 0 };
const mimeTypes = { '.html': 'text/html', '.css': 'text/css', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.png': 'image/png', '.ttf': 'font/ttf' };

function localAsset(url) {
  const { origin: host, pathname } = new URL(url);
  if (host !== origin) throw new Error(`Unexpected assembly resource ${url}`);
  if (pathname.startsWith('/print/school-assembly/') || pathname.startsWith('/src/')) return path.join(frontend, pathname);
  if (pathname.startsWith('/resources/') || pathname.startsWith('/images/')) return path.join(frontend, 'public', pathname);
  throw new Error(`Unknown assembly resource ${pathname}`);
}

async function serveAsset(route) {
  const file = localAsset(route.request().url());
  let body;
  if (['Gelasio-Regular.ttf', 'Gelasio-Bold.ttf', 'Gelasio-Italic.ttf'].includes(path.basename(file))) {
    body = await fs.readFile(path.join(fontDir, path.basename(file)));
  } else if (path.extname(file) === '.ttf') {
    // EOT FontDataSize identifies the original uncompressed TTF at the end of the font part.
    const container = await fs.readFile(path.join(fontDir, path.basename(file, '.ttf') + '.eot'));
    body = container.subarray(-container.readUInt32LE(4));
  } else {
    body = await fs.readFile(file);
  }
  await route.fulfill({ contentType: mimeTypes[path.extname(file)], body });
}

// This function runs in Chromium. All coordinates and font measurements are CSS pixels.
function measureSlide(section) {
  const canvas = section.getBoundingClientRect();
  const slots = [];
  const names = new Set();
  function color(value) {
    const rgb = value.match(/^rgb\((\d+), (\d+), (\d+)\)$/);
    if (!rgb) throw new Error(`Expected an opaque RGB color, got ${value}`);
    return '#' + rgb.slice(1).map(v => Number(v).toString(16).padStart(2, '0')).join('');
  }
  for (const el of section.querySelectorAll('[data-ppt]')) {
    if (el.closest('[data-preview]')) continue;
    const name = el.dataset.ppt;
    if (!name || names.has(name)) throw new Error(`Missing or duplicate native shape name: ${name}`);
    names.add(name);
    const r = el.getBoundingClientRect();
    const position = { left: r.left - canvas.left, top: r.top - canvas.top, width: r.width, height: r.height };
    if (!r.width || !r.height || position.left < -0.5 || position.top < -0.5 || r.right > canvas.right + 0.5 || r.bottom > canvas.bottom + 0.5) {
      throw new Error(`${name} has an empty frame or extends past the slide: ${JSON.stringify(position)}`);
    }
    const style = getComputedStyle(el);
    if (el instanceof HTMLImageElement) {
      slots.push({ name, position, kind: 'image', url: el.currentSrc, alt: el.alt, fit: style.objectFit });
    } else if (el.hasAttribute('data-rect')) {
      const radius = parseFloat(style.borderTopLeftRadius);
      slots.push({ name, position, kind: 'rect', fill: color(style.backgroundColor), ...(radius ? { radius } : {}) });
    } else {
      const fontSize = parseFloat(style.fontSize);
      // Measure natural browser line breaks while keeping all lines in one editable text box.
      const lines = [];
      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      const range = document.createRange();
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        for (const word of node.textContent.matchAll(/\S+/gu)) {
          range.setStart(node, word.index);
          range.setEnd(node, word.index + word[0].length);
          const box = range.getBoundingClientRect();
          if (!box.width) continue;
          if (box.left < r.left - 2 || box.right > r.right + 2 || box.bottom > r.bottom + fontSize * 0.25) {
            throw new Error(`${name} has text outside its HTML frame: ${word[0]}`);
          }
          if (!lines.length || Math.abs(box.top - lines.at(-1).top) > 1) lines.push({ top: box.top, words: [] });
          lines.at(-1).words.push(word[0]);
        }
      }
      let text = lines.map(line => line.words.join(' ')).join('\n');
      if (style.textTransform === 'uppercase') text = text.toUpperCase();
      if (!text) throw new Error(`Empty native text frame: ${name}`);
      slots.push({ name, position, kind: 'text', text, color: color(style.color),
        typeface: style.fontFamily.split(',')[0].trim().replace(/^["']|["']$/g, ''), fontSize,
        bold: Number(style.fontWeight) >= 600, italic: style.fontStyle === 'italic',
        align: { start: 'left', end: 'right' }[style.textAlign] || style.textAlign,
        letterSpacing: parseFloat(style.letterSpacing) || 0, lineHeight: parseFloat(style.lineHeight) || fontSize * 1.2 });
    }
  }
  return { width: canvas.width, height: canvas.height, background: color(getComputedStyle(section).backgroundColor),
    notes: section.querySelector('[data-notes]')?.textContent.trim() || '', slots };
}

async function addImage(slide, slot) {
  const source = sharp(localAsset(slot.url));
  const { width, height, hasAlpha } = await source.metadata();
  const position = { ...slot.position };
  const widthScale = position.width / width, heightScale = position.height / height;
  if (slot.fit === 'contain' && Math.abs(widthScale - heightScale) > 0.001) {
    // The unused portion of an object-fit:contain frame is transparent in the HTML.
    const scale = Math.min(widthScale, heightScale);
    position.left += (position.width - width * scale) / 2;
    position.top += (position.height - height * scale) / 2;
    position.width = width * scale;
    position.height = height * scale;
  }
  const image = hasAlpha ? await source.png().toBuffer() : await source.jpeg({ quality: 90 }).toBuffer();
  const picture = slide.images.add({ name: slot.name, blob: image, contentType: hasAlpha ? 'image/png' : 'image/jpeg',
    alt: slot.alt, fit: slot.fit === 'cover' ? 'cover' : 'contain', position });
  picture.name = slot.name;
}

async function build(pages, file, browserPage) {
  const deck = Presentation.create({ slideSize: dimensions });
  deck.theme.defaultFont = 'Georgia';
  for (const page of pages) {
    if (page.width !== dimensions.width || page.height !== dimensions.height) throw new Error(`Expected 1280 × 720 HTML slide, got ${page.width} × ${page.height}`);
    const slide = deck.slides.add();
    slide.background.fill = page.background;
    for (const slot of page.slots) {
      if (slot.kind === 'image') {
        await addImage(slide, slot);
      } else if (slot.kind === 'rect') {
        slide.shapes.add({ name: slot.name, position: slot.position, geometry: slot.radius ? 'roundRect' : 'rect',
          ...(slot.radius ? { borderRadius: slot.radius } : {}), fill: slot.fill, line: noLine });
      } else {
        const text = slide.shapes.add({ name: slot.name, position: slot.position, geometry: 'textbox', fill: 'none', line: noLine });
        // CSS line height is absolute here. A percentage in PowerPoint instead
        // multiplies the typeface's own leading and moves the first baseline.
        text.text = slot.text.split('\n').map(line => ({ runs: [line],
          paragraphStyle: { lineSpacingPoints: Math.round(slot.lineHeight * 75) } }));
        text.text.style = { typeface: slot.typeface, color: slot.color, fontSize: slot.fontSize,
          bold: slot.bold, italic: slot.italic, alignment: slot.align, characterSpacing: Math.round(slot.letterSpacing * 75),
          verticalAlignment: 'top', insets: 0, wrap: 'none', autoFit: 'none' };
      }
    }
    slide.speakerNotes.text = page.notes;
  }
  await (await PresentationFile.exportPptx(deck)).save(file);
  // The presentation exporter keeps the native picture names but currently
  // omits their alt text. Copy each HTML alt to its Office accessibility field.
  const archive = await JSZip.loadAsync(await fs.readFile(file));
  for (const [index, page] of pages.entries()) {
    const part = `ppt/slides/slide${index + 1}.xml`;
    const descriptions = Object.fromEntries(page.slots.filter(slot => slot.kind === 'image').map(slot => [slot.name, slot.alt]));
    const xml = await archive.file(part).async('string');
    const updated = await browserPage.evaluate(({ xml, descriptions }) => {
      const doc = new DOMParser().parseFromString(xml, 'application/xml');
      for (const picture of doc.getElementsByTagNameNS('*', 'pic')) {
        const properties = picture.getElementsByTagNameNS('*', 'cNvPr')[0];
        properties.setAttribute('descr', descriptions[properties.getAttribute('name')]);
      }
      return new XMLSerializer().serializeToString(doc);
    }, { xml, descriptions });
    archive.file(part, updated);
  }
  await fs.writeFile(file, await archive.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' }));
}

const work = await fs.mkdtemp(path.join(os.tmpdir(), 'school-assembly-'));
try {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  try {
    const page = await browser.newPage({ viewport: dimensions, deviceScaleFactor: 1 });
    const assetErrors = [];
    await page.route('**/*', async route => {
      try { await serveAsset(route); }
      catch (error) { assetErrors.push(error.message); await route.abort(); }
    });
    await page.goto(origin + entry);
    await page.evaluate(async () => {
      await Promise.all([...document.images].map(img => img.decode()));
      await document.fonts.ready;
    });
    if (assetErrors.length) throw new Error(assetErrors.join('\n'));
    if (previews) await fs.mkdir(previews, { recursive: true });
    const slides = await page.locator('.slide').all();
    if (slides.length !== 6) throw new Error(`Expected 6 school assembly slides, got ${slides.length}`);
    for (const theme of ['light', 'dark']) {
      await page.evaluate(mode => document.documentElement.classList.toggle('dark', mode === 'dark'), theme);
      const pages = [];
      for (const [index, slide] of slides.entries()) {
        pages.push(await slide.evaluate(measureSlide));
        if (previews) await slide.screenshot({ path: path.join(previews, `${theme}-${index + 1}.png`), animations: 'disabled' });
      }
      if (previews) await fs.writeFile(path.join(previews, `${theme}.json`), JSON.stringify(pages, null, 2));
      await build(pages, path.join(work, theme + '.pptx'), page);
    }
  } finally {
    await browser.close();
  }
  await fs.mkdir(path.dirname(light), { recursive: true });
  await fs.copyFile(path.join(work, 'light.pptx'), light);
  await fs.copyFile(path.join(work, 'dark.pptx'), dark);
} finally {
  await fs.rm(work, { recursive: true, force: true });
}
