"""Native shape entrances, paths and slide transitions for the school assembly."""
from dataclasses import replace
from itertools import count

from lxml import etree
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn

from src.services.presentation_choreography import Entrance, slide_entrances
from src.services.presentation_google_motion import bar_positions, float_positions, reel_positions
from src.services.presentation_intro import (
    GOOGLE_HANDOFF_MS, GOOGLE_OUTRO_SETTLE_MS, INTRO_TEMPLATE_INDEX, MORPH_MARK, MORPH_NAMES,
    MORPH_WORDMARK, SIGNATURE_FILM, SIGNATURE_FRAME_COVER, SIGNATURE_FRAME_PREFIX, SIGNATURE_LAYOUTS,
)
from src.services.presentation_reels import prepare_category_rolls


PROGRESS_WINDOW_NAME = 'Progress meter window'
DISTRIBUTION_WINDOW_NAME = 'Lunch distribution window'
RATE_WINDOW_NAMES = {'prev': 'Previous lunch rate window', 'curr': 'Latest lunch rate window'}
_FIXED_WINDOWS = {PROGRESS_WINDOW_NAME, DISTRIBUTION_WINDOW_NAME, *RATE_WINDOW_NAMES.values()}
_GOOGLE_MASK_SUFFIXES = (' left corner', ' right corner', ' entrance mask')
_FADE_MS = 250
# The paths run in reverse, from their signed offset to the shape's editable
# design position. The first coordinate is normalized to slide width, the
# second to height. All motion paths have 50% smooth start and end.
_FLOAT_PATHS = {
    # movement: (PowerPoint preset, editable path, rotation center, duration)
    'settle': (64, 'M 0 0 L 0 -0.018 ', (0, -900), 500),
    'lunch': (35, 'M 0 0 L -0.012 0 ', (-600, 0), 410),
    'across': (35, 'M 0 0 L -0.009 0 ', (-450, 0), 390),
    'lift': (42, 'M 0 0 L 0 0.012 ', (0, 600), 360),
    'reel': (42, 'M 0 0 L 0 0.012 ', (0, 600), 250),
}


def _node(parent, tag, **attrs):
    return etree.SubElement(parent, qn('p:' + tag), {key: str(value) for key, value in attrs.items()})


def _start(time, delay):
    return _node(_node(time, 'stCondLst'), 'cond', delay=delay)


def _effect(group, ids, preset, kind, subtype, delay, group_id, *, eased=False):
    easing = {'accel': 50000, 'decel': 50000} if eased else {}
    time = _node(_node(group, 'par'), 'cTn', id=next(ids), presetID=preset, presetClass=kind,
                 presetSubtype=subtype, fill='hold', grpId=group_id, nodeType='withEffect', **easing)
    _start(time, delay)
    return _node(time, 'childTnLst')


def _behavior(action, ids, shape, duration, properties=(), *, hold=False, start=False, reverse=False, base=False):
    behavior = _node(action, 'cBhvr', **({'additive': 'base'} if base else {}))
    time = _node(behavior, 'cTn', id=next(ids), dur=duration)
    if hold:
        time.set('fill', 'hold')
    if reverse:
        time.set('spd', '-100000')
    if start:
        _start(time, 0)
    _node(_node(behavior, 'tgtEl'), 'spTgt', spid=shape)
    if properties:
        names = _node(behavior, 'attrNameLst')
        for name in properties:
            _node(names, 'attrName').text = name
    return time


def _visibility(actions, ids, shape, value):
    action = _node(actions, 'set')
    _behavior(action, ids, shape, 1, ('style.visibility',), hold=True, start=True)
    _node(_node(action, 'to'), 'strVal', val=value)


def _axis(actions, ids, shape, prop, duration, origin, destination):
    animation = _node(actions, 'anim', calcmode='lin', valueType='num')
    _behavior(animation, ids, shape, duration, (prop,), hold=True, base=True)
    keyframes = _node(animation, 'tavLst')
    for time, value in ((0, origin), (100000, destination)):
        _node(_node(_node(keyframes, 'tav', tm=time), 'val'), 'strVal', val=value)


def _bar_entrance(group, ids, shape, cue):
    actions = _effect(group, ids, 2, 'entr', 8, cue.start, 0, eased=True)
    _visibility(actions, ids, shape, 'visible')
    # Whole bars start off slide like the opener. Each subsequent color in a
    # stack travels its own width, from behind the already-filled colors.
    origin_x = '0-#ppt_w/2' if cue.movement == 'fly' else '#ppt_x-#ppt_w'
    _axis(actions, ids, shape, 'ppt_x', cue.duration, origin_x, '#ppt_x')
    _axis(actions, ids, shape, 'ppt_y', cue.duration, '#ppt_y', '#ppt_y')


