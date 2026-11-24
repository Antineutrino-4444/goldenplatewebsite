"""Short, measured motion using the native objects and cue times kept by Slides."""
from copy import deepcopy

from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Pt

from .presentation_reels import copy_frame, mark_google_motion_only


def _travel(t):
    """Distance for PowerPoint's equal smooth start and end fractions."""
    return 2 * t * t if t < .5 else 1 - 2 * (1 - t) ** 2


def bar_positions(slide, fill, cue):
    # Google turns every imported Fly In into a journey of one slide width.
    # Sample the visible rectangle at 30 fps along the actual PowerPoint
    # 50% smooth-start / 50% smooth-end motion. Successive opaque rectangles
    # cover their predecessors; the final editable shape lands at full width.
    steps = max(2, round(cue.duration * .03))
    for i in range(1, steps):
        t = i / steps
        eased = _travel(t)
        distance = fill.width * eased
        if cue.movement == 'fly':
            distance = (fill.left + fill.width) * eased - fill.left
        shape = mark_google_motion_only(copy_frame(slide, fill, f'{fill.name} motion frame {i:02}'))
        shape.width = max(Pt(.01), round(distance))
        if distance <= 0:
            shape.fill.background()
        yield shape, cue.start + round(cue.duration * t)
    yield fill, cue.start + cue.duration


def _paper_mask(slide, name, x, y, width, height, anchor):
    mask = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, width, height)
    mask.name = name
    mask.fill.solid()
    mask.fill.fore_color.rgb = slide.background.fill.fore_color.rgb
    mask.line.fill.background()
    mask.shadow.inherit = False
    for ref in mask._element.xpath('p:style/a:effectRef'):
        ref.set('idx', '0')
    anchor.addprevious(mark_google_motion_only(mask)._element)
    return mask


def float_positions(slide, target, center, duration, fade_ms):
    # The converter removes PowerPoint paths. Reconstruct the short path with
    # local editable copies whose ink ramps from the paper to the original
    # run color during exactly the first quarter second.
    presentation = slide.part.package.presentation_part.presentation
    dx = round(presentation.slide_width * center[0] / 50000)
    dy = round(presentation.slide_height * center[1] / 50000)
    paper = tuple(slide.background.fill.fore_color.rgb)
    steps = round(duration / 40)
    frames = []
    for i in range(1, steps + 1):
        elapsed = round(i * duration / steps)
        remaining = 1 - _travel(i / steps)
        frame = mark_google_motion_only(copy_frame(slide, target, f'{target.name} motion frame {i:02}'))
        frame.left += round(dx * remaining)
        frame.top += round(dy * remaining)
        opacity = min(1., elapsed / fade_ms)
        for color in frame._element.xpath('.//a:rPr/a:solidFill/a:srgbClr'):
            rgb = bytes.fromhex(color.get('val'))
            color.set('val', bytes(round(p + opacity * (c - p)) for p, c in zip(paper, rgb)).hex().upper())
        frames.append((frame, elapsed))
    # Cover all offset text in the static editor and on paper. During the
    # show this mask arrives only after the one canonical text box is opaque.
    mask = _paper_mask(slide, target.name + ' motion cover', target.left + min(dx, 0), target.top + min(dy, 0),
                       target.width + abs(dx), target.height + abs(dy), target._element)
    return frames, mask


def reel_positions(slide, digits, boundaries):
    # A pair of equally spaced lines moves behind two fixed masks. At the
    # boundary, the entering row of one pair becomes the first row of the
    # next. No number teleports between baselines. Keep the masks and moving
    # lines below the other slide artwork so they never occlude the legend.
    anchor = slide.shapes[0]._element
    for source, following, start, end in zip(digits[:-1], digits[1:], boundaries[:-1], boundaries[1:], strict=True):
        steps = max(3, round((end - start) * .04))
        yield source, start, start + round((end - start) / steps)
        for i in range(1, steps):
            shape = mark_google_motion_only(copy_frame(slide, source, f'{source.name} motion frame {i:02}'))
            extra = deepcopy(following.text_frame.paragraphs[0]._p)
            shape.text_frame._txBody.append(extra)
            shape.top = source.top - round(source.height * i / steps)
            shape.height = 2 * source.height
            anchor.addprevious(shape._element)
            yield (shape, start + round((end - start) * i / steps),
                   start + round((end - start) * (i + 1) / steps))
    for side in ('top', 'bottom'):
        target = digits[-1]
        y = target.top - target.height if side == 'top' else target.top + target.height
        _paper_mask(slide, target.name + ' reel ' + side + ' mask', target.left, y, target.width, target.height, anchor)
