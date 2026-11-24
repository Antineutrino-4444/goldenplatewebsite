from copy import deepcopy
from io import BytesIO
import re
from zipfile import ZipFile

import pytest
from lxml import etree
from pptx import Presentation
from pptx.enum.shapes import PP_PLACEHOLDER

from src.services import presentation_fonts
from src.services.presentation_exports import PALETTES, generate_deck


NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'mc': 'http://schemas.openxmlformats.org/markup-compatibility/2006',
      'p14': 'http://schemas.microsoft.com/office/powerpoint/2010/main'}


@pytest.fixture
def results():
    latest = dict(name='Community Lunch', date='2026-11-18', student_clean=85, faculty_clean=5,
                  clean=90, dirty=8, very_dirty=2, total=100, clean_percentage=90)
    prior = dict(latest, name='Autumn Lunch', date='2026-11-09', student_clean=43, faculty_clean=2,
                 clean=45, dirty=12, very_dirty=3, total=60, clean_percentage=75)
    return dict(school_name='Aurora School', school_code='AUR', generated_at='2026-11-20T13:00:00+00:00',
                totals=dict(clean=135, total=160, clean_percentage=84.4, session_count=2),
                latest=latest, previous=prior, change=dict(clean=45, total=40, clean_percentage_points=15.0))


@pytest.mark.parametrize(('instant', 'zone', 'expected'), [
    ('2026-07-01T01:15:00Z', None, 'Jun 30, 2026 at 21:15 EDT'),
    ('2026-11-01T05:30:00Z', None, 'Nov 1, 2026 at 01:30 EDT'),
    ('2026-11-01T06:30:00Z', None, 'Nov 1, 2026 at 01:30 EST'),
    ('2026-11-01T06:30:00', 'America/Los_Angeles', 'Oct 31, 2026 at 23:30 PDT'),
    ('2026-11-01T06:30:00Z', 'invalid', 'Nov 1, 2026 at 01:30 EST'),
])
def test_powerpoint_footer_uses_the_school_clock(results, instant, zone, expected):
    results['generated_at'] = instant
    if zone:
        results['reporting_timezone'] = zone
    deck = Presentation(BytesIO(generate_deck('overview', 'dark', results)))
    footer = next(shape for shape in deck.slides[0].shapes if shape.name == 'stamp')
    assert footer.text == 'Records as of ' + expected


@pytest.mark.parametrize('theme', ('light', 'dark'))
@pytest.mark.parametrize('platform', ('powerpoint', 'google-slides'))
def test_assembly_exports_editable_dated_results_with_expected_motion(results, theme, platform):
    doc = generate_deck('assembly', theme, results, platform)
    opened = Presentation(BytesIO(doc))
    native = platform == 'powerpoint'
    expected_count = 9 if native else 6
    closing_index = expected_count - (2 if native else 1)
    overview_index = 1 if native else 0
    assert len(opened.slides) == expected_count
    assert str(opened.slides[0].background.fill.fore_color.rgb) == PALETTES[theme].paper
    with ZipFile(BytesIO(doc)) as archive:
        roots = [etree.fromstring(archive.read(f'ppt/slides/slide{i}.xml')) for i in range(1, expected_count + 1)]
    for index, root in enumerate(roots):
        transitions = root.xpath('p:transition | mc:AlternateContent/mc:Choice/p:transition', namespaces=NS)
        assert bool(transitions) == (platform == 'powerpoint')
        valid_ids = set(root.xpath('//p:cNvPr/@id', namespaces=NS))
        assert set(root.xpath('//p:spTgt/@spid', namespaces=NS)) <= valid_ids
        if native:
            if index not in (0, expected_count - 1):
                _slide_effects(opened.slides[index])
            assert root.find('.//p:cTn[@presetClass="entr"][@presetID="17"]', NS) is None  # Stretch
        else:
            assert root.find('p:timing', NS) is None
        if overview_index <= index < closing_index:
            expected_time = '08:00 EST' if platform == 'powerpoint' else '13:00 UTC'
            assert f'Records as of Nov 20, 2026 at {expected_time}' in root.xpath('//a:t/text()', namespaces=NS)
    for text in ('Community Lunch', 'Autumn Lunch', '+45', '+15%', 'Latest − previous'):
        assert text in roots[overview_index + 2].xpath('//a:t/text()', namespaces=NS)
    assert opened.slides[overview_index + 1]._element.cSld.get('name') == 'Community Lunch'
    ticks = {'Axis minimum', 'Axis midpoint', 'Axis maximum'}
    chart_names = {shape.name for shape in opened.slides[overview_index + 3].shapes}
    assert chart_names.isdisjoint(ticks) if platform == 'powerpoint' else ticks <= chart_names
    last_texts = roots[closing_index - 1].xpath('//a:t/text()', namespaces=NS)
    assert any('portion' in text.lower() for text in last_texts)
    assert any('plate' in text.lower() for text in last_texts)
    assert len(roots[closing_index - 1].xpath('//p:pic', namespaces=NS)) == 1  # Logo only.
    first, second = opened.slides[closing_index].shapes
    assert (first.text, second.text) == ('Be Green,', 'Do Good')
    # The authored 192px indent and 30px gap convert to PowerPoint points.
    assert second.left.pt - first.left.pt == pytest.approx(144, abs=.01)
    assert second.top.pt - first.top.pt - first.height.pt == pytest.approx(22.5, abs=.01)
    for line in (first, second):
        font = line.text_frame.paragraphs[0].runs[0].font
        assert font.size.pt == 115 and font.name == 'Newsreader'
        assert str(font.color.rgb) == ('946B20' if theme == 'light' else 'E8C780')
    overview = generate_deck('overview', theme, results, platform)
    assert len(Presentation(BytesIO(overview)).slides) == 1
    with ZipFile(BytesIO(overview)) as archive:
        if native:
            standalone = etree.fromstring(archive.read('ppt/slides/slide1.xml'))
            assert standalone.find('.//{http://schemas.microsoft.com/office/powerpoint/2015/09/main}morph') is None
            assert standalone.xpath('//a:t/text()', namespaces=NS) == roots[overview_index].xpath('//a:t/text()', namespaces=NS)
        else:
            assert archive.read('ppt/slides/slide1.xml') == etree.tostring(roots[0], encoding='UTF-8', xml_declaration=True, standalone=True)


@pytest.mark.parametrize('theme', ('light', 'dark'))
def test_session_wording_preserves_school_names_in_slides_and_notes(results, theme):
    results['previous']['name'] = 'Friday Lunch'
    results['latest']['name'] = 'Saturday Breakfast'
    deck = Presentation(BytesIO(generate_deck('assembly', theme, results)))
    table = deck.slides[3]
    assert table._element.cSld.get('name') == 'Session comparison'
    assert {shape.text for shape in table.shapes if shape.has_text_frame} >= {
        'Friday Lunch', 'Saturday Breakfast', 'Previous session', 'Latest session',
    }
    assert 'Previous session: Friday Lunch' in table.notes_slide.notes_text_frame.text
    assert 'Latest session: Saturday Breakfast' in table.notes_slide.notes_text_frame.text
    for slide in deck.slides:
        words = [slide._element.cSld.get('name'), slide.notes_slide.notes_text_frame.text]
        words.extend(shape.text for shape in slide.shapes if shape.has_text_frame)
        boilerplate = ' '.join(' '.join(words).split()).replace('Friday Lunch', '').replace('Saturday Breakfast', '')
        assert not re.search(r'\b(?:breakfast|lunch(?:es)?|dinner)\b', boilerplate, re.I)


