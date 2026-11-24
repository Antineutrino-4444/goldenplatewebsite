"""Generate an editable assembly presentation or matching PDF from one school snapshot."""
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from io import BytesIO
from math import cos, pi, sqrt
from pathlib import Path
import re
import unicodedata
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Length, Pt
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from src.services.presentation_fonts import FONT_FILES, apply_presentation_fonts, font_ttf, supporting_pdf_font
from src.services.presentation_intro import (
    INTRO_TEMPLATE_INDEX, OUTRO_MARKER, OUTRO_TEMPLATE_INDEX, SignatureFilm, opening_pair,
)
from src.services.presentation_motion import DISTRIBUTION_WINDOW_NAME, PROGRESS_WINDOW_NAME, RATE_WINDOW_NAMES, add_slide_motion
from src.services.presentation_winner import WINNER_MARKER, WINNER_TEMPLATE_INDEX, add_winner_slide


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
    radius: float = 0
    # A segment of one continuous rounded meter, identified by (offset, full width).
    meter_slice: tuple[float, float] | None = None


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
    template_index: int
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
        radius = min(width, height) * shape.adjustments[0] if shape.auto_shape_type == MSO_SHAPE.ROUNDED_RECTANGLE else 0
        return Rect(shape.name, x, y, width, height, str(shape.fill.fore_color.rgb), radius=radius)
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
    titles = ('School Results', 'Latest session', 'Session comparison', 'Clean-Plate Rates', 'Quick Reminders',
              'Be Green, Do Good')
    pages = []
    for index, (page, fallback) in enumerate(zip(deck.slides, titles, strict=True)):
        items = [_template_item(shape) for shape in page.shapes]
        heading = next((' '.join(item.lines) for item in items if isinstance(item, Text)
                        and item.name.lower() in ('title', 'slide title', 'slide_title')), fallback)
        pages.append(Slide(index, str(page.background.fill.fore_color.rgb), page._element.cSld.get('name') or heading,
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


def _stamp(value, zone_name):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    try:
        zone = ZoneInfo(zone_name)
    except (TypeError, ValueError, ZoneInfoNotFoundError):
        zone = ZoneInfo('America/New_York')
    local = stamp.astimezone(zone)
    return f'Records as of {local:%b} {local.day}, {local.year} at {local:%H:%M %Z}'


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
    clean, total, sessions = totals['clean'], totals['total'], totals['session_count']
    milestone = data.get('milestone')
    share = (f"{_pct(_clean_rate(totals))} of {total:,} recorded {'plate' if total == 1 else 'plates'} "
             f"across {sessions:,} {'session' if sessions == 1 else 'sessions'}")
    values = {
        'all_clean': f"{clean:,} clean {'plate' if clean == 1 else 'plates'}",
        'share': share if total else 'No plates recorded yet',
        'goal_label': _goal_label(clean, milestone) if total or milestone else '',
        'latest_heading': 'Latest session', 'rate_heading': '', 'change_heading': '',
        'latest_name': 'No session results yet', 'latest_date': '', 'latest_counts': '',
        'latest_rate': '', 'latest_change': '', 'change_units': '',
    }
    if latest:
        values.update(
            latest_name=latest['name'], latest_date=_date(latest['date']),
            latest_counts=_clean_plate_count(latest),
            rate_heading='Clean-plate rate', latest_rate=_pct(_clean_rate(latest)),
            change_heading='' if data['previous'] else 'First recorded session',
        )
        delta = _rate_difference(data)
        if delta is not None:
            values.update(change_heading='Change from previous session', latest_change=_signed(delta, 1),
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
    if clean <= 0:
        return
    share = min(goal, clean) if goal else clean
    # Snap the shared boundary once to Office's native coordinate unit. A
    # mathematically positive fraction can be smaller than a drawable shape.
    full_width = round(track.width * Pt(1))
    boundary = min(full_width, round(full_width * share / scale))
    width = boundary / Pt(1)
    above_goal = goal and clean > goal and boundary < full_width
    if boundary:
        # Split a completed meter at a straight color boundary. Tiny fills also
        # need the physical left corner of the track to constrain their ink.
        crop = (0, track.width) if above_goal or width < 2 * track.radius else None
        yield replace(track, name='Clean plates toward milestone' if goal else 'All-time clean plate share',
                      width=width, color=palette.fill, effect='fly', meter_slice=crop)
    if above_goal:
        yield replace(track, name='Clean plates above milestone', x=track.x + width,
                      width=track.width - width, color=palette.accent, effect='excess' if boundary else 'fly',
                      meter_slice=(width, track.width) if boundary else None)


def _meter_outline(track, offset=0, end=None):
    """Trace a full rounded window or its exact horizontal interval in slide points."""
    end = track.width if end is None else end
    radius = track.radius
    xs = {offset, end}
    # Twelve segments per quarter circle keep chord error below .01 pt at the
    # authored radius. Both renderers use the same outline at a color boundary.
    for step in range(13):
        x = radius * (1 - cos(step * pi / 24))
        xs.update(value for value in (x, track.width - x) if offset < value < end)
    top = []
    for x in sorted(xs):
        distance = max(0, radius - x, x - (track.width - radius))
        y = radius - sqrt(max(0, radius ** 2 - distance ** 2))
        top.append((track.x + x, track.y + y))
    return top + [(x, 2 * track.y + track.height - y) for x, y in reversed(top)]


def _meter_segment_outline(item):
    offset, full_width = item.meter_slice
    track = replace(item, x=item.x - offset, width=full_width)
    return _meter_outline(track, offset, offset + item.width)


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
                          color=swatches[label + ' key'])


def _fit_frame(item, lines, *, allow_ellipsis):
    # A slightly longer session name can still fit in full at presentation size.
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
                  stamp=data['records_stamp'])
    title = _clean_text(values['latest_name']) if index == 1 else template.title
    page = Slide(index, template.background, title, '\n'.join((template.notes, data['school_name'], notes)).strip())
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
            if item.name == 'latest_change' and text.startswith(('+', '−', '-')):
                fitted = replace(fitted, effect='signed_change')
            page.items.append(fitted)
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


def _latest_session_page(snapshot, theme, platform):
    latest = snapshot['latest']
    page = _bind_page(1, snapshot, theme, _latest_values(latest), _session_note(latest))
    if platform == 'powerpoint' and latest['total'] > 0:
        zero_counts = set()
        for key, label in CATEGORIES:
            if key in ('dirty', 'very_dirty') and latest[key] == 0:
                zero_counts.update((key, label + ' label'))
        gold = next(item.color for item in _template_pages(theme)[-1].items if item.name == 'Be Green')
        page.items = [replace(item, color=gold) if item.name in zero_counts else item for item in page.items]
    return page


def _winner_detail_lines(role, details, width):
    def number(key):
        try:
            value = Decimal(str(details.get(key)))
        except InvalidOperation:
            return None
        return value if value.is_finite() and value >= 0 else None

    def fits(words):
        return pdfmetrics.stringWidth(words, _pdf_face(words, 'Georgia', False), 14) <= width * .93

    def ticket_count(value):
        quantity = format(abs(value) if value == 0 else value, ',f')
        if '.' in quantity:
            quantity = quantity.rstrip('0').rstrip('.')
        return f"{quantity} {'ticket' if value == 1 else 'tickets'}"

    tickets, probability, pool = (number(key) for key in ('tickets', 'probability', 'pool_size'))
    next_gain = number('next_ticket_gain')
    method = details.get('method')
    lines = [ticket_count(tickets) + ' at draw'] if tickets is not None else []
    remaining_odds = None
    if probability is not None and probability <= 100:
        qualifier = 'pool share' if method == 'manual' else 'chance'
        odds = f'{probability:.2f}% {qualifier}'
        if not lines:
            lines.append(odds)
        elif fits(lines[0] + ' · ' + odds):
            lines[0] += ' · ' + odds
        else:
            remaining_odds = odds
    if next_gain is not None:
        lines.append('Next clean plate: +' + ticket_count(next_gain))
    if remaining_odds:
        lines.append(remaining_odds)
    selection = {'manual': 'Manual selection', 'random': 'Random draw'}.get(method)
    context = []
    if pool is not None and pool == pool.to_integral_value():
        group = ('student' if pool == 1 else 'students') if role == 'student' else (
            'faculty member' if pool == 1 else 'faculty')
        context.append(f'{pool:,.0f} eligible {group}')
    if selection:
        context.append(selection)
    if context:
        lines.append(' · '.join(context))

    school = []
    for key in ('grade', 'house', 'clan'):
        raw = details.get(key)
        if not isinstance(raw, (str, int)) or isinstance(raw, bool):
            continue
        value = _clean_text(raw)
        if not value:
            continue
        if key not in value.casefold().split():
            value = 'Grade ' + value if key == 'grade' else value + ' ' + key.title()
        if fits(' · '.join([*school, value])):
            school.append(value)
    if school:
        lines.append(' · '.join(school))
    return lines


def _winner_page(overview, snapshot, theme):
    source = {item.name: item for item in overview.items}
    masthead = [source[name] for name in ('Plate mark', 'Publisher', 'school', 'Masthead rule', 'stamp')]
    page = Slide(WINNER_TEMPLATE_INDEX, overview.background, WINNER_MARKER, snapshot['school_name'], masthead)
    display, supporting = source['all_clean'], source['share']
    gold = next(item.color for item in _template_pages(theme)[-1].items if item.name == 'Be Green')

    def text(style, name, words, x, y, width, height, size, color, *, bold=False):
        lines = (words,) if isinstance(words, str) else tuple(words) or ('',)
        item = replace(style, name=name, lines=lines, x=x, y=y, width=width, height=height, size=size,
                       align='center', color=color, bold=bold, italic=False, anchor='top', leading=1.13,
                       tracking=0, effect='')
        fitted = _fit_frame(item, lines, allow_ellipsis=False) if words else item
        page.items.append(fitted)
        return fitted

    raw_names = snapshot.get('winner_names') or {}
    names = {role: _clean_text(raw_names.get(role) or '') for role in ('student', 'faculty')}
    heading = 'Golden Plate winners' if all(names.values()) else 'Golden Plate winner'
    text(supporting, 'winner_title', heading, 216, 155, 528, 36, 21, display.color, bold=True)
    text(display, 'winner_detail', 'Congratulations!', 214, 198, 532, 80, 56, gold)
    single = sum(bool(name) for name in names.values()) == 1
    details = snapshot.get('winner_details') or {}
    for role, x in [('student', 221), ('faculty', 495)]:
        name = names[role]
        width = 244
        if name and single:
            width = 440
            x = (WIDTH - width) / 2
        text(supporting, 'winner_role_' + role, role.title() + ' winner' if name else '',
             x, 291, width, 24, 15, supporting.color, bold=True)
        stats = _winner_detail_lines(role, details.get(role) or {}, width) if name else []
        # Reserve real line height for the draw details before fitting a long
        # recipient name, so the two blocks and dateline remain separate.
        name_height = min(112, 493 - 321 - 12 - len(stats) * 14 * 1.13)
        recipient = text(display, 'winner_name_' + role, name, x, 321, width, name_height, 37, display.color)
        top = max(372, recipient.y + len(recipient.lines) * recipient.size * recipient.leading + 8)
        text(supporting, 'winner_stats_' + role, stats, x, top, width, 493 - top, 14, supporting.color)
    return page


def _powerpoint_polygon(slide, contours, *, unit=Pt):
    points = [[(unit(x), unit(y)) for x, y in contour] for contour in contours]
    builder = slide.shapes.build_freeform(*points[0][0])
    builder.add_line_segments(points[0][1:])
    for contour in points[1:]:
        builder.move_to(*contour[0])
        builder.add_line_segments(contour[1:])
    return builder.convert_to_shape()


def _paint_shape(shape, color):
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor.from_string(color)
    shape.line.fill.background()
    shape.shadow.inherit = False
    # LibreOffice also considers the theme's default shadow on a preset shape.
    for effect_ref in shape._element.xpath('p:style/a:effectRef'):
        effect_ref.set('idx', '0')


def _powerpoint_rect(slide, item):
    if item.meter_slice:
        shape = _powerpoint_polygon(slide, [_meter_segment_outline(item)])
    else:
        preset = MSO_SHAPE.ROUNDED_RECTANGLE if item.radius else MSO_SHAPE.RECTANGLE
        shape = slide.shapes.add_shape(preset, Pt(item.x), Pt(item.y), Pt(item.width), Pt(item.height))
        if item.radius:
            shape.adjustments[0] = item.radius / min(item.width, item.height)
    _paint_shape(shape, item.color)
    return shape


_CHART_CORNER_FRACTION = .4  # Same proportion as the opening meter.


def _powerpoint_chart_bar(slide, item, tracks):
    if item.name.endswith(' share'):
        track = tracks.get('distribution')
    elif item.name in ('prev_fill', 'curr_fill'):
        track = tracks.get(item.name.replace('_fill', '_track'))
    else:
        track = tracks.get(item.name)
    if track is None:
        return _powerpoint_rect(slide, item)

    # Snap each boundary once in native units. Adjacent distribution colors
    # therefore meet exactly, even when a share is less than a pixel wide.
    unit = Pt(1)
    full = round(track.width * unit)
    start = round((item.x - track.x) * unit)
    end = round((item.x + item.width - track.x) * unit)
    width = (end - start) / unit
    curved = item.name == track.name or track.name != 'distribution'
    radius = track.height * _CHART_CORNER_FRACTION if width and curved else 0
    crop = None
    if radius and item.name != track.name and end - start < full and width < 2 * radius:
        # A tiny rate on the comparison slide fits the curved start of its track.
        crop = (0, full / unit)
    bar = replace(item, x=track.x + start / unit, width=width, radius=radius, meter_slice=crop)
    shape = _powerpoint_rect(slide, bar)
    shape.left, shape.width = round(track.x * unit) + start, end - start
    return shape


def _chart_window(slide, track, paper, name, right):
    # Build in native coordinates: the hole follows the stored track outline.
    # The left wing hides a fixed-width shape for the portion of its flight
    # before it enters the track. The two-point rim covers exterior bleed.
    top, bottom = track.top - Pt(2), track.top + track.height + Pt(2)
    outer = [(0, top), (right, top), (right, bottom), (0, bottom)]
    outline = Rect(track.name, track.left, track.top, track.width, track.height, paper,
                   radius=min(track.width, track.height) * track.adjustments[0])
    aperture = list(reversed(_meter_outline(outline)))
    window = _powerpoint_polygon(slide, [outer, aperture], unit=round)
    _paint_shape(window, paper)
    window.name = name
    return window


def _add_distribution_window(slide, paper):
    shapes = {shape.name: shape for shape in slide.shapes}
    track = shapes['distribution']
    # Newly revealed colors travel underneath their predecessors, so the
    # straight advancing face starts at the previously recorded boundary.
    shares = [shapes[label + ' share'] for _, label in CATEGORIES if label + ' share' in shapes]
    for share in shares:
        track._element.addnext(share._element)
    window = _chart_window(slide, track, paper, DISTRIBUTION_WINDOW_NAME, Pt(WIDTH))
    (shares[0] if shares else track)._element.addnext(window._element)


def _prepare_rate_chart(slide, paper):
    shapes = {shape.name: shape for shape in slide.shapes}
    for name in shapes.keys() & {'Axis minimum', 'Axis midpoint', 'Axis maximum'}:
        shape = shapes[name]._element
        shape.getparent().remove(shape)

    layers = []
    for prefix, name in RATE_WINDOW_NAMES.items():
        track = shapes[prefix + '_track']
        layers.append(track)
        if prefix + '_fill' in shapes:
            layers.append(shapes[prefix + '_fill'])
        layers.append(_chart_window(slide, track, paper, name, track.left + track.width + Pt(2)))
    # Place both complete bar assemblies beneath every text object, including
    # the school-owned names crossing the stationary masks' left wings.
    for position, shape in enumerate(layers, 2):
        slide.shapes._spTree.insert(position, shape._element)


def _add_meter_window(slide, track, paper):
    # The fly-in starts outside the slide. A paper-colored rim with a real
    # cutout hides its travel until it reaches the track's rounded left edge.
    right = min(WIDTH, track.x + track.width + 1)
    top, bottom = track.y - 1, track.y + track.height + 1
    outside = [(0, top), (right, top), (right, bottom), (0, bottom)]
    shape = _powerpoint_polygon(slide, [outside, list(reversed(_meter_outline(track)))])
    _paint_shape(shape, paper)
    shape.name = PROGRESS_WINDOW_NAME


def _powerpoint(pages, *, animated):
    presentation = Presentation()
    presentation.slide_width, presentation.slide_height = Pt(WIDTH), Pt(HEIGHT)
    has_intro = pages[0].template_index == INTRO_TEMPLATE_INDEX
    presentation.core_properties.title = pages[1 if has_intro else 0].title
    presentation.core_properties.author = 'Golden Plate'
    presentation.core_properties.comments = ''
    for page in pages:
        slide = (add_winner_slide(presentation) if page.template_index == WINNER_TEMPLATE_INDEX
                 else presentation.slides.add_slide(presentation.slide_layouts[6]))
        slide._element.cSld.set('name', page.title)
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = RGBColor.from_string(page.background)
        role_overrides = {}
        meter_track = None
        meter_fill = None
        chart_tracks = {item.name: item for item in page.items
                        if animated and item.name in ('distribution', 'prev_track', 'curr_track')}
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
                shape = _powerpoint_chart_bar(slide, item, chart_tracks)
                if item.name == 'progress_track':
                    meter_track = item
            elif isinstance(item, SignatureFilm):
                shape = item.add_to(slide)
            else:
                shape = slide.shapes.add_picture(BytesIO(item.data), Pt(item.x), Pt(item.y),
                                                 Pt(item.width), Pt(item.height))
                shape._element.nvPicPr.cNvPr.set('descr', item.description)
            shape.name = item.name
            if animated:
                effect = getattr(item, 'effect', '')
                if effect:
                    role_overrides[shape.shape_id] = effect
                if effect == 'fly':
                    meter_fill = shape
                elif effect == 'excess' and meter_fill is not None:
                    # The completed green fill masks the gold segment until its
                    # leading edge crosses the goal. Both segments can fly in.
                    meter_fill._element.addprevious(shape._element)
                elif effect == 'signed_change':
                    slide.shapes._spTree.insert(2, shape._element)
        slide.notes_slide.notes_text_frame.text = '\n'.join(_clean_text(line) for line in page.notes.splitlines())
        if animated:
            if 'distribution' in chart_tracks:
                _add_distribution_window(slide, page.background)
            if page.template_index == 3:
                _prepare_rate_chart(slide, page.background)
            if page.template_index == 4:
                from src.services.presentation_reminders import restyle_powerpoint_reminders
                closing = next(page for page in pages if page.template_index == 5)
                gold = next(item.color for item in closing.items if item.name == 'Be Green')
                restyle_powerpoint_reminders(slide, gold)
            if meter_track and meter_fill is not None:
                _add_meter_window(slide, meter_track, page.background)
            add_slide_motion(slide, page.template_index, role_overrides,
                             morph_from_intro=has_intro and page.template_index == 0)
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
                    bottom = HEIGHT - item.y - item.height
                    if item.meter_slice:
                        points = _meter_segment_outline(item)
                        path = pdf.beginPath()
                        path.moveTo(points[0][0], HEIGHT - points[0][1])
                        for x, y in points[1:]:
                            path.lineTo(x, HEIGHT - y)
                        path.close()
                        pdf.drawPath(path, stroke=0, fill=1)
                    elif item.radius:
                        pdf.roundRect(item.x, bottom, item.width, item.height, item.radius, stroke=0, fill=1)
                    else:
                        pdf.rect(item.x, bottom, item.width, item.height, stroke=0, fill=1)
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
    zone = snapshot.get('reporting_timezone', 'America/New_York') if platform == 'powerpoint' else 'UTC'
    snapshot = {**snapshot, 'records_stamp': _stamp(snapshot['generated_at'], zone)}
    latest, previous = snapshot['latest'], snapshot['previous']
    milestone = snapshot.get('milestone')
    overview = _overview_values(snapshot)
    overview_note = f"{overview['all_clean']}. {overview['share']}."
    if milestone:
        overview_note += f" {overview['goal_label']}."
    if latest:
        overview_note += (f" The latest session was {latest['name']} ({overview['latest_date']}). "
                          f"{overview['latest_counts']}. The clean-plate rate was {overview['latest_rate']}.")
    if overview['latest_change']:
        overview_note += f" The rate changed by {overview['latest_change']} {overview['change_units']}."
    pages = [_bind_page(0, snapshot, theme, overview, overview_note)]
    if kind == 'assembly':
        if latest:
            pages.append(_latest_session_page(snapshot, theme, platform))
            if previous:
                notes = 'Previous session: ' + _session_note(previous) + ' Latest session: ' + _session_note(latest)
                comparison = _comparison_values(snapshot)
                notes += (f" Clean-plate rates: {comparison['prev_rate']} previously and {comparison['curr_rate']} "
                          f"in the latest session. {comparison['rate_comparison']}.")
                pages.append(_bind_page(2, snapshot, theme, comparison, notes))
                pages.append(_bind_page(3, snapshot, theme, comparison, notes))
        if platform == 'powerpoint':
            pages.append(_winner_page(pages[0], snapshot, theme))
            pages[0:1] = opening_pair(pages[0], snapshot['school_name'], theme)
        pages.append(_bind_page(4, snapshot, theme, {}, ''))
        pages.append(_bind_page(5, snapshot, theme, {}, ''))
        if platform == 'powerpoint':
            pages.append(replace(pages[0], template_index=OUTRO_TEMPLATE_INDEX, title=OUTRO_MARKER))
    if platform == 'pdf':
        return _pdf(pages)
    return _powerpoint(pages, animated=platform == 'powerpoint')
