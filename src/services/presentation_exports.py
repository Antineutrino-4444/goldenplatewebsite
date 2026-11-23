"""Generate an editable assembly presentation or matching PDF from one school snapshot."""
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import re
import unicodedata

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls
from pptx.util import Length, Pt
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from src.services.presentation_fonts import FONT_FILES, apply_presentation_fonts, font_ttf, supporting_pdf_font


WIDTH, HEIGHT = 960, 540
TEMPLATE_DIR = Path(__file__).with_name('templates')
TEMPLATE_FILES = {'light': 'school-assembly.pptx', 'dark': 'school-assembly-dark.pptx'}


@dataclass(frozen=True)
class Palette:
    paper: str
    ink: str
    muted: str
    line: str
    fill: str
    accent: str


@dataclass(frozen=True)
class Text:
    name: str
    lines: tuple
    x: float
    y: float
    width: float
    height: float
    size: float
    color: str
    face: str
    bold: bool
    italic: bool
    align: str
    anchor: str
    leading: float
    tracking: float
    effect: str = ''


@dataclass(frozen=True)
class Rect:
    name: str
    x: float
    y: float
    width: float
    height: float
    color: str
    effect: str = ''


@dataclass(frozen=True)
class Photo:
    name: str
    description: str
    data: bytes
    x: float
    y: float
    width: float
    height: float


def _clean_text(value):
    # School and session names come from school-owned records. They can include
    # newlines or XML-incompatible characters from older imports.
    return ' '.join(''.join(c for c in str(value) if c.isspace() or (
        unicodedata.category(c) not in ('Cc', 'Cs') and c not in '\ufffe\uffff')).split())


@lru_cache(maxsize=1)
def _pdf_cjk_font():
    font = UnicodeCIDFont('STSong-Light')
    pdfmetrics.registerFont(font)
    return font.fontName


@lru_cache(maxsize=1)
def _embedded_pdf_font(name):
    pdfmetrics.registerFont(TTFont(name, BytesIO(font_ttf(name))))
    return name


def _pdf_face(text, face, bold, italic=False):
    if any(unicodedata.east_asian_width(c) in ('W', 'F') for c in text):
        return _pdf_cjk_font()
    if face == 'Georgia':
        return supporting_pdf_font(bold, italic)
    styles = FONT_FILES[face]
    return _embedded_pdf_font(styles['bold'] if bold and 'bold' in styles else styles['regular'])


def _fit(text, width, size, face, bold, max_lines, italic=False, tracking=0):
    """Fit long school/session names to projection-size type. Keep full names in notes."""
    font = _pdf_face(text, face, bold, italic)
    available = width * .93  # Allow for font substitution when a school imports a slide.
    def measure(value):
        return pdfmetrics.stringWidth(value, font, size) + max(0, len(value) - 1) * tracking

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
    background: str
    title: str
    notes: str = ''
    items: list = field(default_factory=list)