def _fade(group, ids, shape, delay, *, group_id):
    fade = _effect(group, ids, 10, 'entr', 0, delay, group_id)
    _visibility(fade, ids, shape, 'visible')
    _behavior(_node(fade, 'animEffect', transition='in', filter='fade'), ids, shape, _FADE_MS)
    return fade


def _float(group, ids, shape, delay, settings):
    preset, path, center, duration = settings
    motion = _effect(group, ids, preset, 'path', 0, delay, 0, eased=True)
    action = _node(motion, 'animMotion', origin='layout', path=path, pathEditMode='relative', rAng=0,
                   ptsTypes='AA')
    _behavior(action, ids, shape, duration, ('ppt_x', 'ppt_y'), hold=True, reverse=True)
    _node(action, 'rCtr', x=center[0], y=center[1])


def _color(actions, ids, shape, prop, start, end, duration):
    action = _node(actions, 'animClr', clrSpc='rgb')
    _behavior(action, ids, shape, duration, (prop,), hold=True)
    for tag, color in (('from', start), ('to', end)):
        etree.SubElement(_node(action, tag), qn('a:srgbClr'), val=color)


def _pulse(group, ids, shape, delay, group_id, scale):
    actions = _effect(group, ids, 6, 'emph', 0, delay, group_id, eased=True)
    action = _node(actions, 'animScale')
    clock = _behavior(action, ids, shape, 140, ('ScaleX', 'ScaleY'), hold=True)
    clock.set('autoRev', '1')
    _node(action, 'from', x=100000, y=100000)
    _node(action, 'to', x=scale, y=scale)


def _disappear(group, ids, shape, delay, group_id):
    actions = _effect(group, ids, 1, 'exit', 0, delay, group_id)
    _visibility(actions, ids, shape, 'hidden')


def _build(builds, shape, group_id):
    background = {'animBg': 1} if shape.shape_type != MSO_SHAPE_TYPE.TEXT_BOX else {}
    _node(builds, 'bldP', spid=shape.shape_id, grpId=group_id, **background)


def _entrance(group, ids, builds, shape, cue, initial_color=None):
    identifier = shape.shape_id
    path = _FLOAT_PATHS.get(cue.movement)
    if cue.movement in ('fly', 'excess', 'segment'):
        _bar_entrance(group, ids, identifier, cue)
    else:
        fade = _fade(group, ids, identifier, cue.start, group_id=1 if path else 0)
        if initial_color:
            _color(fade, ids, identifier, 'style.color', initial_color, initial_color, 1)
    _build(builds, shape, 0)
    if path:
        _float(group, ids, identifier, cue.start, path)
        _build(builds, shape, 1)


def _category_group(group, ids, builds, shapes, roll):
    key = shapes[roll.label + ' key']
    label = shapes[roll.label + ' label']
    value = shapes[roll.key]
    share = shapes.get(roll.label + ' share')
    _entrance(group, ids, builds, key, Entrance(key.name, 0, 'fade', 0))
    label_ink = str(shapes['Student clean plates label'].text_frame.paragraphs[0].runs[0].font.color.rgb)
    _entrance(group, ids, builds, label, Entrance(label.name, 0, 'fade', 0), label_ink if roll.gold else None)
    if share is not None:
        _entrance(group, ids, builds, share, Entrance(share.name, 20, 'segment' if share.width else 'fade', 540))

    # Each successive reel position stays a little longer as the wheel settles.
    # Its native y keyframes move the glyph upward; disappearing at the handoff
    # prevents intermediate counts from ever accumulating beside the final one.
    boundaries = (25, 100, 195, 315, 470)
    for name, start, end in zip(roll.digits, boundaries[:-1], boundaries[1:], strict=True):
        digit = shapes[name]
        identifier = digit.shape_id
        actions = _effect(group, ids, 1, 'entr', 0, start, 0)
        _visibility(actions, ids, identifier, 'visible')
        _color(actions, ids, identifier, 'style.color', roll.ink, roll.ink, 1)
        _axis(actions, ids, identifier, 'ppt_y', end - start, '#ppt_y+0.012', '#ppt_y-0.012')
        _disappear(group, ids, identifier, end, 1)
        _build(builds, digit, 0)
        _build(builds, digit, 1)
    _entrance(group, ids, builds, value, Entrance(value.name, boundaries[-1], 'reel', 0),
              roll.ink if roll.gold else None)

    if roll.gold:
        # Both canonical text boxes are already gold in the printable final
        # frame. During playback, start neutral and reward the settled zero.
        for shape, neutral, group_id in ((value, roll.ink, 2), (label, label_ink, 1)):
            actions = _effect(group, ids, 3, 'emph', 0, 920, group_id)
            _color(actions, ids, shape.shape_id, 'style.color', neutral, roll.gold, 160)
            _build(builds, shape, group_id)
        _pulse(group, ids, value.shape_id, 1080, 3, 108000)
        _build(builds, value, 3)
        marker = shapes[roll.marker]
        actions = _effect(group, ids, 1, 'entr', 0, 1080, 0)
        _visibility(actions, ids, marker.shape_id, 'visible')
        _color(actions, ids, marker.shape_id, 'fillcolor', roll.gold, roll.gold, 1)
        _pulse(group, ids, marker.shape_id, 1080, 1, 140000)
        _disappear(group, ids, marker.shape_id, 1365, 2)
        for group_id in (0, 1, 2):
            _build(builds, marker, group_id)
    # The first legend key consumes the presenter click. Its siblings share
    # that click's clock, including entrances with a positive delay.
    first_effect = group.find(qn('p:par') + '/' + qn('p:cTn'))
    first_effect.set('nodeType', 'clickEffect')


