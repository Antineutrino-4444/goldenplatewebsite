"""Generate an editable assembly presentation or matching PDF from one school snapshot."""
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import unicodedata

from PIL import Image, ImageOps
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls
from pptx.util import Pt
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas


WIDTH, HEIGHT = 960, 540
LEFT, RIGHT = 48, 912


@dataclass(frozen=True)
class Palette:
    paper: str
    ink: str
    muted: str
    line: str
    fill: str
    accent: str


PALETTES = {
    'light': Palette('F8F7F0', '183B2F', '495B50', 'CBD3C7', '3E7154', '80632B'),
    'dark': Palette('101A16', 'EDF0E6', 'B6C4B9', '3C5042', 'A9C7A8', 'DDC38A'),
}


@dataclass
class Text:
    name: str
    lines: list
    x: float
    y: float
    width: float
    size: float
    color: str
    face: str
    bold: bool
    align: str
    effect: str = ''


@dataclass
class Rect:
    name: str
    x: float
    y: float
    width: float
    height: float
    color: str
    effect: str = ''


@dataclass
class Photo:
    name: str
    data: bytes
    x: float
    y: float
    width: float
    height: float


def _clean_text(value):
    # School and session names come from school-owned records. They can include
    # newlines or XML-incompatible characters from older imports.
    return ' '.join(''.join(c if c.isspace() or unicodedata.category(c) not in ('Cc', 'Cs') else ''
                            for c in str(value)).split())


@lru_cache(maxsize=1)
def _pdf_cjk_font():
    font = UnicodeCIDFont('STSong-Light')
    pdfmetrics.registerFont(font)
    return font.fontName


def _pdf_face(text, face, bold):
    if any(unicodedata.east_asian_width(c) in ('W', 'F') for c in text):
        return _pdf_cjk_font()
    if face == 'Georgia':
        return 'Times-Bold' if bold else 'Times-Roman'
    return 'Helvetica-Bold' if bold else 'Helvetica'


def _fit(text, width, size, face, bold, max_lines):
    """Fit long school/session names to projection-size type. Keep full names in notes."""
    font = _pdf_face(text, face, bold)
    available = width * .93  # Allow for font substitution when a school imports a slide.
    def measure(value):
        return pdfmetrics.stringWidth(value, font, size)

    lines = []
    remaining = text
    while remaining and len(lines) < max_lines:
        if measure(remaining) <= available:
            lines.append(remaining)
            break
        last = len(lines) == max_lines - 1
        suffix = '…' if last else ''
        low, high = 0, len(remaining)
        while low < high:
            middle = (low + high + 1) // 2
            if measure(remaining[:middle] + suffix) <= available:
                low = middle
            else:
                high = middle - 1
        cut = max(1, low)
        if not last and ' ' in remaining[:cut]:
            cut = remaining.rfind(' ', 0, cut + 1)
        lines.append(remaining[:cut].rstrip() + suffix)
        if last:
            break
        remaining = remaining[cut:].lstrip()
    return lines or ['']


@dataclass
class Slide:
    palette: Palette
    title: str
    notes: str = ''
    items: list = field(default_factory=list)

    def text(self, value, x, y, width, size, *, color=None, face='Arial', bold=False,
             align='left', max_lines=1, name=None, effect=''):
        text = _clean_text(value)
        self.items.append(Text(name or text[:65], _fit(text, width, size, face, bold, max_lines),
                               x, y, width, size, color or self.palette.ink, face, bold, align, effect))

    def rect(self, name, x, y, width, height, color, effect=''):
        self.items.append(Rect(name, x, y, width, height, color, effect))

    def bar(self, name, count, total, x, y, width, height):
        self.rect(name + ' track', x, y, width, height, self.palette.line)
        if total and count:
            self.rect(name, x, y, width * min(1, count / total), height, self.palette.fill, 'wipe')


def _date(value):
    if not value:
        return 'Date unavailable'
    stamp = date.fromisoformat(value)
    return f'{stamp:%b} {stamp.day}, {stamp.year}'