def _template_item(shape):
    x, y, width, height = (v.pt for v in (shape.left, shape.top, shape.width, shape.height))
    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
        blob = shape.image.blob
        # An Office picture can store more pixels than its visible crop. Bake the
        # crop once so the PDF and both editable formats show the same framing.
        crop = (shape.crop_left, shape.crop_top, shape.crop_right, shape.crop_bottom)
        if any(crop):
            with Image.open(BytesIO(blob)) as image, BytesIO() as target:
                w, h = image.size
                box = (round(crop[0] * w), round(crop[1] * h),
                       round((1 - crop[2]) * w), round((1 - crop[3]) * h))
                if box != (0, 0, w, h):
                    image.crop(box).save(target, 'PNG')
                    blob = target.getvalue()
        props = shape._element.nvPicPr.cNvPr
        name = shape.name or 'Photograph'
        return Photo(name, props.get('descr') or name, blob, x, y, width, height)
    if not shape.text:
        return Rect(shape.name, x, y, width, height, str(shape.fill.fore_color.rgb))
    frame = shape.text_frame
    paragraph = frame.paragraphs[0]
    font = paragraph.runs[0].font
    tracking = int(font._rPr.get('spc', 0)) / 100
    spacing = paragraph.line_spacing
    leading = spacing.pt / font.size.pt if isinstance(spacing, Length) else (spacing or 1.22)
    align = {PP_ALIGN.RIGHT: 'right', PP_ALIGN.CENTER: 'center'}.get(paragraph.alignment, 'left')
    anchor = {MSO_ANCHOR.MIDDLE: 'middle', MSO_ANCHOR.BOTTOM: 'bottom'}.get(frame.vertical_anchor, 'top')
    return Text(shape.name, tuple(shape.text.splitlines()), x + frame.margin_left.pt, y + frame.margin_top.pt,
                width - frame.margin_left.pt - frame.margin_right.pt,
                height - frame.margin_top.pt - frame.margin_bottom.pt, font.size.pt, str(font.color.rgb),
                font.name, bool(font.bold), bool(font.italic), align, anchor, leading, tracking)


@lru_cache(maxsize=2)
def _template_pages(theme):
    deck = Presentation(TEMPLATE_DIR / TEMPLATE_FILES[theme])
    titles = ('School Results', 'Latest Lunch', 'Lunch to Lunch', 'Clean-Plate Rates', 'Quick Reminders',
              'Be Green, Do Good')
    pages = []
    for page, fallback in zip(deck.slides, titles, strict=True):
        items = [_template_item(shape) for shape in page.shapes]
        heading = next((' '.join(item.lines) for item in items if isinstance(item, Text)
                        and item.name.lower() in ('title', 'slide title', 'slide_title')), fallback)
        pages.append(Slide(str(page.background.fill.fore_color.rgb), page._element.cSld.get('name') or heading,
                           page.notes_slide.notes_text_frame.text, items))
    return tuple(pages)


class _TemplatePalettes(Mapping):
    """Expose the existing theme lookup using the corresponding authored colors."""

    def __iter__(self):
        return iter(TEMPLATE_FILES)

    def __len__(self):
        return len(TEMPLATE_FILES)

    def __getitem__(self, theme):
        cover, breakdown = _template_pages(theme)[:2]
        cover_colors = {item.name: item.color for item in cover.items if isinstance(item, (Text, Rect))}
        fill = next(item.color for item in breakdown.items if item.name == 'Student clean plates key')
        return Palette(cover.background, cover_colors['all_clean'], cover_colors['share'],
                       cover_colors['Masthead rule'], fill, cover_colors['latest_change'])


PALETTES = _TemplatePalettes()


def _date(value):
    if not value:
        return 'Date unavailable'
    stamp = date.fromisoformat(value)
    return f'{stamp:%b} {stamp.day}, {stamp.year}'


def _stamp(value):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
    return f'{stamp:%b} {stamp.day}, {stamp.year} at {stamp:%H:%M} UTC'


def _pct(value):
    if value is None:
        return '—'
    return f'{value:,.1f}'.removesuffix('.0') + '%'


def _signed(value, digits=0):
    value = round(value, digits)
    sign = '+' if value > 0 else '−' if value < 0 else ''
    return sign + f'{abs(value):,.{digits}f}'.removesuffix('.0')


CATEGORIES = (
    ('student_clean', 'Student clean plates'), ('faculty_clean', 'Faculty clean plates'),
    ('dirty', 'Dirty plates'), ('very_dirty', 'Very dirty plates'),
)


def _goal_label(clean, milestone):
    if not milestone:
        return 'Share of plates returned clean'
    if clean > milestone:
        return f'{clean - milestone:,} above the {milestone:,}-plate goal'
    if clean == milestone:
        return f'{milestone:,}-plate goal reached'
    return f'{milestone - clean:,} to the {milestone:,}-plate goal'