def test_empty_and_first_result_are_distinguished(results):
    results.update(previous=None, change=None)
    results['latest'].update(name='Lunch & <Thursday>\x00', clean=1, student_clean=1, faculty_clean=0,
                             dirty=0, very_dirty=0, total=1, clean_percentage=100)
    results['totals'].update(clean=1, total=1, clean_percentage=100, session_count=1)
    deck = Presentation(BytesIO(generate_deck('assembly', 'light', results)))
    assert len(deck.slides) == 7
    assert deck.slides[-4]._element.cSld.get('name') == 'gp.winner'
    assert [line.text for line in deck.slides[-2].shapes] == ['Be Green,', 'Do Good']
    labels = {shape.name: ' '.join(shape.text.split()) for shape in deck.slides[1].shapes if shape.has_text_frame}
    assert labels['all_clean'] == '1 clean plate'
    assert labels['share'] == '100% of 1 recorded plate across 1 session'
    assert labels['latest_name'] == 'Lunch & <Thursday>'
    assert labels['latest_counts'] == '1 of 1 plate was clean'
    assert labels['change_heading'] == 'First recorded session'
    _assert_overview_column_timing(_slide_effects(deck.slides[1]), has_previous=False)
    for slide in list(deck.slides)[1:-1]:
        _slide_effects(slide)
    assert 'latest_change' not in labels and 'change_units' not in labels
    breakdown_counts = next(shape for shape in deck.slides[2].shapes if shape.name == 'latest_counts')
    assert ' '.join(breakdown_counts.text.split()) == '1 of 1 plate was clean'
    assert '1 of 1 plate was clean.' in deck.slides[1].notes_slide.notes_text_frame.text
    assert '1 of 1 recorded plate was clean.' in deck.slides[2].notes_slide.notes_text_frame.text
    results['latest'].update(clean=0, student_clean=0, dirty=10, total=10, clean_percentage=0)
    results['totals'].update(clean=0, total=10, clean_percentage=0)
    page = Presentation(BytesIO(generate_deck('overview', 'light', results))).slides[0]
    labels = {shape.name: ' '.join(shape.text.split()) for shape in page.shapes if shape.has_text_frame}
    assert labels['latest_rate'] == '0%' and labels['latest_counts'] == '0 of 10 plates were clean'
    results.update(latest=None, totals=dict(clean=0, total=0, clean_percentage=0, session_count=0))
    deck = Presentation(BytesIO(generate_deck('assembly', 'dark', results)))
    assert len(deck.slides) == 6
    assert deck.slides[-4]._element.cSld.get('name') == 'gp.winner'
    labels = {shape.name: shape.text for shape in deck.slides[1].shapes if shape.has_text_frame}
    assert labels['all_clean'] == '0 clean plates'
    assert labels['share'] == 'No plates recorded yet'
    assert labels['latest_name'] == 'No session results yet'
    assert not {'goal_label', 'progress_track', 'latest_date', 'latest_counts', 'rate_heading',
                'latest_rate', 'change_heading', 'latest_change', 'change_units'}.intersection(labels)
    for slide in list(deck.slides)[1:-1]:
        _slide_effects(slide)


def _slide_effects(slide):
    """Check navigation and index the native effects on each editable shape."""
    choice = slide._element.find('mc:AlternateContent/mc:Choice', NS)
    transition = choice.find('p:transition', NS)
    morph = transition.find('{http://schemas.microsoft.com/office/powerpoint/2015/09/main}morph')
    if morph is None:
        assert choice.get('Requires') == 'p14'
        assert transition.get('{%s}dur' % NS['p14']) == '250'
        assert transition.find('p:fade', NS) is not None
    else:
        assert morph.get('option') == 'byObject'
        assert transition.get('{%s}dur' % NS['p14']) == '850'
    fallback = slide._element.find('mc:AlternateContent/mc:Fallback/p:transition', NS)
    assert fallback.find('p:fade', NS) is not None
    for variant in (transition, fallback):
        assert variant.get('advClick', '1') == '1' and variant.get('advTm') is None

    timing = slide._element.find('p:timing', NS)
    fade_clocks = timing.findall('.//p:animEffect[@filter="fade"]/p:cBhvr/p:cTn', NS)
    assert {clock.get('dur') for clock in fade_clocks} == {'250'}
    main = timing.find('.//p:cTn[@nodeType="mainSeq"]', NS)
    trigger = main.find('p:childTnLst/p:par/p:cTn/p:stCondLst/p:cond[@evt="onBegin"]', NS)
    assert trigger.get('delay') == '0' and trigger.find('p:tn', NS).get('val') == main.get('id')
    names = {str(shape.shape_id): shape.name for shape in slide.shapes}
    breakdown = 'distribution' in names.values()
    steps = main.findall('p:childTnLst/p:par/p:cTn', NS)
    assert len(steps) == (5 if breakdown else 1)
    for step in steps[1:]:
        starts = step.findall('p:stCondLst/p:cond', NS)
        assert [(cond.get('evt'), cond.get('delay')) for cond in starts] == [(None, 'indefinite')]
    assert timing.find('.//p:cond[@evt="onClick"]', NS) is None
    assert timing.find('.//p:seq/p:nextCondLst/p:cond[@evt="onNext"]/p:tgtEl/p:sldTgt', NS) is not None
    ids = [node.get('id') for node in timing.findall('.//p:cTn', NS)]
    assert len(ids) == len(set(ids))

    effects = {}
    groups = set()
    allowed_types = {'clickEffect', 'withEffect', 'afterEffect'} if breakdown else {'withEffect'}
    for entry in timing.findall('.//p:cTn[@presetID]', NS):
        assert entry.get('nodeType') in allowed_types
        target, = {t.get('spid') for t in entry.findall('.//p:spTgt', NS)}
        shape_effects = effects.setdefault(names[target], {})
        kind = entry.get('presetClass')
        # A zero result can have a color emphasis and a separate scale emphasis.
        if kind != 'emph':
            assert kind not in shape_effects
        shape_effects.setdefault(kind, entry)
        groups.add((target, entry.get('grpId')))
    assert groups == {(b.get('spid'), b.get('grpId')) for b in timing.findall('p:bldLst/p:bldP', NS)}
    visible = {shape.name for shape in slide.shapes if shape.width and shape.height}
    static_windows = {'Progress meter window', 'Lunch distribution window', 'Previous lunch rate window',
                      'Latest lunch rate window'}
    carried_logo = {'!!Golden Plate mark', '!!Golden Plate wordmark'} if morph is not None else set()
    assert carried_logo.isdisjoint(effects)
    assert visible - static_windows - carried_logo <= effects.keys()
    assert static_windows.isdisjoint(effects)
    window_ids = {identifier for identifier, name in names.items() if name in static_windows}
    assert window_ids.isdisjoint(node.get('spid') for node in timing.findall('.//p:spTgt', NS))
    assert window_ids.isdisjoint(node.get('spid') for node in timing.findall('p:bldLst/*', NS))
    for window in (shape for shape in slide.shapes if shape.name in static_windows):
        assert window._element.find('p:nvSpPr/p:cNvPr', NS).get('hidden', '0') in ('0', 'false')
        assert window.fill.fore_color.rgb == slide.background.fill.fore_color.rgb
        alphas = window._element.findall('p:spPr/a:solidFill/*/a:alpha', NS)
        assert all(alpha.get('val') == '100000' for alpha in alphas)
    for entries in effects.values():
        # PowerPoint uses the first listed effect to pre-hide an entering object.
        assert next(iter(entries)) == 'entr'
        entrance = entries['entr']
        assert _effect_start(entrance) >= (0 if breakdown else 1)
        assert entrance.find('.//p:set/p:to/p:strVal[@val="visible"]', NS) is not None
        for entry in entries.values():
            assert _effect_start(entry) + _effect_duration(entry) <= 2600
    return effects