def _stamp(value):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
    return f'{stamp:%b} {stamp.day}, {stamp.year} at {stamp:%H:%M} UTC'


def _pct(value):
    return f'{value:,.1f}'.removesuffix('.0') + '%'


def _signed(value, digits=0):
    value = round(value, digits)
    sign = '+' if value > 0 else '−' if value < 0 else ''
    return sign + f'{abs(value):,.{digits}f}'.removesuffix('.0')


def _page(data, theme, title):
    page = Slide(theme, title)
    page.text(data['school_name'], LEFT, 30, RIGHT - LEFT, 16, color=theme.accent, bold=True)
    page.text(title, LEFT, 60, RIGHT - LEFT, 42, face='Georgia')
    page.rect('Header rule', LEFT, 132, RIGHT - LEFT, 1, theme.line)
    page.rect('Footer rule', LEFT, 486, RIGHT - LEFT, 1, theme.line)
    page.text('Golden Plate', LEFT, 499, 180, 11, color=theme.muted, bold=True)
    page.text('Records as of ' + _stamp(data['generated_at']), 255, 499, RIGHT - 255, 11,
              color=theme.muted, align='right')
    return page


def _overview(data, theme):
    page = _page(data, theme, 'School Results')
    totals, latest, change = data['totals'], data['latest'], data['change']
    page.text('All-Time Clean Plates', LEFT, 164, 422, 20, bold=True)
    page.text(f"{totals['clean']:,}", LEFT, 202, 420, 66, face='Georgia')
    milestone = data.get('milestone')
    clean = totals['clean']
    if milestone:
        scale = max(milestone, clean)
        page.bar('Clean plates toward milestone', min(clean, milestone), scale, LEFT, 301, 398, 15)
        if clean > milestone:
            goal_width = 398 * milestone / scale
            page.rect('Clean plates above milestone', LEFT + goal_width, 301, 398 - goal_width, 15,
                      theme.accent, effect='wipe')
            goal_label = f"{clean - milestone:,} above the {milestone:,}-plate goal"
        elif clean == milestone:
            goal_label = f"{milestone:,}-plate goal reached"
        else:
            goal_label = f"{milestone - clean:,} to the {milestone:,}-plate goal"
        page.text(goal_label, LEFT, 332, 416, 18, max_lines=2)
    else:
        page.bar('All-time clean plate share', clean, totals['total'], LEFT, 301, 398, 15)
    if totals['total']:
        clean_share = f"{_pct(totals['clean_percentage'])} of {totals['total']:,} recorded plates"
    else:
        clean_share = 'No plates recorded yet'
    page.text(clean_share, LEFT, 386 if milestone else 334, 416, 18, max_lines=2)
    count = totals['session_count']
    page.text(f"{count:,} recorded lunch {'session' if count == 1 else 'sessions'}",
              LEFT, 448 if milestone else 404, 411, 16, color=theme.muted)
    page.rect('Column divider', 483, 163, 1, 282, theme.line)
    x, width = 522, 390
    page.text('Latest Lunch', x, 164, width, 20, bold=True)
    if latest:
        page.text(latest['name'], x, 206, width, 26, face='Georgia', max_lines=2)
        page.text(_date(latest['date']), x, 284, width, 15, color=theme.muted)
        page.text(f"{latest['clean']:,} of {latest['total']:,} plates were clean", x, 319, width, 19,
                  max_lines=2)
        page.text(f"Clean-plate rate: {_pct(latest['clean_percentage'])}", x, 375, width, 18)
        if change:
            page.text(f"{_signed(change['clean_percentage_points'], 1)} percentage points from the previous lunch",
                      x, 410, width, 16, max_lines=2, color=theme.accent, effect='fade')
        else:
            page.text('First recorded lunch', x, 410, width, 16, color=theme.muted)
    else:
        page.text('The first lunch result will appear after plates are recorded.',
                  x, 213, width, 24, face='Georgia', max_lines=3)
    progress = (f"The progress bar compares all-time clean plates with the school's {milestone:,}-plate goal."
                if milestone else "The progress bar shows the share of all recorded plates that were clean.")
    page.notes = (f"{data['school_name']}. {progress} The totals include student and faculty clean plates. "
                  "Empty and discarded sessions are excluded.")
    if latest:
        page.notes += f" Latest session: {latest['name']}, {_date(latest['date'])}."
    return page