def _clean_plate_count(session, *, recorded=False):
    total = session['total']
    subject = 'plate was' if total == 1 else 'plates were'
    if recorded:
        subject = 'recorded ' + subject
    return f"{session['clean']:,} of {total:,} {subject} clean"


def _clean_rate(session):
    if not session or not session['total']:
        return None
    rate = session.get('clean_percentage')
    if isinstance(rate, (int, float)) and 0 <= rate <= 100:
        return round(rate, 1)
    # Older snapshots may have counts without a usable percentage.
    clean, total = session['clean'], session['total']
    return round(100 * clean / total, 1) if 0 <= clean <= total else None


def _rate_difference(data):
    previous, latest = _clean_rate(data['previous']), _clean_rate(data['latest'])
    return round(latest - previous, 1) if previous is not None and latest is not None else None


def _overview_values(data):
    totals, latest = data['totals'], data['latest']
    clean, total, lunches = totals['clean'], totals['total'], totals['session_count']
    milestone = data.get('milestone')
    share = (f"{_pct(_clean_rate(totals))} of {total:,} recorded {'plate' if total == 1 else 'plates'} "
             f"across {lunches:,} {'lunch' if lunches == 1 else 'lunches'}")
    values = {
        'all_clean': f"{clean:,} clean {'plate' if clean == 1 else 'plates'}",
        'share': share if total else 'No plates recorded yet',
        'goal_label': _goal_label(clean, milestone) if total or milestone else '',
        'latest_heading': 'Latest lunch', 'rate_heading': '', 'change_heading': '',
        'latest_name': 'No lunch results yet', 'latest_date': '', 'latest_counts': '',
        'latest_rate': '', 'latest_change': '', 'change_units': '',
    }
    if latest:
        values.update(
            latest_name=latest['name'], latest_date=_date(latest['date']),
            latest_counts=_clean_plate_count(latest),
            rate_heading='Clean-plate rate', latest_rate=_pct(_clean_rate(latest)),
            change_heading='' if data['previous'] else 'First recorded lunch',
        )
        delta = _rate_difference(data)
        if delta is not None:
            values.update(change_heading='Change from previous lunch', latest_change=_signed(delta, 1),
                          change_units='percentage point' if abs(delta) == 1 else 'percentage points')
    return values


def _latest_values(latest):
    return {
        'latest_name': latest['name'], 'latest_date': _date(latest['date']),
        'rate': _pct(_clean_rate(latest)),
        'latest_counts': _clean_plate_count(latest),
        **{key: f'{latest[key]:,}' for key, _ in CATEGORIES},
    }


def _comparison_values(data):
    values = {}
    for prefix, session in (('prev', data['previous']), ('curr', data['latest'])):
        values.update({
            prefix + '_name': session['name'], prefix + '_date': _date(session['date']),
            prefix + '_clean': f"{session['clean']:,}", prefix + '_total': f"{session['total']:,}",
            prefix + '_rate': _pct(_clean_rate(session)), prefix + '_counts': _clean_plate_count(session),
        })
    previous, latest = data['previous'], data['latest']
    delta = _rate_difference(data)
    comparison = 'Rate comparison unavailable'
    if delta == 0:
        comparison = 'No change in clean-plate rate'
    elif delta is not None:
        points = 'percentage point' if abs(delta) == 1 else 'percentage points'
        direction = 'higher' if delta > 0 else 'lower'
        comparison = f"{abs(delta):g} {points} {direction}"
    values.update(delta_clean=_signed(latest['clean'] - previous['clean']),
                  delta_total=_signed(latest['total'] - previous['total']),
                  delta_rate='—' if delta is None else _signed(delta, 1) + '%',
                  rate_comparison=comparison)
    return values


