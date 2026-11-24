"""Sample the approved tutorial master into lossless, tightly cropped Slides build frames."""
import json
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZipInfo

from PIL import Image, ImageChops, ImageDraw, ImageFont

SCALE = 3
FPS = 30
CANVAS = (960 * SCALE, 540 * SCALE)
SOURCE = Path(__file__).resolve().parents[2] / 'src/services/templates'
# Coordinates of the logo pictures and visible wordmark ink in the approved assembly.
HERO = (424, 174, 112, 112)
CORNER = (48, 22.5, 36, 36)
HERO_TYPE = (407, 299, 145, 26.5)
CORNER_TYPE = (90, 31, 136, 26.5)


def smooth(u):
    u = min(1, max(0, u))
    return u * u * (3 - 2 * u)


def bounds(box):
    return tuple(round(SCALE * value) for value in box)


def draw_sprite(canvas, sprite, box):
    x, y, w, h = bounds(box)
    image = sprite.resize((w, h), Image.Resampling.LANCZOS)
    canvas.paste(image, (x, y), image.getchannel('A'))


def word_sprite(font, ink):
    glyphs = Image.new('L', (900, 140))
    ImageDraw.Draw(glyphs).text((8, 0), 'golden plate', fill=255, font=font)
    glyphs = glyphs.crop(glyphs.getbbox())
    sprite = Image.new('RGBA', glyphs.size, ink)
    sprite.putalpha(glyphs)
    return sprite


def archive_entry(archive, name, data):
    # Stable zip metadata keeps the generated bundle reproducible.
    archive.writestr(ZipInfo(name), data)


def store_frame(archive, frames, image, time_ms, paper):
    difference = ImageChops.difference(image, Image.new('RGB', image.size, paper)).convert('L')
    box = difference.point(lambda value: 255 if value > 5 else 0).getbbox()
    if box is None:
        return
    pixels = image.crop(box)
    encoded = BytesIO()
    pixels.save(encoded, format='PNG')
    file = f'{time_ms:04d}.png'
    archive_entry(archive, file, encoded.getvalue())
    frames.append(dict(file=file, ms=time_ms, x=box[0] / SCALE, y=box[1] / SCALE,
                       width=pixels.width / SCALE, height=pixels.height / SCALE))


def build(output, theme, georgia):
    paper = (16, 26, 22) if theme == 'dark' else (248, 247, 240)
    ink = '#edf0e6' if theme == 'dark' else '#183b2f'
    word = word_sprite(ImageFont.truetype(str(georgia), 108), ink)
    eot = (SOURCE / 'fonts/Newsreader-Regular.eot').read_bytes()
    ttf_size = int.from_bytes(eot[4:8], 'little')
    small_word = word_sprite(ImageFont.truetype(BytesIO(eot[-ttf_size:]), 108), ink)
    large_mark = Image.open(output / f'tutorial-plate-{theme}.png').convert('RGBA')
    small_mark = Image.open(SOURCE / 'plate-mark-768.png').convert('RGBA')

    # The source was authored on a flat background. Mapping the decoded video's
    # paper back to the slide paper avoids visible video-range seams around the ink.
    y, w, h = 510, 1620, 360
    filter = f'fps={FPS},scale={CANVAS[0]}:{CANVAS[1]}:flags=lanczos,crop={w}:{h}:0:{y},format=rgb24'
    process = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(output / f'tutorial-signature-{theme}.mp4'),
                                '-vf', filter, '-frames:v', '45', '-f', 'rawvideo', 'pipe:1'], stdout=subprocess.PIPE)
    frames = []
    with ZipFile(output / f'slides-signature-{theme}.zip', 'w') as archive:
        for index in range(45):
            raw = process.stdout.read(w * h * 3)
            if len(raw) != w * h * 3:
                raise RuntimeError(f'Tutorial signature ended before frame {index}')
            film = Image.frombytes('RGB', (w, h), raw)
            background = film.getpixel((w - 1, 0))
            table = [min(255, max(0, n + target - original))
                     for target, original in zip(paper, background) for n in range(256)]
            canvas = Image.new('RGB', CANVAS, paper)
            canvas.paste(film.point(table), (0, y))
            seconds = index / FPS
            if seconds > .95:
                offset = 37 * (1 - smooth((seconds - .95) / .5))
                type_layer = Image.new('RGB', CANVAS, paper)
                draw_sprite(type_layer, word, (HERO_TYPE[0], HERO_TYPE[1] + offset, *HERO_TYPE[2:]))
                clip = bounds((325, 294, 635, 331))
                canvas.paste(type_layer.crop(clip), clip[:2])
            store_frame(archive, frames, canvas, round(seconds * 1000), paper)
        process.stdout.close()
        if process.wait() != 0:
            raise RuntimeError('Could not decode the tutorial signature')
        for index in range(26):
            elapsed = index / FPS
            progress = smooth(elapsed / .85)
            mark_box = tuple(a + (b - a) * progress for a, b in zip(HERO, CORNER))
            word_box = tuple(a + (b - a) * progress for a, b in zip(HERO_TYPE, CORNER_TYPE))
            canvas = Image.new('RGB', CANVAS, paper)
            draw_sprite(canvas, large_mark, mark_box)
            draw_sprite(canvas, word, word_box)
            # The destination masthead uses a different mark crop and Newsreader.
            # Blend the two rendered lockups as native Morph changes their styling.
            if progress:
                destination = Image.new('RGB', CANVAS, paper)
                draw_sprite(destination, small_mark, mark_box)
                draw_sprite(destination, small_word, word_box)
                canvas = Image.blend(canvas, destination, progress)
            store_frame(archive, frames, canvas, 1500 + round(elapsed * 1000), paper)
        archive_entry(archive, 'frames.json', json.dumps(frames, separators=(',', ':')).encode())


if __name__ == '__main__':
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else SOURCE
    candidates = ['/System/Library/Fonts/Supplemental/Georgia.ttf',
                  '/usr/share/fonts/truetype/msttcorefonts/Georgia.ttf',
                  '/usr/share/fonts/truetype/msttcorefonts/georgia.ttf', 'C:/Windows/Fonts/georgia.ttf']
    georgia = Path(sys.argv[2]) if len(sys.argv) > 2 else next((Path(f) for f in candidates if Path(f).is_file()), None)
    if not georgia:
        raise SystemExit('Pass the path to Georgia.ttf as the second argument to rebuild the wordmark.')
    for theme in ('light', 'dark'):
        build(output, theme, georgia)