def _latest(data, theme):
    latest = data['latest']
    page = _page(data, theme, 'Latest Lunch')
    page.text(latest['name'], LEFT, 160, 412, 24, face='Georgia', max_lines=2)
    page.text(_date(latest['date']), LEFT, 231, 402, 15, color=theme.muted)
    page.text(_pct(latest['clean_percentage']), LEFT, 269, 402, 65, face='Georgia')
    page.text('of recorded plates were clean', LEFT, 361, 402, 18)
    page.text(f"{latest['total']:,} plates recorded", LEFT, 407, 402, 17, color=theme.muted)
    categories = [('Student clean plates', 'student_clean'), ('Faculty clean plates', 'faculty_clean'),
                  ('Dirty plates', 'dirty'), ('Very dirty plates', 'very_dirty')]
    for index, (label, key) in enumerate(categories):
        y = 166 + index * 73
        page.text(label, 503, y, 280, 19)
        page.text(f'{latest[key]:,}', 767, y, 145, 20, bold=True, align='right')
        page.bar(label + ' share', latest[key], latest['total'], 503, y + 37, 409, 8)
    page.notes = (f"{latest['name']} on {_date(latest['date'])}. Each bar represents its share "
                  "of the session's total. The clean rate combines clean student and faculty plates.")
    return page


def _comparison(data, theme):
    old, new, change = data['previous'], data['latest'], data['change']
    page = _page(data, theme, 'Change Since the Previous Lunch')
    page.text('Previous', 300, 152, 218, 17, color=theme.muted, bold=True)
    page.text('Latest', 528, 152, 218, 17, color=theme.muted, bold=True)
    page.text('Change', 764, 152, 148, 17, color=theme.muted, bold=True, align='right')
    for x, session in ((300, old), (528, new)):
        page.text(session['name'], x, 183, 210, 16, max_lines=2)
        page.text(_date(session['date']), x, 233, 205, 13, color=theme.muted)
    rows = [
        ('Clean plates', f"{old['clean']:,}", f"{new['clean']:,}", _signed(change['clean'])),
        ('Plates recorded', f"{old['total']:,}", f"{new['total']:,}", _signed(change['total'])),
        ('Clean-plate rate', _pct(old['clean_percentage']), _pct(new['clean_percentage']),
         _signed(change['clean_percentage_points'], 1) + ' pts'),
    ]
    for index, (label, before, after, delta) in enumerate(rows):
        y = 266 + index * 52
        page.rect(label + ' rule', LEFT, y, RIGHT - LEFT, 1, theme.line)
        page.text(label, LEFT, y + 12, 245, 19)
        page.text(before, 300, y + 10, 215, 22)
        page.text(after, 528, y + 10, 215, 22)
        page.text(delta, 744, y + 10, 168, 22, color=theme.accent, bold=True, align='right', effect='fade')
    page.text('Rate change is shown in percentage points.', LEFT, 444, RIGHT - LEFT, 14, color=theme.muted)
    page.notes = (f"Previous: {old['name']} on {_date(old['date'])}. Latest: {new['name']} on "
                  f"{_date(new['date'])}. Compare the clean-plate rates when attendance differs.")
    return page


@lru_cache(maxsize=1)
def _coaches_image():
    base = Path(__file__).resolve().parents[2]
    for directory in ('src/static', 'frontend/public'):
        photo = base / directory / 'images/initiative/compost-coaches.webp'
        if photo.is_file():
            with Image.open(photo) as source, BytesIO() as file:
                ImageOps.fit(source.convert('RGB'), (880, 548), centering=(.55, .35)).save(file, 'JPEG', quality=87)
                return file.getvalue()
    return None