def _effect_start(entry):
    return int(entry.find('p:stCondLst/p:cond', NS).get('delay'))


def _effect_duration(entry):
    return max(int(clock.get('dur')) * (2 if clock.get('autoRev') == '1' else 1)
               for clock in entry.findall('.//p:cBhvr/p:cTn', NS))


def _path_offset(entry):
    """Return the starting offset of a reversed straight path in slide units."""
    motion = entry.find('.//p:animMotion', NS)
    assert entry.get('accel') == entry.get('decel') == '50000'
    assert motion.find('p:cBhvr/p:cTn', NS).get('spd') == '-100000'
    return tuple(map(float, motion.get('path').split('L')[1].strip().rstrip(' E').split()))


def _assert_position_only_fly(entrance, origin, duration):
    assert entrance.get('presetClass') == 'entr' and entrance.get('presetID') == '2'
    assert entrance.get('presetSubtype') == '8'
    assert entrance.get('accel') == entrance.get('decel') == '50000'
    assert entrance.find('.//p:animScale', NS) is None and entrance.find('.//p:animEffect', NS) is None
    axes = {}
    for animation in entrance.findall('.//p:anim', NS):
        assert animation.get('calcmode') == 'lin'
        behavior = animation.find('p:cBhvr', NS)
        assert behavior.get('additive') == 'base'
        prop = behavior.find('p:attrNameLst/p:attrName', NS).text
        keys = animation.findall('p:tavLst/p:tav', NS)
        assert [key.get('tm') for key in keys] == ['0', '100000']
        clock = behavior.find('p:cTn', NS)
        assert clock.get('dur') == str(duration) and clock.get('fill') == 'hold'
        axes[prop] = [key.find('p:val/p:strVal', NS).get('val') for key in keys]
    assert axes == {'ppt_x': [origin, '#ppt_x'], 'ppt_y': ['#ppt_y', '#ppt_y']}


def _normalized_effect_xml(entrance):
    """Compare the entire native effect, independent of the assigned shape, node IDs and start time."""
    effect = deepcopy(entrance)
    effect.find('p:stCondLst/p:cond', NS).set('delay', '0')
    for node in effect.iter('{%s}cTn' % NS['p']):
        node.set('id', '0')
    for target in effect.findall('.//p:spTgt', NS):
        target.set('spid', '0')
    return etree.tostring(effect, method='c14n', exclusive=True)


def _assert_reading_order(effects, *names):
    delays = [_effect_start(effects[name]['entr']) for name in names]
    assert all(earlier < later for earlier, later in zip(delays, delays[1:]))


def _assert_overview_column_timing(effects, *, has_previous):
    columns = [('latest_heading', 'latest_name', 'latest_date'), ('rate_heading', 'latest_rate', 'latest_counts'),
               ('change_heading', 'latest_change', 'change_units')]
    for column, names in enumerate(columns):
        for name, offset in zip(names, (0, 100, 290)):
            if not has_previous and name in ('latest_change', 'change_units'):
                assert name not in effects
                continue
            expected = 930 + column * 170 + offset
            entry = effects[name]
            assert entry['entr'].find('.//p:animEffect[@filter="fade"]', NS) is not None
            assert _effect_start(entry['entr']) == expected
            if 'path' in entry:
                assert _effect_start(entry['path']) == expected


@pytest.mark.parametrize('theme', ('light', 'dark'))
@pytest.mark.parametrize(('previous_rate', 'goal', 'change_text'), [
    (75, 200, '+15'), (95, 100, '−5'), (90, None, '0'),
])
def test_opening_follows_the_results_and_finishes_automatically(results, theme, previous_rate, goal, change_text):
    results['previous']['clean_percentage'] = previous_rate
    results['milestone'] = goal
    slide = Presentation(BytesIO(generate_deck('overview', theme, results))).slides[0]
    effects = _slide_effects(slide)
    assert 'Progress meter window' in {shape.name for shape in slide.shapes}
    base = 'Clean plates toward milestone' if goal else 'All-time clean plate share'
    order = ('all_clean', 'share', 'progress_track', base, 'Lunch detail rule', 'latest_name', 'stamp')
    _assert_reading_order(effects, *order)
    _assert_overview_column_timing(effects, has_previous=True)
    assert _effect_start(effects['latest_name']['entr']) < (
        _effect_start(effects[base]['entr']) + _effect_duration(effects[base]['entr']))
    for name in ('school', 'stamp'):
        assert effects[name].keys() == {'entr'}
        assert effects[name]['entr'].find('.//p:animEffect[@filter="fade"]', NS) is not None

    x, y = _path_offset(effects['all_clean']['path'])
    assert abs(x) < .0001 and y < 0  # The headline settles downward.
    for name in ('latest_name', 'latest_rate'):
        x, y = _path_offset(effects[name]['path'])
        assert x < 0 and abs(y) < .0001  # Follow the row left to right.
        assert effects[name]['entr'].find('.//p:animEffect[@filter="fade"]', NS) is not None

    fly = effects[base]['entr']
    _assert_position_only_fly(fly, '0-#ppt_w/2', 1150)
    if goal == 100:
        excess = effects['Clean plates above milestone']['entr']
        assert excess.get('presetID') == '2' and excess.get('accel') == excess.get('decel') == '50000'
        assert _effect_start(excess) == _effect_start(fly) + _effect_duration(fly)
        assert _effect_duration(excess) == 450
        positions = excess.xpath('./p:childTnLst/p:anim[p:cBhvr/p:attrNameLst/p:attrName="ppt_x"]'
                                 '/p:tavLst/p:tav/p:val/p:strVal/@val', namespaces=NS)
        assert positions == ['#ppt_x-#ppt_w', '#ppt_x']
        order = [shape.name for shape in slide.shapes]
        assert order.index('Clean plates above milestone') < order.index(base) < order.index('Progress meter window')

    change = effects['latest_change']
    fade = change['entr']
    assert next(shape.text for shape in slide.shapes if shape.name == 'latest_change') == change_text
    assert fade.find('.//p:animEffect[@filter="fade"]', NS) is not None
    if change_text == '0':
        assert change.keys() == {'entr'}
        assert _effect_duration(fade) == 250
    else:
        travel = change['path']
        lunch = effects['latest_name']
        assert _path_offset(travel) == _path_offset(lunch['path']) == (-.012, 0)
        assert _effect_duration(travel) == _effect_duration(lunch['path']) == 410
        assert _effect_duration(fade) == _effect_duration(lunch['entr']) == 250
        assert _effect_start(travel) == _effect_start(fade)


