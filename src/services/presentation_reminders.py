"""Native PowerPoint typography for the two spoken assembly reminders."""

from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Pt


def _set_lines(shape, lines, highlight=None, gold=None):
    """Keep a whole instruction in one editable shape, with an intentional reading order."""
    frame = shape.text_frame
    frame.clear()
    for index, (text, family, size, leading, color, bold) in enumerate(lines):
        paragraph = frame.add_paragraph() if index else frame.paragraphs[0]
        paragraph.alignment = PP_ALIGN.LEFT
        paragraph.line_spacing = Pt(leading)
        paragraph.space_before = paragraph.space_after = Pt(0)
        parts = [(text, color)]
        if highlight and highlight in text:
            before, phrase, after = text.partition(highlight)
            parts = [(before, color), (phrase, gold), (after, color)]
        for words, ink in parts:
            if words:
                run = paragraph.add_run()
                run.text = words
                run.font.name = family
                run.font.size = Pt(size)
                run.font.bold = bold
                run.font.color.rgb = ink


def restyle_powerpoint_reminders(slide, closing_color):
    shapes = {shape.name: shape for shape in slide.shapes}
    title = shapes['title']
    portion = shapes['Portion choice']
    plate = shapes['Plate count']
    # Source the wording from the same master as the printable and Google
    # versions. A future copy revision can still use the original full text.
    choice, condition, appetite = ' '.join(portion.text.split()).partition(' that ')
    location, comma, instruction = ' '.join(plate.text.split()).partition(', ')
    action, sequence, finish = instruction.partition(' before ')
    if not (condition and comma and sequence):
        return

    ink = title.text_frame.paragraphs[0].runs[0].font.color.rgb
    muted = shapes['stamp'].text_frame.paragraphs[0].runs[0].font.color.rgb
    gold = RGBColor.from_string(closing_color)
    title.top, title.height = Pt(101), Pt(26)
    _set_lines(title, [(title.text, 'Georgia', 17, 23, muted, True)])

    # One rule separates the two actions. The masthead already supplies the
    # top boundary, so a second rule between the label and the first action
    # would interrupt their reading order.
    upper_rule = shapes['Serving line rule']._element
    upper_rule.getparent().remove(upper_rule)
    shapes['Dish return rule'].top = Pt(264)

    portion.top, portion.width, portion.height = Pt(143), Pt(864), Pt(99)
    _set_lines(portion, [
        (choice, 'Newsreader', 51, 61, ink, False),
        (condition.strip() + ' ' + appetite, 'Georgia', 26, 36, ink, False),
    ], 'fits your appetite', gold)

    plate.top, plate.width, plate.height = Pt(288), Pt(864), Pt(136)
    _set_lines(plate, [
        (location + comma.rstrip(), 'Georgia', 21, 30, muted, False),
        (action, 'Newsreader', 51, 61, ink, False),
        (sequence.strip() + ' ' + finish, 'Georgia', 26, 36, ink, False),
    ], 'Compost Coach', gold)