def _appear_at(group, ids, builds, shape, start):
    actions = _effect(group, ids, 1, 'entr', 0, start, 0)
    _visibility(actions, ids, shape.shape_id, 'visible')
    _build(builds, shape, 0)


def _google_bar(slide, group, ids, builds, shape, cue):
    for frame, start in bar_positions(slide, shape, cue):
        _appear_at(group, ids, builds, frame, start)


def _google_float(slide, group, ids, builds, shape, cue):
    _, _, center, duration = _FLOAT_PATHS.get(cue.movement, _FLOAT_PATHS['lunch'])
    if cue.movement == 'fade':
        center = (0, 0)  # A signed change of zero stays on its baseline.
    frames, cover = float_positions(slide, shape, center, duration, _FADE_MS)
    end = cue.start + duration
    for i, (frame, elapsed) in enumerate(frames):
        _appear_at(group, ids, builds, frame, cue.start + elapsed)
        stop = cue.start + frames[i + 1][1] if i + 1 < len(frames) else end + _FADE_MS
        _disappear(group, ids, frame.shape_id, stop, 1)
        _build(builds, frame, 1)
    _fade(group, ids, shape.shape_id, end, group_id=0)
    _build(builds, shape, 0)
    _appear_at(group, ids, builds, cover, end + _FADE_MS)


def _google_category_group(slide, group, ids, builds, shapes, roll):
    """Use effects that survive Drive conversion, including the real four click groups."""
    settled_at = 920
    caption = shapes[roll.label + ' label']
    for name in (roll.label + ' key', roll.label + (' neutral label' if roll.marker else ' label')):
        shape = shapes[name]
        _fade(group, ids, shape.shape_id, 0, group_id=0)
        _build(builds, shape, 0)
    group.find(qn('p:par') + '/' + qn('p:cTn')).set('nodeType', 'clickEffect')
    share = shapes.get(roll.label + ' share')
    if share is not None:
        _google_bar(slide, group, ids, builds, share, Entrance(share.name, 20, 'segment', 540))
    digits = [shapes[name] for name in roll.digits]
    stops = (25, 100, 195, 315, 470)
    for shape, start, end in reel_positions(slide, digits, stops):
        _appear_at(group, ids, builds, shape, start)
        _disappear(group, ids, shape.shape_id, end, 1)
        _build(builds, shape, 1)
    value = shapes[roll.key]
    landing = digits[-1]
    _appear_at(group, ids, builds, landing, stops[-1])
    final_at = settled_at if roll.marker else stops[-1]
    if roll.marker:
        neutral = shapes[roll.label + ' neutral label']
        _disappear(group, ids, neutral.shape_id, settled_at + _FADE_MS, 1)
        _build(builds, neutral, 1)
        _fade(group, ids, caption.shape_id, settled_at, group_id=0)
        _build(builds, caption, 0)
        enlarged = shapes[roll.key + ' emphasis']
        _fade(group, ids, enlarged.shape_id, settled_at, group_id=0)
        _build(builds, enlarged, 0)
        final_at += _FADE_MS
        _disappear(group, ids, enlarged.shape_id, final_at + _FADE_MS, 1)
        _build(builds, enlarged, 1)
    _fade(group, ids, value.shape_id, final_at, group_id=0)
    _build(builds, value, 0)
    _disappear(group, ids, landing.shape_id, final_at + _FADE_MS, 1)
    _build(builds, landing, 1)
    if roll.marker:
        marker = shapes[roll.marker]
        _fade(group, ids, marker.shape_id, settled_at, group_id=0)
        leaving = _effect(group, ids, 10, 'exit', 0, final_at, 1)
        _behavior(_node(leaving, 'animEffect', transition='out', filter='fade'), ids, marker.shape_id, _FADE_MS)
        _build(builds, marker, 0)
        _build(builds, marker, 1)