def test_body_slides_build_their_own_reading_order(results):
    deck = Presentation(BytesIO(generate_deck('assembly', 'dark', results)))
    lunch, table, chart, winner, reminders, closing = [_slide_effects(page) for page in list(deck.slides)[2:-1]]
    _assert_reading_order(winner, 'winner_title', 'winner_detail', 'winner_role_student', 'winner_name_student')
    _assert_reading_order(lunch, 'title', 'latest_name', 'rate', 'distribution')
    _assert_reading_order(table, 'title', 'prev_name', 'prev_clean', 'prev_total', 'prev_rate')
    for metric in ('clean', 'total', 'rate'):
        _assert_reading_order(table, 'prev_' + metric, 'curr_' + metric, 'delta_' + metric)
    _assert_reading_order(chart, 'title', 'prev_fill', 'curr_fill', 'rate_comparison')
    for name in ('prev_fill', 'curr_fill'):
        _assert_position_only_fly(chart[name]['entr'], '0-#ppt_w/2', 1150)
    _assert_reading_order(reminders, 'title', 'Portion choice', 'Dish return rule', 'Plate count')
    shape_by_name = {shape.name: shape for shape in deck.slides[-3].shapes}
    for name, paragraphs in [('Portion choice', 2), ('Plate count', 3)]:
        assert len(shape_by_name[name].text_frame.paragraphs) == paragraphs
        assert reminders[name].keys() == {'entr', 'path'}
        for effect in reminders[name].values():
            assert effect.find('.//p:spTgt/p:txEl', NS) is None
    _assert_reading_order(closing, 'Be Green', 'Do Good')
    first = closing['Be Green']['entr']
    second = closing['Do Good']['entr']
    assert _effect_start(first) + _effect_duration(first) < _effect_start(second)
    for effects, names, direction in (
        (lunch, ('latest_name',), (0, -1)),
        (table, ('delta_clean', 'delta_total', 'delta_rate'), (-1, 0)),
        (chart, ('rate_comparison',), (0, 1)),
        (reminders, ('Portion choice', 'Plate count'), (-1, 0)),
        (closing, ('Be Green',), (0, -1)),
        (closing, ('Do Good',), (-1, 0)),
    ):
        for name in names:
            offset = _path_offset(effects[name]['path'])
            assert tuple((axis > 0) - (axis < 0) for axis in offset) == direction
            assert _effect_start(effects[name]['path']) == _effect_start(effects[name]['entr'])


@pytest.mark.parametrize(('winners', 'heading'), [
    ({}, 'Golden Plate winner'),
    ({'student': 'Riley Chen'}, 'Golden Plate winner'),
    ({'faculty': 'Morgan Ellis'}, 'Golden Plate winner'),
    ({'student': 'Riley Chen', 'faculty': 'Morgan Ellis'}, 'Golden Plate winners'),
])
def test_winner_announcement_binds_recipient_and_photo_roles_separately(results, winners, heading):
    results['winner_names'] = winners
    deck = Presentation(BytesIO(generate_deck('assembly', 'dark', results)))
    slide = deck.slides[-4]
    assert slide._element.cSld.get('name') == 'gp.winner'
    assert slide.slide_layout.name == slide.slide_layout._element.get('matchingName') == 'gp.winner'
    assert slide.slide_layout.part in {layout.part for layout in deck.slide_master.slide_layouts}
    assert slide.slide_layout.slide_master.part == deck.slide_master.part
    assert slide._element.get('show', '1') == '1'
    shapes = {s.name: s for s in slide.shapes}
    assert shapes['winner_title'].text == heading and shapes['winner_detail'].text == 'Congratulations!'
    for role in ('student', 'faculty'):
        assert shapes['winner_name_' + role].text == winners.get(role, '')
        assert shapes['winner_role_' + role].text == (role.title() + ' winner' if role in winners else '')
    assert {ph.placeholder_format.idx for ph in slide.placeholders} == {21, 22}
    for slot, role, side in ((21, 'student', 'left'), (22, 'faculty', 'right')):
        photo = slide.placeholders[slot]
        assert photo.name == 'gp.winner.photo.' + side
        assert photo.placeholder_format.type == PP_PLACEHOLDER.PICTURE
        assert photo._element.nvSpPr.cNvPr.get('descr') == role.title() + ' winner photo'
        assert not photo._element.xpath('.//a:blip') and not photo._element.xpath('p:spPr/a:xfrm')
        layout_photo = next(ph for ph in slide.slide_layout.placeholders if ph.placeholder_format.idx == slot)
        assert layout_photo._element.xpath('p:spPr/a:xfrm')
        assert (photo.width, photo.height) == (layout_photo.width, layout_photo.height)
        assert photo.width * 5 == photo.height * 4
    left, right = slide.placeholders[21], slide.placeholders[22]
    student, faculty = shapes['winner_name_student'], shapes['winner_name_faculty']
    if len(winners) == 1:
        role = next(iter(winners))
        for field in ('winner_name_', 'winner_role_', 'winner_stats_'):
            shape = shapes[field + role]
            assert 2 * shape.left + shape.width == deck.slide_width
            assert left.left + left.width < shape.left < shape.left + shape.width < right.left
    else:
        assert left.left + left.width < student.left < student.left + student.width < faculty.left
        assert faculty.left + faculty.width < right.left
    # Pasting into either role must retain its native placeholder identity/crop
    # and its entrance target. The logo provides a small square test image.
    source = shapes['Plate mark'].image.blob
    for slot in (21, 22):
        ph = slide.placeholders[slot]
        shape_id = ph.shape_id
        photo = ph.insert_picture(BytesIO(source))
        assert photo.placeholder_format.idx == slot and photo.shape_id == shape_id
        assert photo.crop_left == pytest.approx(photo.crop_right) and photo.crop_left > 0
        assert photo.crop_top == photo.crop_bottom == 0
    saved = BytesIO()
    deck.save(saved)
    reopened = Presentation(BytesIO(saved.getvalue())).slides[-4]
    for slot in (21, 22):
        photo = reopened.placeholders[slot]
        assert photo.image.blob == source and photo._element.xpath('p:nvPicPr/p:nvPr/p:ph')


