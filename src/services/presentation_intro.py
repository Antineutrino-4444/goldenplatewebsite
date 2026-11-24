"""The tutorial signature used to introduce and close the PowerPoint assembly."""
from dataclasses import dataclass, replace
from functools import lru_cache
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image
from pptx.util import Pt


INTRO_MARKER = 'gp.intro'
INTRO_TEMPLATE_INDEX = 7
OUTRO_MARKER = 'gp.outro'
OUTRO_TEMPLATE_INDEX = 8
SIGNATURE_LAYOUTS = {INTRO_TEMPLATE_INDEX, OUTRO_TEMPLATE_INDEX}
SIGNATURE_FILM = 'gp.signature.film'
SIGNATURE_FRAME_PREFIX = 'gp.signature.frame.'
SIGNATURE_FRAME_COVER = 'gp.signature.frame-cover'
GOOGLE_HANDOFF_MS = 2350
GOOGLE_OUTRO_SETTLE_MS = 1500
MORPH_MARK = '!!Golden Plate mark'
MORPH_WORDMARK = '!!Golden Plate wordmark'
MORPH_NAMES = {MORPH_MARK, MORPH_WORDMARK}
_ARTWORK = Path(__file__).with_name('templates')


@lru_cache(maxsize=2)
def _google_frames(theme):
    with ZipFile(_ARTWORK / f'slides-signature-{theme}.zip') as archive:
        return [(row, archive.read(row['file'])) for row in json.loads(archive.read('frames.json'))]


def _google_signature_layers(theme, image, rule, background, *, moving):
    frames = [
        replace(image, name=f'{SIGNATURE_FRAME_PREFIX}{row["ms"]:04d}', description='[gp-motion-only]',
                x=row['x'], y=row['y'], width=row['width'], height=row['height'], data=blob)
        for row, blob in _google_frames(theme) if moving or row['ms'] < GOOGLE_OUTRO_SETTLE_MS
    ]
    # In the editor or a printout the live, editable slide sits on this paper.
    # Disappear removes it on entry to expose the timed pictures underneath.
    paper = replace(rule, name=SIGNATURE_FRAME_COVER, x=0, y=0, width=960, height=540, color=background)
    return [*frames, paper]


def google_outro(intro, overview, theme):
    picture = intro.items[0]
    rule = next(item for item in overview.items if item.name == 'Masthead rule')
    layers = _google_signature_layers(theme, picture, rule, overview.background, moving=False)
    return replace(intro, template_index=OUTRO_TEMPLATE_INDEX, title=OUTRO_MARKER, items=layers + intro.items)


@dataclass(frozen=True)
class SignatureFilm:
    file: Path
    paper: str
    name: str = SIGNATURE_FILM

    def add_to(self, slide):
        poster = BytesIO()
        Image.new('RGB', (16, 9), '#' + self.paper).save(poster, 'PNG')
        poster.seek(0)
        movie = slide.shapes.add_movie(str(self.file), 0, 0, Pt(960), Pt(540),
                                       poster_frame_image=poster, mime_type='video/mp4')
        # python-pptx installs a minimal, click-only timing tree when adding
        # media. The assembly builds a single timing tree after all shapes exist.
        slide._element.remove(slide._element.xpath('p:timing')[0])
        for link in movie._element.xpath('p:nvPicPr/p:cNvPr/a:hlinkClick'):
            link.getparent().remove(link)
        movie._element.nvPicPr.cNvPr.set('descr', 'Golden Plate tutorial signature')
        return movie


def opening_pair(overview, school_name, theme, *, google=False):
    """Use native picture/text at the end of the film for continuous object Morph."""
    masthead = {item.name: item for item in overview.items}
    # A high-resolution transparent crop of the original plate/leaf vector
    # from the website's school-overview PDF, with the masthead's framing.
    artwork = _ARTWORK / 'plate-mark-768.png'
    mark = replace(masthead['Plate mark'], name=MORPH_MARK, data=artwork.read_bytes())
    word = replace(masthead['Publisher'], name=MORPH_WORDMARK)
    replacements = {'Plate mark': mark, 'Publisher': word}
    results = replace(overview, items=[replacements.get(item.name, item) for item in overview.items])

    # The tutorial was authored at 1920×1080. Half its pixel coordinates give
    # the matching positions on the 960×540 pt assembly canvas.
    film = SignatureFilm(_ARTWORK / f'tutorial-signature-{theme}.mp4', overview.background)
    large_mark = replace(mark, x=424, y=174, width=112, height=112,
                         data=(_ARTWORK / f'tutorial-plate-{theme}.png').read_bytes())
    large_word = replace(word, x=325, y=294, width=310, height=37, size=27, face='Georgia',
                         align='center', tracking=0, leading=35 / 27)
    if google:
        items = [replace(large_mark, name=SIGNATURE_FILM, description='Golden Plate'), large_word]
        layers = _google_signature_layers(theme, mark, masthead['Masthead rule'], overview.background, moving=True)
        results = replace(results, items=layers + results.items)
    else:
        items = [film, large_mark, large_word]
    intro = replace(overview, template_index=INTRO_TEMPLATE_INDEX, title=INTRO_MARKER,
                    notes=school_name, items=items)
    return intro, results