def _progress_bar(track, data, palette):
    clean, total = data['totals']['clean'], data['totals']['total']
    goal = data.get('milestone')
    scale = max(goal, clean) if goal else total
    if not scale:
        return
    yield track
    if clean:
        share = min(goal, clean) if goal else clean
        width = track.width * share / scale
        yield replace(track, name='Clean plates toward milestone' if goal else 'All-time clean plate share',
                      width=width, color=palette.fill, effect='wipe')
        if goal and clean > goal:
            yield replace(track, name='Clean plates above milestone', x=track.x + width,
                          width=track.width - width, color=palette.accent, effect='wipe')


def _distribution_bar(track, latest, layout):
    yield track
    swatches = {item.name: item.color for item in layout if isinstance(item, Rect)}
    offset = 0
    for key, label in CATEGORIES:
        count = latest[key]
        if count:
            x = track.x + track.width * offset / latest['total']
            offset += count
            end = track.x + track.width * offset / latest['total']
            yield replace(track, name=label + ' share', x=x, width=end - x,
                          color=swatches[label + ' key'], effect='wipe')


def _fit_frame(item, lines, *, allow_ellipsis):
    # A slightly longer lunch name can still fit in full at presentation size.
    # Retain the full spelling in notes if an unusually long name needs ellipsis.
    size = item.size
    minimum = min(size, max(12, size * .8) if allow_ellipsis else 12)
    while True:
        tracking = item.tracking * size / item.size
        capacity = max(1, int((item.height / size + item.leading - 1) / item.leading + 1e-5))
        if item.name == 'all_clean' or (len(lines) == 1 and re.fullmatch(r'[+−-]?[\d,.]+(?:%| pts)?', lines[0])):
            capacity = 1
        fitted = []
        for index, line in enumerate(lines):
            budget = max(1, capacity - len(fitted) - (len(lines) - 1 - index))
            fitted.extend(_fit(line, item.width, size, item.face, item.bold, budget, item.italic, tracking))
        if not any(line.endswith('…') for line in fitted) or size <= minimum:
            return replace(item, lines=tuple(fitted), size=size, tracking=tracking)
        size = max(minimum, size - 1)


def _fit_school_label(item, text, masthead_bottom):
    # The masthead has room above and below its one-line sample. Wrap within
    # that space before reducing the type so the full registered name is visible.
    center = item.y + item.height / 2
    height_available = 2 * min(center, masthead_bottom - center - 3)
    size = item.size
    while True:
        line_height = size * item.leading
        capacity = max(1, int(height_available / line_height))
        lines = _fit(text, item.width, size, item.face, item.bold, capacity + 1, item.italic)
        if len(lines) <= capacity:
            height = len(lines) * line_height
            return replace(item, lines=tuple(lines), size=size, y=center - height / 2, height=height)
        if size <= 1:
            # Preserve even a malformed legacy record longer than the header
            # can display at the minimum font size supported by PowerPoint.
            return replace(item, lines=(text,), size=size)
        size = max(1, size - 1)


def _bind_page(index, data, theme, values, notes):
    template = _template_pages(theme)[index]
    values.update(school=data.get('school_label') or data['school_name'],
                  stamp='Records as of ' + _stamp(data['generated_at']))
    title = _clean_text(values['latest_name']) if index == 1 else template.title
    page = Slide(template.background, title, '\n'.join((template.notes, data['school_name'], notes)).strip())
    for item in template.items:
        if isinstance(item, Text):
            if item.name not in values:
                page.items.append(item)
                continue
            text = _clean_text(values[item.name] or '')
            if not text:
                continue
            # The browser has already measured and wrapped the template copy.
            # Refit only when a school's value differs from the authored text.
            if item.name == 'school':
                rule = next(part for part in template.items if part.name == 'Masthead rule')
                page.items.append(_fit_school_label(item, text, rule.y))
                continue
            school_owned_name = item.name in ('prev_name', 'curr_name') or (
                item.name == 'latest_name' and data['latest'] is not None)
            fitted = item if text == ' '.join(item.lines) else _fit_frame(
                item, (text,), allow_ellipsis=school_owned_name)
            effect = 'fade' if item.name.startswith('delta_') or item.name == 'latest_change' else ''
            page.items.append(replace(fitted, effect=effect))
        elif item.name == 'progress_track':
            page.items.extend(_progress_bar(item, data, PALETTES[theme]))
        elif item.name == 'distribution':
            page.items.extend(_distribution_bar(item, data['latest'], template.items))
        elif item.name in ('prev_fill', 'curr_fill'):
            prefix = item.name.split('_')[0]
            track = next(part for part in template.items if part.name == prefix + '_track')
            rate = _clean_rate(data['previous'] if prefix == 'prev' else data['latest'])
            if rate is not None:
                page.items.append(replace(item, x=track.x, width=track.width * rate / 100))
        else:
            page.items.append(item)
    return page