@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_winner_draw_details_fit_and_follow_the_recorded_selection(results, theme):
    results['winner_names'] = {'student': 'María de los Ángeles Sáenz de Santa Coloma',
                               'faculty': 'Morgan Ellis'}
    results['winner_details'] = {
        'student': {'tickets': 4.5, 'next_ticket_gain': 1.25, 'probability': 12.5, 'pool_size': 18, 'method': 'random',
                    'grade': 10, 'house': 'Maple House', 'clan': 'Owl'},
        'faculty': {'tickets': 1, 'next_ticket_gain': 1, 'probability': 0, 'pool_size': 12, 'method': 'manual',
                    'house': 'A long historical house name ' * 10},
    }
    deck = Presentation(BytesIO(generate_deck('assembly', theme, results)))
    winner = deck.slides[-4]
    shapes = {shape.name: shape for shape in winner.shapes}
    effects = _slide_effects(winner)
    for role, lines in [('student', ['4.5 tickets at draw · 12.50% chance', 'Next clean plate: +1.25 tickets',
                                      '18 eligible students · Random draw',
                                      'Grade 10 · Maple House · Owl Clan']),
                        ('faculty', ['1 ticket at draw · 0.00% pool share', 'Next clean plate: +1 ticket',
                                     '12 eligible faculty · Manual selection'])]:
        key = 'winner_stats_' + role
        stats, recipient = shapes[key], shapes['winner_name_' + role]
        assert stats.text.splitlines() == lines
        assert ' '.join(recipient.text.splitlines()) == results['winner_names'][role]
        assert stats.left == recipient.left and stats.width == recipient.width
        last_line = sum(p.line_spacing for p in recipient.text_frame.paragraphs)
        assert stats.top > recipient.top + last_line
        assert sum(p.line_spacing for p in stats.text_frame.paragraphs) <= stats.height + 1
        assert stats.top + stats.height < shapes['stamp'].top
        assert all(p.runs[0].font.name == 'Georgia' for p in stats.text_frame.paragraphs)
        _assert_reading_order(effects, 'winner_name_' + role, key, 'stamp')
        assert set(effects[key]) == {'entr'} and _effect_duration(effects[key]['entr']) == 250

    # A missing snapshot, invalid field, or unnamed recipient must not produce
    # a zero-valued metric, and an unusually long optional label may be omitted.
    results['winner_names'].pop('student')
    results['winner_details']['faculty'] = {'tickets': None, 'next_ticket_gain': -1, 'probability': 112, 'pool_size': -1}
    bare = Presentation(BytesIO(generate_deck('assembly', theme, results))).slides[-4]
    assert all(not shape.text for shape in bare.shapes if shape.name.startswith('winner_stats_'))
    results['winner_details']['faculty'] = {'tickets': 0, 'pool_size': 1}
    single = Presentation(BytesIO(generate_deck('assembly', theme, results))).slides[-4]
    stats = next(shape for shape in single.shapes if shape.name == 'winner_stats_faculty')
    assert stats.text == '0 tickets at draw\n1 eligible faculty member'
    assert 2 * stats.left + stats.width == deck.slide_width
    results['winner_details']['faculty'] = {'tickets': 8, 'next_ticket_gain': 0}
    page = Presentation(BytesIO(generate_deck('assembly', theme, results))).slides[-4]
    assert next(s.text for s in page.shapes if s.name == 'winner_stats_faculty') == (
        '8 tickets at draw\nNext clean plate: +0 tickets')


@pytest.mark.parametrize('custom', [False, True])
def test_full_school_or_custom_label_fits_masthead_on_every_results_slide(results, custom):
    long_name = ('École internationale des sciences et des arts de la communauté de la vallée du Saint-Laurent '
                 'et du Centre régional des programmes bilingues pour les élèves du secondaire')
    actual_name = 'Aurora School' if custom else long_name
    results.update(school_name=actual_name, school_label=long_name if custom else None)
    deck = Presentation(BytesIO(generate_deck('assembly', 'dark', results)))
    for slide in list(deck.slides)[1:-2]:
        shapes = {shape.name: shape for shape in slide.shapes}
        label = shapes['school']
        assert ' '.join(label.text.splitlines()) == long_name
        assert len(label.text.splitlines()) > 1
        assert label.top >= 0 and label.top + label.height < shapes['Masthead rule'].top
        publisher = shapes.get('!!Golden Plate wordmark') or shapes['Publisher']
        assert label.left >= publisher.left + publisher.width
        assert actual_name in slide.notes_slide.notes_text_frame.text


@pytest.mark.parametrize(('clean', 'goal_text', 'goal_width', 'extra_width'), [
    (0, '100 to the 100-plate goal', 0, 0),
    (50, '50 to the 100-plate goal', 199, 0),
    (100, '100-plate goal reached', 398, 0),
    (200, '100 above the 100-plate goal', 199, 199),
])
def test_overview_displays_school_count_milestone_and_recorded_share(results, clean, goal_text, goal_width, extra_width):
    results.update(milestone=100, totals=dict(clean=clean, total=clean * 2, clean_percentage=50 if clean else 0,
                                              session_count=2 if clean else 0))
    deck = Presentation(BytesIO(generate_deck('assembly', 'dark', results)))
    page = deck.slides[1]
    if clean == 0:
        entrances = _slide_effects(page)
        assert 'progress_track' in entrances and 'Clean plates toward milestone' not in entrances
    labels = [' '.join(shape.text.split()) for shape in page.shapes if shape.has_text_frame]
    assert goal_text in labels
    assert (f'50% of {clean * 2} recorded plates across 2 sessions' if clean else 'No plates recorded yet') in labels
    widths = {shape.name: shape.width.pt for shape in page.shapes}
    # Chromium quantizes CSS layout to 1/64 pixel when compiling the source.
    browser_unit_pt = .75 / 64
    assert widths['progress_track'] == pytest.approx(398, abs=browser_unit_pt)
    assert widths.get('Clean plates toward milestone', 0) == pytest.approx(goal_width, abs=browser_unit_pt)
    assert widths.get('Clean plates above milestone', 0) == pytest.approx(extra_width, abs=browser_unit_pt)
    fills = {shape.name: str(shape.fill.fore_color.rgb) for shape in page.shapes
             if shape.name in ('Clean plates toward milestone', 'Clean plates above milestone')}
    if goal_width:
        swatch = next(shape for shape in deck.slides[2].shapes if shape.name == 'Student clean plates key')
        assert fills['Clean plates toward milestone'] == str(swatch.fill.fore_color.rgb)
    if extra_width:
        change = next(shape for shape in page.shapes if shape.name == 'latest_change')
        assert fills['Clean plates above milestone'] == str(change.text_frame.paragraphs[0].runs[0].font.color.rgb)


@pytest.mark.parametrize('theme', ['light', 'dark'])
@pytest.mark.parametrize('platform', ['powerpoint', 'google-slides'])
def test_rounded_progress_window_belongs_only_to_the_animated_meter(results, theme, platform):
    results['milestone'] = 200
    page = Presentation(BytesIO(generate_deck('overview', theme, results, platform))).slides[0]
    shapes = {shape.name: shape for shape in page.shapes}
    track = shapes['progress_track']
    fill = shapes['Clean plates toward milestone']
    assert track.adjustments[0] == pytest.approx(.4)
    assert fill.adjustments[0] == track.adjustments[0]
    assert (fill.left, fill.top, fill.height) == (track.left, track.top, track.height)
    assert fill.width == pytest.approx(track.width * results['totals']['clean'] / 200, abs=1)
    if platform == 'powerpoint':
        window = shapes['Progress meter window']
        assert list(shapes).index(fill.name) < list(shapes).index(window.name)
        assert 0 == window.left < track.left
        assert window.left + window.width >= track.left + track.width
        assert len(window._element.xpath('p:spPr/a:custGeom/a:pathLst/a:path/a:moveTo')) == 2
        assert window.fill.fore_color.rgb == page.background.fill.fore_color.rgb
    else:
        assert 'Progress meter window' not in shapes


def test_cover_preserves_the_single_line_total_and_labels_the_rate_change(results):
    clean = 9_223_372_036_854_775_807
    results['totals'].update(clean=clean, total=clean, clean_percentage=100)
    results['previous'].update(clean=91, total=100, clean_percentage=91)
    page = Presentation(BytesIO(generate_deck('overview', 'light', results, 'google-slides'))).slides[0]
    shapes = {shape.name: shape for shape in page.shapes}
    assert shapes['all_clean'].text == f'{clean:,} clean plates'
    assert f'{clean:,} clean plates' in page.notes_slide.notes_text_frame.text
    assert ' '.join(shapes['goal_label'].text.split()) == 'Share of plates returned clean'
    assert str(shapes['All-time clean plate share'].fill.fore_color.rgb) == PALETTES['light'].fill
    assert shapes['latest_heading'].text == 'Latest session'
    assert ' '.join(shapes['rate_heading'].text.split()) == 'Clean-plate rate'
    assert shapes['latest_rate'].text == '90%'
    assert ' '.join(shapes['latest_counts'].text.split()) == '90 of 100 plates were clean'
    assert ' '.join(shapes['change_heading'].text.split()) == 'Change from previous session'
    assert shapes['latest_change'].text == '−1' and shapes['change_units'].text == 'percentage point'


