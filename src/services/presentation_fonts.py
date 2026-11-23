"""Fonts shared by the editable assembly deck and its printable PDF."""
from functools import lru_cache
from pathlib import Path
from struct import unpack_from

from lxml import etree
from pptx.opc.constants import CONTENT_TYPE as CT, RELATIONSHIP_TYPE as RT
from pptx.opc.package import Part, XmlPart
from pptx.opc.packuri import PackURI
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn
from reportlab import rl_config
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont, TTFError


_FONTS = Path(__file__).with_name('templates') / 'fonts'
FONT_FILES = {
    'Newsreader': {'regular': 'Newsreader-Regular'},
}
_GEORGIA_FILES = {
    'Regular': ('Georgia', ('Georgia.ttf', 'georgia.ttf')),
    'Bold': ('Georgia-Bold', ('Georgia Bold.ttf', 'Georgia_Bold.ttf', 'georgiab.ttf')),
    'Italic': ('Georgia-Italic', ('Georgia Italic.ttf', 'Georgia_Italic.ttf', 'georgiai.ttf')),
}


@lru_cache(maxsize=1)
def _eot(name):
    return (_FONTS / (name + '.eot')).read_bytes()


def font_ttf(name):
    # These uncompressed EOT files end in the complete static TrueType face.
    # FontDataSize is the second uint32 in the EOT header.
    eot = _eot(name)
    size, = unpack_from('<I', eot, 4)
    return eot[-size:]


def _georgia_directories():
    return (
        *map(Path, rl_config.TTFSearchPath),
        Path('/System/Library/Fonts/Supplemental'),
        Path('/Library/Fonts/Microsoft'),
        Path('/Applications/Microsoft PowerPoint.app/Contents/Resources/DFonts'),
        Path('/usr/share/fonts/truetype/msttcorefonts'),
    )


@lru_cache(maxsize=3)
def supporting_pdf_font(bold=False, italic=False):
    """Use local Georgia when available, or the bundled metric-compatible Gelasio."""
    style = 'Italic' if italic else 'Bold' if bold else 'Regular'
    native_name, filenames = _GEORGIA_FILES[style]
    for directory in _georgia_directories():
        for filename in filenames:
            path = directory / filename
            if not path.is_file():
                continue
            try:
                font = TTFont(native_name, str(path))
            except (OSError, TTFError):
                continue
            if font.face.name == native_name.encode():
                pdfmetrics.registerFont(font)
                return font.fontName
    fallback = 'Gelasio-' + style
    font = TTFont(fallback, str(_FONTS / (fallback + '.ttf')))
    pdfmetrics.registerFont(font)
    return font.fontName


def apply_presentation_fonts(deck):
    package = deck.part.package
    for part in package.iter_parts():
        if part.content_type == CT.OFC_THEME:
            # The notes master creates its theme as a live XmlPart. The
            # bundled slide master initially loads its theme as a binary Part.
            theme = part._element if isinstance(part, XmlPart) else parse_xml(part.blob)
            theme.find('.//' + qn('a:majorFont') + '/' + qn('a:latin')).set('typeface', 'Newsreader')
            theme.find('.//' + qn('a:minorFont') + '/' + qn('a:latin')).set('typeface', 'Georgia')
            if not isinstance(part, XmlPart):
                part._blob = etree.tostring(theme, encoding='UTF-8', xml_declaration=True, standalone=True)

    # PowerPoint embeds Newsreader as EOT and resolves Georgia by name.
    fonts = parse_xml(f'<p:embeddedFontLst {nsdecls("p", "r")}/>')
    for family, styles in FONT_FILES.items():
        face = etree.SubElement(fonts, qn('p:embeddedFont'))
        etree.SubElement(face, qn('p:font'), typeface=family)
        for style, name in styles.items():
            uri = PackURI(f'/ppt/fonts/{name}.fntdata')
            font = Part(uri, CT.X_FONTDATA, package, _eot(name))
            entry = etree.SubElement(face, qn('p:' + style))
            entry.set(qn('r:id'), deck.part.relate_to(font, RT.FONT))
    deck._element.insert_element_before(fonts, 'p:custShowLst', 'p:photoAlbum', 'p:custDataLst',
                                        'p:kiosk', 'p:defaultTextStyle', 'p:modifyVerifier', 'p:extLst')
    deck._element.set('embedTrueTypeFonts', '1')
    deck._element.set('saveSubsetFonts', '0')