def _timing_group(children, ids, *, automatic):
    trigger = _node(_node(children, 'par'), 'cTn', id=next(ids), fill='hold')
    starts = _node(trigger, 'stCondLst')
    _node(starts, 'cond', delay='indefinite')
    if automatic:
        _node(_node(starts, 'cond', evt='onBegin', delay=0), 'tn', val=2)
    wave = _node(_node(_node(trigger, 'childTnLst'), 'par'), 'cTn', id=next(ids), fill='hold')
    _start(wave, 0)
    return _node(wave, 'childTnLst')


def _signature_motion(root_children, group, ids, builds, shapes, *, handoff):
    film, mark, word = (shapes[name] for name in (SIGNATURE_FILM, MORPH_MARK, MORPH_WORDMARK))
    # The passive media node is the playback target. The automatic main
    # sequence plays it once, alongside the editable word rising into view.
    video = _node(root_children, 'video', fullScrn=0)
    media = _node(video, 'cMediaNode', vol=0, mute=1, showWhenStopped=0)
    passive = _node(media, 'cTn', id=next(ids), fill='hold', display=0)
    _start(passive, 'indefinite')
    _node(_node(media, 'tgtEl'), 'spTgt', spid=film.shape_id)
    play = _effect(group, ids, 1, 'mediacall', 0, 0, 0)
    # The supplied reveal runs for 104 frames at 60 fps.
    _behavior(_node(play, 'cmd', type='call', cmd='playFrom(0.0)'), ids, film.shape_id, 1733)

    # In the tutorial, text rises 74 px behind a fixed overflow edge. Moving
    # a 37 pt box up by its own height while opening it from the top keeps the
    # clipping boundary stationary as the gold line curls into the plate.
    start, duration = 950, 500
    reveal = _effect(group, ids, 22, 'entr', 1, start, 1, eased=True)
    _visibility(reveal, ids, word.shape_id, 'visible')
    _behavior(_node(reveal, 'animEffect', transition='in', filter='wipe(down)'), ids, word.shape_id, duration)
    _float(group, ids, word.shape_id, start, (42, 'M 0 0 L 0 0.06851852 ', (0, 3426), duration))
    _build(builds, word, 1)
    _build(builds, word, 0)

    # Both layers show the same settled plate at this frame. Reveal the native
    # picture and retire playback before its decoder can return to the poster.
    appear = _effect(group, ids, 1, 'entr', 0, handoff, 0)
    _visibility(appear, ids, mark.shape_id, 'visible')
    _disappear(group, ids, film.shape_id, handoff, 0)
    _build(builds, mark, 0)
    _build(builds, film, 0)


def _google_signature_motion(group, ids, builds, shapes, settled_at):
    # Slides imports these native visibility effects even when its slideshow
    # renderer freezes the first image of a GIF or discards an embedded film.
    def appear(shape, when):
        action = _effect(group, ids, 1, 'entr', 0, when, 0)
        _visibility(action, ids, shape.shape_id, 'visible')
        _build(builds, shape, 0)

    paper = shapes.pop(SIGNATURE_FRAME_COVER)
    paper._element.nvSpPr.cNvPr.set('descr', '[gp-motion-only]')
    _disappear(group, ids, paper.shape_id, 0, 0)
    _build(builds, paper, 0)
    starts = sorted((int(name.removeprefix(SIGNATURE_FRAME_PREFIX)), name)
                    for name in shapes if name.startswith(SIGNATURE_FRAME_PREFIX))
    for (start, name), end in zip(starts, [t for t, _ in starts[1:]] + [settled_at], strict=True):
        frame = shapes.pop(name)
        appear(frame, start)
        _disappear(group, ids, frame.shape_id, end, 1)
        _build(builds, frame, 1)
    for name in list(shapes):
        if name in MORPH_NAMES or name == SIGNATURE_FILM or name.endswith(_GOOGLE_MASK_SUFFIXES):
            appear(shapes.pop(name), settled_at)