@pytest.mark.parametrize('theme', ('light', 'dark'))
def test_printable_results_as_pdf(results, theme):
    for kind, pages in [('assembly', 6), ('overview', 1)]:
        pdf = generate_deck(kind, theme, results, 'pdf')
        assert pdf.startswith(b'%PDF-')
        assert b'/Count ' + str(pages).encode() + b' ' in pdf


@pytest.mark.parametrize('theme', ('light', 'dark'))
@pytest.mark.parametrize('platform', ('powerpoint', 'google-slides'))
def test_latest_lunch_chart_and_legend_follow_the_school_snapshot(results, theme, platform):
    latest = results['latest']
    latest.update(student_clean=6, faculty_clean=0, dirty=3, very_dirty=1,
                  total=10, clean=6, clean_percentage=60)
    deck = Presentation(BytesIO(generate_deck('assembly', theme, results, platform)))
    lunch = deck.slides[2 if platform == 'powerpoint' else 1]
    shapes = {shape.name: shape for shape in lunch.shapes}
    assert shapes['latest_counts'].text == '6 of 10 plates were clean'
    assert shapes['rate'].text == '60%'
    assert shapes['faculty_clean'].text == '0'
    assert 'Faculty clean plates share' not in shapes
    track = shapes['distribution']
    effects = _slide_effects(lunch) if platform == 'powerpoint' else {}
    left = track.left
    for label, fraction in [('Student clean plates', .6), ('Dirty plates', .3), ('Very dirty plates', .1)]:
        segment = shapes[label + ' share']
        assert segment.left == pytest.approx(left, abs=1)
        assert segment.width == pytest.approx(track.width * fraction, abs=1)
        assert segment.fill.fore_color.rgb == shapes[label + ' key'].fill.fore_color.rgb
        if effects:
            entrance = effects[segment.name]['entr']
            _assert_position_only_fly(entrance, '#ppt_x-#ppt_w', 540)
        left = segment.left + segment.width
    assert left == pytest.approx(track.left + track.width, abs=1)
    assert ('Lunch distribution window' in shapes) == (platform == 'powerpoint')


def _assert_rounded_window(window, track):
    assert track._element.find('p:spPr/a:prstGeom', NS).get('prst') == 'roundRect'
    assert track.adjustments[0] == pytest.approx(.4)
    assert window.left == 0 and window.left + window.width >= track.left + track.width
    assert window.top < track.top and window.top + window.height > track.top + track.height
    path, = window._element.xpath('p:spPr/a:custGeom/a:pathLst/a:path')
    commands = [etree.QName(cmd).localname for cmd in path]
    assert commands[:5] == ['moveTo', 'lnTo', 'lnTo', 'lnTo', 'close']
    assert commands[5] == 'moveTo' and commands[-1] == 'close' and set(commands[6:-1]) == {'lnTo'}

    def points(contour):
        return [(round(window.left + int(cmd[0].get('x')) * window.width / int(path.get('w'))),
                 round(window.top + int(cmd[0].get('y')) * window.height / int(path.get('h'))))
                for cmd in contour]

    def signed_area(contour):
        return sum(x * ny - nx * y for (x, y), (nx, ny) in zip(contour, contour[1:] + contour[:1]))

    outer, inner = points(path[:4]), points(path[5:-1])
    assert signed_area(outer) * signed_area(inner) < 0  # The opposite winding cuts the track out of the paper.
    assert len(inner) >= 16
    left, right, top, bottom = track.left, track.left + track.width, track.top, track.top + track.height
    xs, ys = zip(*inner)
    assert (min(xs), max(xs), min(ys), max(ys)) == pytest.approx((left, right, top, bottom), abs=2)
    radius = track.height * .4
    for x, y in inner:
        # The boundary is one radius away from the track's inset rectangle.
        dx = max(left + radius - x, x - right + radius, 0)
        dy = max(top + radius - y, y - bottom + radius, 0)
        assert (dx ** 2 + dy ** 2) ** .5 == pytest.approx(radius, abs=2)


def _assert_distribution_clip(slide, shapes, category_names):
    track = shapes['distribution']
    segments = [shapes[name] for name in category_names if name in shapes]
    assert not any(name.endswith(' progress tip') for name in shapes)
    for shape in segments:
        assert shape._element.find('p:spPr/a:prstGeom', NS).get('prst') == 'rect'
        assert (shape.top, shape.height) == (track.top, track.height)
    window = shapes['Lunch distribution window']
    _assert_rounded_window(window, track)
    assert window.width == slide.part.package.presentation_part.presentation.slide_width
    z_order = list(shapes)
    layer = [track, *reversed(segments), window]
    assert [z_order.index(shape.name) for shape in layer] == sorted(z_order.index(shape.name) for shape in layer)
    assert all(z_order.index(window.name) < z_order.index(name) for name in z_order if name.endswith(' zero marker'))


@pytest.mark.parametrize('theme', ('light', 'dark'))
@pytest.mark.parametrize('counts', [(85, 5, 8, 2), (7000, 1, 2000, 999), (70, 0, 0, 30), (0, 1, 0, 9),
                                    (0, 0, 12, 0), (94, 6, 0, 0), (0, 0, 0, 0)])