def _session_note(session):
    return f"{session['name']}, {_date(session['date'])}. {_clean_plate_count(session, recorded=True)}."


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
        slide.background.fill.fore_color.rgb = RGBColor.from_string(page.background)
        effects = []
        for item in page.items:
            if isinstance(item, Text):
                shape = slide.shapes.add_textbox(Pt(item.x), Pt(item.y), Pt(item.width), Pt(item.height))
                frame = shape.text_frame
                frame.word_wrap = False
                frame.auto_size = MSO_AUTO_SIZE.NONE
                frame.vertical_anchor = {'top': MSO_ANCHOR.TOP, 'middle': MSO_ANCHOR.MIDDLE,
                                         'bottom': MSO_ANCHOR.BOTTOM}[item.anchor]
                frame.margin_top = frame.margin_right = frame.margin_bottom = frame.margin_left = 0
                for index, line in enumerate(item.lines):
                    paragraph = frame.add_paragraph() if index else frame.paragraphs[0]
                    paragraph.alignment = {'left': PP_ALIGN.LEFT, 'right': PP_ALIGN.RIGHT,
                                           'center': PP_ALIGN.CENTER}[item.align]
                    paragraph.space_after = paragraph.space_before = Pt(0)
                    # CSS leading is relative to the font size, whereas Office
                    # percentage spacing multiplies the font's intrinsic line box.
                    paragraph.line_spacing = Pt(item.size * item.leading)
                    run = paragraph.add_run()
                    run.text = line
                    run.font.name, run.font.size = item.face, Pt(item.size)
                    run.font.bold, run.font.italic = item.bold, item.italic
                    run.font.color.rgb = RGBColor.from_string(item.color)
                    if item.tracking:
                        run.font._rPr.set('spc', str(round(item.tracking * 100)))
            elif isinstance(item, Rect):
                shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Pt(item.x), Pt(item.y),
                                               Pt(item.width), Pt(item.height))
                shape.fill.solid()
                shape.fill.fore_color.rgb = RGBColor.from_string(item.color)
                shape.line.fill.background()
                shape.shadow.inherit = False
                # LibreOffice also applies the shape style's default shadow
                # unless its theme-effect reference is explicitly disabled.
                shape._element.xpath('p:style/a:effectRef')[0].set('idx', '0')
            else:
                shape = slide.shapes.add_picture(BytesIO(item.data), Pt(item.x), Pt(item.y),
                                                 Pt(item.width), Pt(item.height))
                shape._element.nvPicPr.cNvPr.set('descr', item.description)
            shape.name = item.name
            if getattr(item, 'effect', ''):
                effects.append((shape.shape_id, item.effect))
        slide.notes_slide.notes_text_frame.text = '\n'.join(_clean_text(line) for line in page.notes.splitlines())
        if animated:
            _animate(slide, effects)
    apply_presentation_fonts(presentation)
    with BytesIO() as file:
        presentation.save(file)
        return file.getvalue()


