"""The tutorial signature used to introduce and close the PowerPoint assembly."""
from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path

from PIL import Image
from pptx.util import Pt


INTRO_MARKER = 'gp.intro'
INTRO_TEMPLATE_INDEX = 7
OUTRO_MARKER = 'gp.outro'
OUTRO_TEMPLATE_INDEX = 8
SIGNATURE_LAYOUTS = {INTRO_TEMPLATE_INDEX, OUTRO_TEMPLATE_INDEX}
SIGNATURE_FILM = 'gp.signature.film'
MORPH_MARK = '!!Golden Plate mark'
MORPH_WORDMARK = '!!Golden Plate wordmark'
MORPH_NAMES = {MORPH_MARK, MORPH_WORDMARK}
_ARTWORK = Path(__file__).with_name('templates')


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


def opening_pair(overview, school_name, theme):
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
    intro = replace(overview, template_index=INTRO_TEMPLATE_INDEX, title=INTRO_MARKER,
                    notes=school_name, items=[film, large_mark, large_word])
    return intro, results