def test_lunch_advances_one_category_per_click(results, theme, counts):
    categories = [('student_clean', 'Student clean plates'), ('faculty_clean', 'Faculty clean plates'),
                  ('dirty', 'Dirty plates'), ('very_dirty', 'Very dirty plates')]
    total = sum(counts)
    clean = sum(counts[:2])
    latest = results['latest']
    latest.update({key: value for (key, _), value in zip(categories, counts)})
    latest.update(total=total, clean=clean, clean_percentage=100 * clean / total if total else None)
    page = Presentation(BytesIO(generate_deck('assembly', theme, results))).slides[2]
    effects = _slide_effects(page)
    shapes = {shape.name: shape for shape in page.shapes}
    _assert_distribution_clip(page, shapes, [label + ' share' for _, label in categories])
    names = {str(shape.shape_id): shape.name for shape in page.shapes}
    steps = page._element.find('.//p:cTn[@nodeType="mainSeq"]', NS).findall('p:childTnLst/p:par/p:cTn', NS)

    def targets(step):
        return {names[target.get('spid')] for target in step.findall('.//p:spTgt', NS)}

    assert targets(steps[0]) == {'Plate mark', 'Publisher', 'school', 'Masthead rule', 'title', 'latest_name',
                                 'latest_date', 'rate', 'latest_counts', 'distribution', 'stamp'}
    for index, ((key, label), count, step) in enumerate(zip(categories, counts, steps[1:])):
        step_effects = step.findall('.//p:cTn[@presetID]', NS)
        assert [effect.get('nodeType') for effect in step_effects].count('clickEffect') == 1
        assert step_effects[0].get('nodeType') == 'clickEffect'
        seen = targets(step)
        assert {key, label + ' label', label + ' key'} <= seen
        assert all(seen.isdisjoint(targets(other)) for other in steps if other is not step)
        assert shapes[key].text == f'{count:,}'
        share_name = label + ' share'
        if count:
            assert effects[share_name].keys() == {'entr'}
            _assert_position_only_fly(effects[share_name]['entr'], '#ppt_x-#ppt_w', 540)
            assert share_name in seen
            if count == total:
                assert shapes[share_name].width == shapes['distribution'].width
        else:
            assert share_name not in shapes
        rolls = sorted(name for name in seen if name.startswith(key + ' roll '))
        assert rolls == [key + ' roll ' + str(frame) for frame in range(1, 5)]
        assert len({shapes[name].text for name in [*rolls, key]}) == 5
        for name in rolls:
            assert len(shapes[name].text.replace(',', '')) == len(str(count))
            assert shapes[name].text_frame.paragraphs[0].runs[0].font.color.rgb == page.background.fill.fore_color.rgb
            assert effects[name]['exit'].find('.//p:set/p:to/p:strVal[@val="hidden"]', NS) is not None
            y_axis = effects[name]['entr'].find('.//p:anim/p:cBhvr/p:attrNameLst/p:attrName', NS)
            assert y_axis.text == 'ppt_y'
        starts = [_effect_start(effects[name]['entr']) for name in rolls] + [_effect_start(effects[key]['entr'])]
        assert all(first < second for first, second in zip(starts, starts[1:]))
        assert [_effect_start(effects[name]['exit']) for name in rolls] == starts[1:]
        marker = label + ' zero marker'
        if key in ('dirty', 'very_dirty') and count == 0 and total > 0:
            assert marker in seen
            track = shapes['distribution']
            expected_edge = track.left + track.width * sum(counts[:index]) / total
            assert shapes[marker].left + shapes[marker].width / 2 == pytest.approx(expected_edge, abs=2)
            assert shapes[marker].top + shapes[marker].height == track.top
            assert shapes[marker].fill.fore_color.rgb == page.background.fill.fore_color.rgb
            main_ink = str(shapes['student_clean'].text_frame.paragraphs[0].runs[0].font.color.rgb)
            ink = 'FFFFFF' if theme == 'dark' else main_ink
            _assert_zero_lands_then_pulses(step_effects, shapes[key], shapes[marker], effects[key], ink)
            paint = effects[marker]['entr'].find('.//p:animClr/p:to/a:srgbClr', NS)
            assert paint.get('val') == str(shapes[key].text_frame.paragraphs[0].runs[0].font.color.rgb)
        else:
            assert marker not in shapes
            assert all(e.find('.//p:animScale', NS) is None for e in step_effects)


def _assert_zero_lands_then_pulses(step_effects, number, marker, number_effects, ink):
    def action_for(shape, tag):
        target = str(shape.shape_id)
        action, = [(entry, action) for entry in step_effects if entry.get('presetClass') == 'emph'
                   for action in entry.findall('.//p:' + tag, NS)
                   if action.find('p:cBhvr/p:tgtEl/p:spTgt', NS).get('spid') == target]
        return action

    landing = max(_effect_start(number_effects[kind]) + _effect_duration(number_effects[kind])
                  for kind in ('entr', 'path'))
    gold = str(number.text_frame.paragraphs[0].runs[0].font.color.rgb)
    arrival = number_effects['entr'].find('.//p:animClr/p:to/a:srgbClr', NS)
    assert arrival.get('val') == ink and ink != gold
    shift, color = action_for(number, 'animClr')
    assert color.find('p:from/a:srgbClr', NS).get('val') == arrival.get('val')
    assert color.find('p:to/a:srgbClr', NS).get('val') == gold
    assert color.find('p:cBhvr/p:cTn', NS).get('fill') == 'hold'
    assert _effect_start(shift) - landing >= 180
    for shape in (number, marker):
        pulse, scale = action_for(shape, 'animScale')
        assert _effect_start(pulse) >= _effect_start(shift) + _effect_duration(shift)
        assert scale.find('p:cBhvr/p:cTn', NS).get('autoRev') == '1'
        assert scale.find('p:from', NS).get('x') == scale.find('p:from', NS).get('y') == '100000'
        tip_scale = scale.find('p:to', NS)
        assert int(tip_scale.get('x')) == int(tip_scale.get('y')) > 100000
    pulse_end = _effect_start(pulse) + _effect_duration(pulse)
    exit_time, = [entry for entry in step_effects if entry.get('presetClass') == 'exit'
                  and entry.find('.//p:spTgt', NS).get('spid') == str(marker.shape_id)]
    assert _effect_start(exit_time) >= pulse_end
    assert exit_time.find('.//p:set/p:to/p:strVal[@val="hidden"]', NS) is not None
    assert 'exit' not in number_effects


@pytest.mark.parametrize('theme', ('light', 'dark'))
@pytest.mark.parametrize(('dirty', 'very_dirty', 'clean'), [(0, 3, 7), (2, 0, 8), (0, 0, 10), (0, 0, 0)])
def test_powerpoint_highlights_each_recorded_zero_dirty_count(results, theme, dirty, very_dirty, clean):
    total = clean + dirty + very_dirty
    results['latest'].update(dirty=dirty, very_dirty=very_dirty, student_clean=clean, faculty_clean=0,
                             clean=clean, total=total, clean_percentage=100 * clean / total if total else None)
    for platform in ('google-slides', 'powerpoint'):
        deck = Presentation(BytesIO(generate_deck('assembly', theme, results, platform)))
        lunch = deck.slides[2 if platform == 'powerpoint' else 1]
        shapes = {shape.name: shape for shape in lunch.shapes}
        colors = {name: shape.text_frame.paragraphs[0].runs[0].font.color.rgb for name, shape in shapes.items()
                  if shape.has_text_frame and shape.text}
        closing = deck.slides[-2 if platform == 'powerpoint' else -1]
        gold = closing.shapes[0].text_frame.paragraphs[0].runs[0].font.color.rgb
        assert colors['faculty_clean'] == colors['student_clean'] != gold
        assert colors['Faculty clean plates label'] != gold
        for key, label, count in [('dirty', 'Dirty plates', dirty), ('very_dirty', 'Very dirty plates', very_dirty)]:
            highlighted = platform == 'powerpoint' and total > 0 and count == 0
            assert shapes[key].text == str(count)
            assert colors[key] == (gold if highlighted else colors['student_clean'])
            assert colors[label + ' label'] == (gold if highlighted else colors['Faculty clean plates label'])
            assert shapes[label + ' key'].fill.fore_color.rgb != gold