def add_slide_motion(slide, template_index, role_overrides, *, morph_from_intro=False, google=False, seed=False):
    # Older PowerPoint readers use the fallback fade and share the timing tree.
    transition = parse_xml(f'''
        <mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" {nsdecls("p")}>
          <mc:Choice xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main" Requires="p14">
            <p:transition p14:dur="{_FADE_MS}" advClick="1"><p:fade/></p:transition>
          </mc:Choice>
          <mc:Fallback><p:transition advClick="1"><p:fade/></p:transition></mc:Fallback>
        </mc:AlternateContent>''')
    if google:
        transition = parse_xml(f'<p:transition {nsdecls("p")} xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main" '
                               f'p14:dur="{_FADE_MS}" spd="fast" advClick="1"><p:fade/></p:transition>')
    elif morph_from_intro:
        transition.insert(0, parse_xml(f'''
            <mc:Choice xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" {nsdecls("p")}
                       xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main"
                       xmlns:p159="http://schemas.microsoft.com/office/powerpoint/2015/09/main" Requires="p159">
              <p:transition p14:dur="850" advClick="1"><p159:morph option="byObject"/></p:transition>
            </mc:Choice>'''))
    if template_index in SIGNATURE_LAYOUTS:
        # Mac PowerPoint can skip the film at zero. Start the intro Morph just
        # after the word settles at 1450 ms and the native logo takes over.
        advance = '1500' if template_index == INTRO_TEMPLATE_INDEX else '2283'
        for variant in transition.iter(qn('p:transition')):
            variant.set('advClick', '1' if google else '0')
            variant.set('advTm', advance)
    slide._element.append(transition)
    if google and template_index == INTRO_TEMPLATE_INDEX:
        return  # Editable cover; the live opening plays directly on the first results page.
    # Restyling can remove a rule or rebuild paragraphs. Bind to the final
    # editable shapes and animate multi-line reminders together by shape ID.
    rolls = prepare_category_rolls(slide, google=google, seed=seed) if template_index == 1 else []
    # These two objects arrive already visible from the intro. An entrance or
    # build-list target on the receiving slide would make them disappear.
    fixed = _FIXED_WINDOWS | MORPH_NAMES if morph_from_intro and not google else _FIXED_WINDOWS
    shapes = {role_overrides.get(shape.shape_id, shape.name): shape for shape in slide.shapes
              if shape.name not in fixed and not (google and not morph_from_intro
                                                  and shape.name.endswith(_GOOGLE_MASK_SUFFIXES))}
    if not shapes:
        return
    timing = _node(slide._element, 'timing')
    root = _node(_node(_node(timing, 'tnLst'), 'par'), 'cTn', id=1, dur='indefinite',
                 restart='never', nodeType='tmRoot')
    root_children = _node(root, 'childTnLst')
    sequence = _node(root_children, 'seq', concurrent=1, nextAc='seek')
    main = _node(sequence, 'cTn', id=2, dur='indefinite', nodeType='mainSeq')
    children = _node(main, 'childTnLst')
    ids = count(3)
    group = _timing_group(children, ids, automatic=True)
    for tag, event in [('prevCondLst', 'onPrev'), ('nextCondLst', 'onNext')]:
        condition = _node(_node(sequence, tag), 'cond', evt=event, delay=0)
        _node(_node(condition, 'tgtEl'), 'sldTgt')
    builds = _node(timing, 'bldLst')
    if google and (morph_from_intro or template_index in SIGNATURE_LAYOUTS):
        _google_signature_motion(group, ids, builds, shapes,
                                 GOOGLE_HANDOFF_MS if morph_from_intro else GOOGLE_OUTRO_SETTLE_MS)
    if template_index in SIGNATURE_LAYOUTS:
        if google:
            return
        handoff = 1460 if template_index == INTRO_TEMPLATE_INDEX else 1650
        _signature_motion(root_children, group, ids, builds, shapes, handoff=handoff)
        return
    category_names = {name for roll in rolls for name in roll.object_names()}
    scaffold = {name: shape for name, shape in shapes.items() if name not in category_names}
    for cue in slide_entrances(template_index, scaffold):
        if google and morph_from_intro:
            cue = replace(cue, start=cue.start + GOOGLE_HANDOFF_MS)
        if google and cue.movement in ('fly', 'excess'):
            _google_bar(slide, group, ids, builds, shapes[cue.name], cue)
            continue
        if google and (cue.movement in _FLOAT_PATHS or seed and shapes[cue.name].name == 'latest_change'):
            _google_float(slide, group, ids, builds, shapes[cue.name], cue)
            continue
        _entrance(group, ids, builds, shapes[cue.name], cue)
    for roll in rolls:
        click_group = _timing_group(children, ids, automatic=False)
        if google:
            _google_category_group(slide, click_group, ids, builds, shapes, roll)
        else:
            _category_group(click_group, ids, builds, shapes, roll)
