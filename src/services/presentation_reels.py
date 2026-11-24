"""Editable intermediate numerals and endpoint markers for the lunch breakdown."""
from copy import deepcopy
from dataclasses import dataclass
from random import Random

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Pt


CATEGORIES = (
    ('student_clean', 'Student clean plates'), ('faculty_clean', 'Faculty clean plates'),
    ('dirty', 'Dirty plates'), ('very_dirty', 'Very dirty plates'),
)


@dataclass
class CategoryRoll:
    label: str
    key: str
    digits: list
    ink: str
    gold: str | None
    marker: str | None

    def object_names(self):
        return {self.key, self.label + ' label', self.label + ' key', self.label + ' share',
                self.key + ' emphasis', self.label + ' neutral label', *self.digits, self.marker}


def copy_frame(slide, source, name):
    element = deepcopy(source._element)
    props = element.nvSpPr.cNvPr
    props.set('id', str(slide.shapes._next_shape_id))
    props.set('name', name)
    source._element.addprevious(element)
    return slide.shapes._shape_factory(element)


def mark_google_motion_only(shape):
    # The Slides API can update an existing timed object, but cannot add its
    # entrance or exit to an older deck. Never create these helpers at rest.
    props = shape._element.nvSpPr.cNvPr
    description = props.get('descr', '')
    if '[gp-motion-only]' not in description:
        props.set('descr', (description + ' [gp-motion-only]').strip())
    return shape


def _interim_counts(key, count):
    # Draw across the full display width, omitting the actual result. Four
    # separate bands give distinct digits even on the single-digit reel.
    digits = len(str(count))
    first = 10 ** (digits - 1) if digits > 1 else 0
    eligible = 10 ** digits - first - 1
    random = Random(f'{key}:{count}')
    stops = [first + random.randrange(i * eligible // 4, (i + 1) * eligible // 4) for i in range(4)]
    stops = [value + (value >= count) for value in stops]
    random.shuffle(stops)
    if stops == sorted(stops) or stops == sorted(stops, reverse=True):
        stops[1], stops[2] = stops[2], stops[1]
    return stops


def _number_color(shape):
    return str(shape.text_frame.paragraphs[0].runs[0].font.color.rgb)


def prepare_category_rolls(slide, *, google=False, seed=False):
    shapes = {shape.name: shape for shape in slide.shapes}
    paper = slide.background.fill.fore_color.rgb
    normal_ink = _number_color(shapes['student_clean'])
    track = shapes['distribution']
    boundary = track.left
    rolls = []
    for key, label in CATEGORIES:
        final = shapes[key]
        count = int(final.text.replace(',', ''))
        color = _number_color(final)
        gold = color if key in ('dirty', 'very_dirty') and count == 0 and color != normal_ink else None
        ink = 'FFFFFF' if gold and sum(paper) < 3 * 128 else normal_ink
        digits = []
        frames = [(f'{key} roll {step}', value) for step, value in enumerate(_interim_counts(key, count), 1)]
        if google:
            # Slides drops runtime color changes. Stage each value on its
            # own frame, then cover it with the final editable number so the
            # editor and print view always show only the settled result.
            final.fill.solid()
            final.fill.fore_color.rgb = paper
            frames.append((f'{key} landing', count))
        for name, value in frames:
            # Put paper-colored helpers behind the permanent editable numeral.
            # The show temporarily gives them ink. The saved slide and print
            # view show only the actual result at this location.
            copy = copy_frame(slide, final, name)
            run = copy.text_frame.paragraphs[0].runs[0]
            run.text = f'{value:,}'
            run.font.color.rgb = RGBColor.from_string(ink) if google else paper
            if google:
                mark_google_motion_only(copy)
            digits.append(name)

        marker_name = None
        if gold or (seed and key in ('dirty', 'very_dirty')):
            if google:
                # A gold caption at click time would give the zero away before
                # its number stops. Introduce a neutral caption first, then
                # crossfade a slightly larger gold digit into the settled one.
                caption = shapes[label + ' label']
                caption.fill.solid()
                caption.fill.fore_color.rgb = paper
                neutral = mark_google_motion_only(copy_frame(slide, caption, label + ' neutral label'))
                neutral.text_frame.paragraphs[0].runs[0].font.color.rgb = RGBColor.from_string(
                    _number_color(shapes['Student clean plates label']))
                emphasis = mark_google_motion_only(copy_frame(slide, final, key + ' emphasis'))
                if gold:
                    font = emphasis.text_frame.paragraphs[0].runs[0].font
                    font.size = Pt(font.size.pt * 1.08)
            # The dot touches the top of the track at the zero category's
            # cumulative boundary. It adds no width to the measured bar.
            diameter = Pt(6)
            dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, boundary - diameter // 2, track.top - diameter,
                                         diameter, diameter)
            dot.name = marker_name = label + ' zero marker'
            if google:
                mark_google_motion_only(dot)
            if google and not gold:
                dot.fill.background()
            else:
                dot.fill.solid()
                dot.fill.fore_color.rgb = RGBColor.from_string(gold) if google else paper
            dot.line.fill.background()
            dot.shadow.inherit = False
            for ref in dot._element.xpath('p:style/a:effectRef'):
                ref.set('idx', '0')
        share = shapes.get(label + ' share')
        if share is not None and count:
            boundary = share.left + share.width
        rolls.append(CategoryRoll(label, key, digits, ink, gold, marker_name))
    return rolls