@pytest.mark.parametrize('theme', ('light', 'dark'))
@pytest.mark.parametrize(('previous_rate', 'latest_rate', 'change', 'summary'), [
    (0, 100, '+100%', '100 percentage points higher'),
    (100, 0, '−100%', '100 percentage points lower'),
    (75.2, 74.2, '−1%', '1 percentage point lower'),
    (50, 51, '+1%', '1 percentage point higher'),
    (72.4, 74.1, '+1.7%', '1.7 percentage points higher'),
    (12.5, 12.5, '0%', 'No change in clean-plate rate'),
])
def test_comparison_chart_uses_a_fixed_scale_and_absolute_point_difference(
        results, theme, previous_rate, latest_rate, change, summary):
    for key, rate in [('previous', previous_rate), ('latest', latest_rate)]:
        clean = round(10 * rate)
        results[key].update(clean_percentage=rate, total=1000, clean=clean, student_clean=clean,
                            faculty_clean=0, dirty=1000 - clean, very_dirty=0)
    deck = Presentation(BytesIO(generate_deck('assembly', theme, results)))
    table = {shape.name: shape for shape in deck.slides[3].shapes}
    opening_fly = _slide_effects(deck.slides[1])['All-time clean plate share']['entr']
    chart_effects = _slide_effects(deck.slides[4])
    chart = {shape.name: shape for shape in deck.slides[4].shapes}
    assert table['delta_rate'].text == change
    assert ' '.join(chart['rate_comparison'].text.split()) == summary
    assert chart['prev_track'].left == chart['curr_track'].left
    assert chart['prev_track'].width == chart['curr_track'].width
    for prefix, rate, session in [('prev', previous_rate, results['previous']), ('curr', latest_rate, results['latest'])]:
        track, fill = chart[prefix + '_track'], chart[prefix + '_fill']
        window = chart['Previous lunch rate window' if prefix == 'prev' else 'Latest lunch rate window']
        _assert_rounded_window(window, track)
        z_order = list(chart)
        assert z_order.index(track.name) < z_order.index(fill.name) < z_order.index(window.name)
        assert all(z_order.index(window.name) < z_order.index(name) for name, shape in chart.items()
                   if shape.has_text_frame and shape.text)

        assert fill.left == track.left
        assert fill.width == pytest.approx(track.width * rate / 100, abs=1)
        entrance = chart_effects[fill.name]['entr']
        if rate == 0:
            assert entrance.find('.//p:anim', NS) is None
        else:
            assert fill.adjustments[0] == pytest.approx(.4)
            _assert_position_only_fly(entrance, '0-#ppt_w/2', 1150)
            assert _normalized_effect_xml(entrance) == _normalized_effect_xml(opening_fly)
            assert chart_effects[fill.name].keys() == {'entr'}
        assert chart[prefix + '_rate'].text == f'{rate:g}%'
        assert chart[prefix + '_name'].text == session['name']
        assert chart[prefix + '_counts'].text == f"{session['clean']:,} of 1,000 plates were clean"
    assert {'Axis minimum', 'Axis midpoint', 'Axis maximum'}.isdisjoint(chart)
    assert summary in deck.slides[4].notes_slide.notes_text_frame.text


def test_missing_or_invalid_rates_use_actual_counts_and_missing_result_is_explicit(results):
    results.pop('change')
    del results['previous']['clean_percentage']
    results['latest']['clean_percentage'] = -3
    deck = Presentation(BytesIO(generate_deck('assembly', 'dark', results)))
    chart = {shape.name: shape for shape in deck.slides[4].shapes}
    assert chart['prev_rate'].text == '75%' and chart['curr_rate'].text == '90%'
    assert chart['rate_comparison'].text == '15 percentage points higher'
    results['previous'].update(clean=0, total=0)
    deck = Presentation(BytesIO(generate_deck('assembly', 'dark', results)))
    chart = {shape.name: shape for shape in deck.slides[4].shapes}
    _assert_rounded_window(chart['Previous lunch rate window'], chart['prev_track'])
    assert 'prev_fill' not in _slide_effects(deck.slides[4])
    assert 'prev_fill' not in chart and chart['prev_rate'].text == '—'
    assert chart['rate_comparison'].text == 'Rate comparison unavailable'


@pytest.mark.parametrize('platform', ('powerpoint', 'google-slides'))
@pytest.mark.parametrize('theme', ('light', 'dark'))
def test_editable_exports_use_native_georgia_and_embed_the_open_fonts(results, platform, theme):
    deck = Presentation(BytesIO(generate_deck('assembly', theme, results, platform)))
    runs = [run for slide in deck.slides for shape in slide.shapes if shape.has_text_frame
            for paragraph in shape.text_frame.paragraphs for run in paragraph.runs]
    assert {run.font.name for run in runs} == {'Newsreader', 'Georgia'}
    assert {run.font.bold for run in runs if run.font.name == 'Georgia'} == {False, True}
    content_slides = list(deck.slides)[1:] if platform == 'powerpoint' else list(deck.slides)
    italic = [(page, shape.name, run.font.name, run.font.bold)
              for page, slide in enumerate(content_slides, start=1) for shape in slide.shapes if shape.has_text_frame
              for paragraph in shape.text_frame.paragraphs for run in paragraph.runs if run.font.italic]
    assert italic == [(1, 'latest_date', 'Georgia', False), (2, 'latest_date', 'Georgia', False),
                      (3, 'prev_date', 'Georgia', False), (3, 'curr_date', 'Georgia', False)]
    for page, name in [(0, 'goal_label'), (3, 'rate_comparison')]:
        shape = next(shape for shape in content_slides[page].shapes if shape.name == name)
        assert shape.text_frame.paragraphs[0].runs[0].font.bold
    expected = {'Newsreader': {'regular'}}
    embedded = deck._element.xpath('p:embeddedFontLst/p:embeddedFont')
    assert {face[0].get('typeface') for face in embedded} == set(expected)
    for face in embedded:
        family = face[0].get('typeface')
        assert {etree.QName(entry).localname for entry in face[1:]} == expected[family]
        for weight in expected[family]:
            rel_id, = face.xpath(f'p:{weight}/@r:id', namespaces=face.nsmap)
            font = deck.part.related_part(rel_id)
            assert font.content_type == 'application/x-fontdata'
            assert font.blob[34:36] == b'LP'  # EOT signature
            size = int.from_bytes(font.blob[4:8], 'little')
            assert font.blob[-size:][:4] == b'\x00\x01\x00\x00'  # TrueType payload
    for part in deck.part.package.iter_parts():
        if part.content_type.endswith('theme+xml'):
            scheme = etree.fromstring(part.blob)
            assert scheme.xpath('//a:majorFont/a:latin/@typeface', namespaces=NS) == ['Newsreader']
            assert scheme.xpath('//a:minorFont/a:latin/@typeface', namespaces=NS) == ['Georgia']


@pytest.mark.parametrize('font_source', ('installed', 'fallback'))
def test_pdf_embeds_and_measures_with_the_available_supporting_font(results, font_source, monkeypatch):
    from src.services.presentation_exports import _pdf_face

    if font_source == 'fallback':
        monkeypatch.setattr(presentation_fonts, '_georgia_directories', lambda: ())
    presentation_fonts.supporting_pdf_font.cache_clear()
    try:
        expected = (['Georgia', 'Georgia-Bold', 'Georgia-Italic'] if font_source == 'installed' else
                    ['Gelasio-Regular', 'Gelasio-Bold', 'Gelasio-Italic'])
        faces = [_pdf_face('Recorded plates', 'Georgia', False), _pdf_face('Previous session', 'Georgia', True),
                 _pdf_face('Nov 20, 2026', 'Georgia', False, italic=True)]
        if font_source == 'installed' and any(face.startswith('Gelasio') for face in faces):
            pytest.skip('Georgia Regular, Bold and Italic are required for the installed-font test')
        assert faces == expected
        pdf = generate_deck('assembly', 'light', results, 'pdf')
        names = re.findall(rb'/BaseFont /(?:[A-Z]{6}\+)?([^\s/]+)', pdf)
        assert set(names) == {b'Newsreader-Regular', *(name.encode() for name in expected)}
        assert pdf.count(b'/FontFile2 ') == 4
    finally:
        presentation_fonts.supporting_pdf_font.cache_clear()