def _next_lunch(data, theme):
    page = _page(data, theme, 'At the Next Lunch')
    photo = _coaches_image()
    width = 375 if photo else 735
    page.text('Choose a portion that fits your appetite.', LEFT, 174, width, 31,
              face='Georgia', max_lines=3)
    page.text('At the dish return, give the student team a moment to count your plate.',
              LEFT, 322, width, 21, max_lines=4)
    if photo:
        page.items.append(Photo("Student Compost Coaches at St. Andrew’s College", photo, 466, 156, 446, 278))
        page.text('Compost Coaches at St. Andrew’s College, Aurora.', 466, 444, 446, 13, color=theme.muted)
    page.notes = ("Invite students to suggest one change that would help them leave less food on their plates. "
                  "Add your next lunch date or draw announcement here before presenting.")
    return page


def _animate(slide, effects):
    # python-pptx has no animation API. Keep motion in the standard presentation
    # timing tree. All objects in a data series reveal together on one click.
    slide._element.append(parse_xml(f'<p:transition {nsdecls("p")} spd="med"><p:fade/></p:transition>'))
    if not effects:
        return
    from lxml import etree
    from pptx.oxml.ns import qn

    def node(parent, tag, **attributes):
        return etree.SubElement(parent, qn('p:' + tag), attributes)

    timing = node(slide._element, 'timing')
    root = node(node(node(timing, 'tnLst'), 'par'), 'cTn', id='1', dur='indefinite',
                restart='never', nodeType='tmRoot')
    sequence = node(node(root, 'childTnLst'), 'seq', concurrent='1', nextAc='seek')
    main = node(sequence, 'cTn', id='2', dur='indefinite', nodeType='mainSeq')
    click = node(node(node(main, 'childTnLst'), 'par'), 'cTn', id='3', fill='hold')
    node(node(click, 'stCondLst'), 'cond', delay='indefinite')
    group = node(node(node(click, 'childTnLst'), 'par'), 'cTn', id='4', fill='hold')
    node(node(group, 'stCondLst'), 'cond', delay='0')
    items = node(group, 'childTnLst')
    for i, (identifier, effect) in enumerate(effects):
        key = 5 + 3 * i
        entry = node(node(items, 'par'), 'cTn', id=str(key), presetClass='entr',
                     presetID='22' if effect == 'wipe' else '10', fill='hold',
                     nodeType='clickEffect' if i == 0 else 'withEffect')
        node(node(entry, 'stCondLst'), 'cond', delay='0')
        actions = node(entry, 'childTnLst')
        visibility = node(actions, 'set')
        behavior = node(visibility, 'cBhvr')
        time = node(behavior, 'cTn', id=str(key + 1), dur='1', fill='hold')
        node(node(time, 'stCondLst'), 'cond', delay='0')
        node(node(behavior, 'tgtEl'), 'spTgt', spid=str(identifier))
        node(node(behavior, 'attrNameLst'), 'attrName').text = 'style.visibility'
        node(node(visibility, 'to'), 'strVal', val='visible')
        animation = node(actions, 'animEffect', transition='in', filter='wipe(right)' if effect == 'wipe' else 'fade')
        behavior = node(animation, 'cBhvr')
        node(behavior, 'cTn', id=str(key + 2), dur='450')
        node(node(behavior, 'tgtEl'), 'spTgt', spid=str(identifier))
    for name, event in [('prevCondLst', 'onPrev'), ('nextCondLst', 'onNext')]:
        condition = node(node(sequence, name), 'cond', evt=event, delay='0')
        node(node(condition, 'tgtEl'), 'sldTgt')