def _pdf(pages):
    with BytesIO() as file:
        pdf = canvas.Canvas(file, pagesize=(WIDTH, HEIGHT), initialFontName=supporting_pdf_font(False, False))
        pdf.setTitle(pages[0].title)
        pdf.setAuthor('Golden Plate')
        for page in pages:
            pdf.setFillColor(HexColor('#' + page.background))
            pdf.rect(0, 0, WIDTH, HEIGHT, stroke=0, fill=1)
            for item in page.items:
                if isinstance(item, Photo):
                    pdf.drawImage(ImageReader(BytesIO(item.data)), item.x, HEIGHT - item.y - item.height,
                                  item.width, item.height, mask='auto')
                elif isinstance(item, Rect):
                    pdf.setFillColor(HexColor('#' + item.color))
                    pdf.rect(item.x, HEIGHT - item.y - item.height, item.width, item.height, stroke=0, fill=1)
                else:
                    pdf.setFillColor(HexColor('#' + item.color))
                    pdf.setFont(_pdf_face(' '.join(item.lines), item.face, item.bold, item.italic), item.size)
                    draw, x = {'left': (pdf.drawString, item.x),
                               'right': (pdf.drawRightString, item.x + item.width),
                               'center': (pdf.drawCentredString, item.x + item.width / 2)}[item.align]
                    line_height = item.size * item.leading
                    free_height = max(0, item.height - len(item.lines) * line_height)
                    top = item.y + {'top': 0, 'middle': free_height / 2, 'bottom': free_height}[item.anchor]
                    # Match the baseline of the editable text box at this fixed
                    # leading, including the descender space below its first line.
                    first_baseline = HEIGHT - top - line_height + .2 * item.size
                    for index, line in enumerate(item.lines):
                        draw(x, first_baseline - line_height * index, line, charSpace=item.tracking)
            pdf.showPage()
        pdf.save()
        return file.getvalue()


def generate_deck(kind, theme, snapshot, platform='powerpoint'):
    """Return a point-in-time assembly/overview as PPTX, Slides-importable PPTX, or PDF.

    Only the requesting school's authorized aggregate snapshot is passed in.
    The resulting file can be presented and copied offline.
    """
    if kind not in ('assembly', 'overview') or theme not in TEMPLATE_FILES or platform not in ('powerpoint', 'google-slides', 'pdf'):
        raise ValueError('Unknown presentation format')
    latest, previous = snapshot['latest'], snapshot['previous']
    milestone = snapshot.get('milestone')
    overview = _overview_values(snapshot)
    overview_note = f"{overview['all_clean']}. {overview['share']}."
    if milestone:
        overview_note += f" {overview['goal_label']}."
    if latest:
        overview_note += (f" The latest lunch was {latest['name']} ({overview['latest_date']}). "
                          f"{overview['latest_counts']}. The clean-plate rate was {overview['latest_rate']}.")
    if overview['latest_change']:
        overview_note += f" The rate changed by {overview['latest_change']} {overview['change_units']}."
    pages = [_bind_page(0, snapshot, theme, overview, overview_note)]
    if kind == 'assembly':
        if latest:
            pages.append(_bind_page(1, snapshot, theme, _latest_values(latest), _session_note(latest)))
            if previous:
                notes = 'Previous lunch: ' + _session_note(previous) + ' Latest lunch: ' + _session_note(latest)
                comparison = _comparison_values(snapshot)
                notes += (f" Clean-plate rates: {comparison['prev_rate']} previously and {comparison['curr_rate']} "
                          f"at the latest lunch. {comparison['rate_comparison']}.")
                pages.append(_bind_page(2, snapshot, theme, comparison, notes))
                pages.append(_bind_page(3, snapshot, theme, comparison, notes))
        pages.append(_bind_page(4, snapshot, theme, {}, ''))
        pages.append(_bind_page(5, snapshot, theme, {}, ''))
    if platform == 'pdf':
        return _pdf(pages)
    return _powerpoint(pages, animated=platform == 'powerpoint')
