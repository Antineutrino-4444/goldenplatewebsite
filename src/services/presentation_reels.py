"""Editable intermediate numerals and endpoint markers for the lunch breakdown."""
from copy import deepcopy
from dataclasses import dataclass
from random import Random

from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Pt


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
                *self.digits, self.marker}


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


def prepare_category_rolls(slide):
    shapes = {shape.name: shape for shape in slide.shapes}
    paper = slide.background.fill.fore_color.rgb
    normal_ink = _number_color(shapes['student_clean'])
    track = shapes['distribution']
    boundary = track.left
    categories = [('Student clean plates', 'student_clean'), ('Faculty clean plates', 'faculty_clean'),
                  ('Dirty plates', 'dirty'), ('Very dirty plates', 'very_dirty')]
    rolls = []
    for label, key in categories:
        final = shapes[key]
        count = int(final.text.replace(',', ''))
        color = _number_color(final)
        gold = color if key in ('dirty', 'very_dirty') and count == 0 and color != normal_ink else None
        ink = 'FFFFFF' if gold and sum(paper) < 3 * 128 else normal_ink
        digits = []
        for step, value in enumerate(_interim_counts(key, count), 1):
            # Put paper-colored helpers behind the permanent editable numeral.
            # The show temporarily gives them ink. The saved slide and print
            # view show only the actual result at this location.
            copy = deepcopy(final._element)
            name = f'{key} roll {step}'
            props = copy.nvSpPr.cNvPr
            props.set('id', str(slide.shapes._next_shape_id))
            props.set('name', name)
            final._element.addprevious(copy)
            run = slide.shapes._shape_factory(copy).text_frame.paragraphs[0].runs[0]
            run.text = f'{value:,}'
            run.font.color.rgb = paper
            digits.append(name)

        marker_name = None
        if gold:
            # The dot touches the top of the track at the zero category's
            # cumulative boundary. It adds no width to the measured bar.
            diameter = Pt(6)
            dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, boundary - diameter // 2, track.top - diameter,
                                         diameter, diameter)
            dot.name = marker_name = label + ' zero marker'
            dot.fill.solid()
            dot.fill.fore_color.rgb = paper
            dot.line.fill.background()
            dot.shadow.inherit = False
            for ref in dot._element.xpath('p:style/a:effectRef'):
                ref.set('idx', '0')
        share = shapes.get(label + ' share')
        if share is not None:
            boundary = share.left + share.width
        rolls.append(CategoryRoll(label, key, digits, ink, gold, marker_name))
    return rolls