def _powerpoint(pages, *, animated):
    presentation = Presentation()
    presentation.slide_width, presentation.slide_height = Pt(WIDTH), Pt(HEIGHT)
    presentation.core_properties.title = pages[0].title
    presentation.core_properties.author = 'Golden Plate'
    presentation.core_properties.comments = ''
    for page in pages:
        slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        slide._element.cSld.set('name', page.title)
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = RGBColor.from_string(page.palette.paper)
        effects = []
        for item in page.items:
            if isinstance(item, Text):
                line_height = item.size * 1.22
                shape = slide.shapes.add_textbox(Pt(item.x), Pt(item.y), Pt(item.width),
                                                 Pt(line_height * len(item.lines) + 3))
                frame = shape.text_frame
                frame.word_wrap = False
                frame.auto_size = MSO_AUTO_SIZE.NONE
                frame.vertical_anchor = MSO_ANCHOR.TOP
                frame.margin_top = frame.margin_right = frame.margin_bottom = frame.margin_left = 0
                for index, line in enumerate(item.lines):
                    paragraph = frame.add_paragraph() if index else frame.paragraphs[0]
                    paragraph.alignment = PP_ALIGN.RIGHT if item.align == 'right' else PP_ALIGN.LEFT
                    paragraph.space_after = paragraph.space_before = Pt(0)
                    paragraph.line_spacing = Pt(line_height)
                    run = paragraph.add_run()
                    run.text = line
                    run.font.name, run.font.size, run.font.bold = item.face, Pt(item.size), item.bold
                    run.font.color.rgb = RGBColor.from_string(item.color)
            elif isinstance(item, Rect):
                shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Pt(item.x), Pt(item.y),
                                               Pt(item.width), Pt(item.height))
                shape.fill.solid()
                shape.fill.fore_color.rgb = RGBColor.from_string(item.color)
                shape.line.fill.background()
            else:
                shape = slide.shapes.add_picture(BytesIO(item.data), Pt(item.x), Pt(item.y),
                                                 Pt(item.width), Pt(item.height))
            shape.name = item.name
            if getattr(item, 'effect', ''):
                effects.append((shape.shape_id, item.effect))
        slide.notes_slide.notes_text_frame.text = _clean_text(page.notes)
        if animated:
            _animate(slide, effects)
    with BytesIO() as file:
        presentation.save(file)
        return file.getvalue()


def _pdf(pages):
    with BytesIO() as file:
        pdf = canvas.Canvas(file, pagesize=(WIDTH, HEIGHT))
        pdf.setTitle(pages[0].title)
        pdf.setAuthor('Golden Plate')
        for page in pages:
            pdf.setFillColor(HexColor('#' + page.palette.paper))
            pdf.rect(0, 0, WIDTH, HEIGHT, stroke=0, fill=1)
            for item in page.items:
                if isinstance(item, Photo):
                    pdf.drawImage(ImageReader(BytesIO(item.data)), item.x, HEIGHT - item.y - item.height,
                                  item.width, item.height)
                elif isinstance(item, Rect):
                    pdf.setFillColor(HexColor('#' + item.color))
                    pdf.rect(item.x, HEIGHT - item.y - item.height, item.width, item.height, stroke=0, fill=1)
                else:
                    pdf.setFillColor(HexColor('#' + item.color))
                    pdf.setFont(_pdf_face(' '.join(item.lines), item.face, item.bold), item.size)
                    draw = pdf.drawRightString if item.align == 'right' else pdf.drawString
                    x = item.x + item.width if item.align == 'right' else item.x
                    for index, line in enumerate(item.lines):
                        draw(x, HEIGHT - item.y - item.size * (1 + 1.22 * index), line)
            pdf.showPage()
        pdf.save()
        return file.getvalue()


def generate_deck(kind, theme, snapshot, platform='powerpoint'):
    """Return a point-in-time assembly/overview as PPTX, Slides-importable PPTX, or PDF.

    Only the requesting school's authorized aggregate snapshot is passed in.
    The resulting file can be presented and copied offline.
    """
    if kind not in ('assembly', 'overview') or theme not in PALETTES or platform not in ('powerpoint', 'google-slides', 'pdf'):
        raise ValueError('Unknown presentation format')
    palette = PALETTES[theme]
    pages = [_overview(snapshot, palette)]
    if kind == 'assembly':
        if snapshot['latest']:
            pages.append(_latest(snapshot, palette))
            if snapshot['previous']:
                pages.append(_comparison(snapshot, palette))
        pages.append(_next_lunch(snapshot, palette))
    if platform == 'pdf':
        return _pdf(pages)
    return _powerpoint(pages, animated=platform == 'powerpoint')
