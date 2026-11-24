"""Read/modify/write the saved Office package, including teachers' native edits."""
from copy import deepcopy
from dataclasses import replace
from io import BytesIO
from unittest.mock import patch

from PIL import Image
from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.util import Pt
import pytest

from src.services import assembly_powerpoint_merge as merge
from src.services import presentation_exports as exports, presentation_motion as motion
from src.services.presentation_exports import generate_deck


@pytest.fixture
def snapshot():
    latest = dict(name='Winter Lunch', date='2026-11-18', student_clean=85, faculty_clean=5,
                  clean=90, dirty=8, very_dirty=2, total=100, clean_percentage=90)
    prior = dict(latest, name='Autumn Lunch', date='2026-11-09', student_clean=43, faculty_clean=2,
                 clean=45, dirty=12, very_dirty=3, total=60, clean_percentage=75)
    return dict(school_name='Sample School', generated_at='2026-11-20T13:00:00+00:00',
                totals=dict(clean=135, total=160, clean_percentage=84.4, session_count=2),
                latest=latest, previous=prior, change=dict(clean=45, total=40, clean_percentage_points=15),
                winner_names={'student': 'Sample student', 'faculty': 'Sample teacher'},
                winner_keys={'student': 'first-student-award', 'faculty': 'first-faculty-award'})


def generate(snapshot):
    return generate_deck('assembly', 'dark', snapshot, platform='powerpoint')


def save(deck):
    data = BytesIO()
    deck.save(data)
    return data.getvalue()


def picture(slide, idx, color):
    stream = BytesIO()
    Image.new('RGB', (83, 52), color).save(stream, format='PNG')
    obj = slide.placeholders[idx].insert_picture(stream)
    obj.name = f'Picture Placeholder {idx + 5}'
    obj.crop_top = 0.125
    return stream.getvalue()


def slide_by_role(deck, name):
    return next(s for s in deck.slides if s._element.cSld.get('name') == name)


def shapes(slide):
    return {s.name: s for s in slide.shapes}


@pytest.mark.parametrize('registered', [False, True])
def test_lunch_wording_refresh_preserves_names_teacher_edits_and_hidden_pages(snapshot, registered):
    data = dict(snapshot, latest=dict(snapshot['latest'], name='Friday Lunch'),
                previous=dict(snapshot['previous'], name='Monday Lunch'))
    fresh = generate(data)
    old = Presentation(BytesIO(fresh))
    table = slide_by_role(old, 'Session comparison')
    table._element.cSld.set('name', 'Lunch to lunch')
    for role, page in [('overview', old.slides[1]), ('latest', slide_by_role(old, 'Friday Lunch')),
                       ('table', table), ('chart', slide_by_role(old, 'Clean-plate rate'))]:
        for label, (previous, _) in merge.LEGACY_SESSION_LABELS[role].items():
            shapes(page)[label].text = previous
        notes = page.notes_slide.notes_text_frame.paragraphs
        notes[0].text = merge.LEGACY_SESSION_CUES[role]
        if role in ('table', 'chart'):
            notes[2].text = (notes[2].text.replace('Previous session:', 'Previous lunch:')
                             .replace('Latest session:', 'Latest lunch:').replace('in the latest session.', 'at the latest lunch.'))
    saved = save(old)
    if registered:
        saved = merge.mark_new_deck(saved, data)
    school = Presentation(BytesIO(saved))
    table = slide_by_role(school, 'Lunch to lunch')
    table._element.set('show', '0')  # Teacher already hid it before the first sync.
    chart = slide_by_role(school, 'Clean-plate rate')
    chart._element.cSld.set('name', 'Lunch council chart')
    shapes(chart)['Previous lunch label'].text = 'Our lunch baseline'
    for page in (table, chart):
        page.notes_slide.notes_text_frame.add_paragraph().text = 'Ask the lunch coordinator to speak.'
    saved = save(school)
    original_order = [s.slide_id for s in school.slides]
    one = dict(data, previous=None, change=None)
    for refresh in (one, one, data, data):
        saved = merge.merge_deck(saved, generate(refresh), refresh)
        model = Presentation(BytesIO(saved))
        assert [s.slide_id for s in model.slides] == original_order
        assert shapes(model.slides[1])['latest_heading'].text == 'Latest session'
        assert shapes(model.slides[1])['latest_name'].text == 'Friday Lunch'
        assert shapes(slide_by_role(model, 'Friday Lunch'))['title'].text == 'Latest session'
        table = slide_by_role(model, 'Session comparison')
        assert table._element.get('show') == '0'
        assert shapes(table)['title'].text == 'Session comparison'
        chart = slide_by_role(model, 'Lunch council chart')
        assert (chart._element.get('show') == '0') == (refresh is one)
        assert shapes(chart)['Previous lunch label'].text == 'Our lunch baseline'
        for page in (table, chart):
            assert shapes(page)['Latest lunch label'].text == 'Latest session'
            assert shapes(page)['prev_name'].text == 'Monday Lunch'
            assert shapes(page)['curr_name'].text == 'Friday Lunch'
            lines = [p.text for p in page.notes_slide.notes_text_frame.paragraphs]
            assert len(lines) == 4 and lines[3] == 'Ask the lunch coordinator to speak.'
            assert 'Previous session: Monday Lunch' in lines[2] and 'Latest session: Friday Lunch' in lines[2]
            assert 'in the latest session.' in lines[2]


def assert_pictures(slide, photos):
    for idx in (21, 22):
        obj = slide.placeholders[idx]
        if idx in photos:
            assert obj.image.blob == photos[idx] and obj.crop_top == 0.125
        else:
            assert obj._element.tag.endswith('}sp')


@pytest.mark.parametrize('hide', [False, True])
def test_same_people_refresh_then_new_draw_archives_and_keeps_other_portrait(snapshot, hide):
    deck = Presentation(BytesIO(merge.mark_new_deck(generate(snapshot), snapshot)))
    winner = slide_by_role(deck, 'gp.winner')
    if hide:
        winner._element.set('show', '0')
    original_id = winner.slide_id
    photos = {21: picture(winner, 21, 'red'), 22: picture(winner, 22, 'blue')}
    winner.notes_slide.notes_text_frame.add_paragraph().text = 'Cue from our assembly organizer.'
    winner.shapes.add_textbox(Pt(10), Pt(15), Pt(180), Pt(30)).text = 'Student council'
    # Real users edit and move slides between any two managed pages.
    custom = deck.slides.add_slide(deck.slide_layouts[6])
    custom.shapes.add_textbox(Pt(40), Pt(60), Pt(300), Pt(40)).text = 'Student council agenda'
    custom_id = custom.slide_id
    ids = deck.slides._sldIdLst
    ids.insert(3, ids[-1])
    cover = shapes(slide_by_role(deck, 'School Results'))
    cover['all_clean'].left = Pt(87)
    cover['all_clean'].text_frame.paragraphs[0].runs[0].font.underline = True
    cover['!!Golden Plate wordmark'].text = 'Hand-edited publisher'
    snapshot['totals']['clean'] = 145
    snapshot['latest']['name'] = 'Friday Lunch'
    input_file = save(deck)
    merged = merge.merge_deck(input_file, generate(snapshot), snapshot)
    updated = Presentation(BytesIO(merged))
    same = slide_by_role(updated, 'gp.winner')
    assert same.slide_id == original_id
    assert_pictures(same, photos)
    assert 'Cue from our assembly organizer.' in same.notes_slide.notes_text_frame.text
    assert shapes(slide_by_role(updated, 'School Results'))['all_clean'].left == Pt(87)
    assert shapes(slide_by_role(updated, 'School Results'))['all_clean'].text == '145 clean plates'
    assert shapes(slide_by_role(updated, 'School Results'))['all_clean'].text_frame.paragraphs[0].runs[0].font.underline
    assert shapes(slide_by_role(updated, 'School Results'))['!!Golden Plate wordmark'].text == 'Hand-edited publisher'
    assert slide_by_role(updated, 'Friday Lunch') is not None
    assert updated.slides[3].slide_id == custom_id
    assert updated.slides[3].shapes[0].text == 'Student council agenda'

    # This is a different award/person with the same display name.
    snapshot['winner_keys']['student'] = 'second-student-award'
    changed = merge.merge_deck(merged, generate(snapshot), snapshot)
    for repeat in range(2):
        output = Presentation(BytesIO(changed))
        history = slide_by_role(output, 'gp.winner.history')
        actual = slide_by_role(output, 'gp.winner')
        assert len(output.slides) == 11 and output.slides[3].slide_id == custom_id
        assert history.slide_id == original_id and history._element.get('show') == '0'
        assert (actual._element.get('show') == '0') == hide
        assert 'Cue from our assembly organizer.' in history.notes_slide.notes_text_frame.text
        assert_pictures(history, photos)
        assert_pictures(actual, {22: photos[22]})
        assert {s.text for s in history.shapes if s.has_text_frame} >= {'Student council'}
        assert 'second-student-award' not in str(merge._state(merge.Package(changed)))
        if not repeat:
            changed = merge.merge_deck(changed, generate(snapshot), snapshot)


def test_details_added_to_existing_winner_then_changed_in_place_with_single_and_dual_layouts(snapshot):
    full = generate(snapshot)
    original = Presentation(BytesIO(full))
    winner = slide_by_role(original, 'gp.winner')
    for role in ('student', 'faculty'):
        stats = shapes(winner)['winner_stats_' + role]._element
        stats.getparent().remove(stats)  # Existing first-release winner layout.
    saved = merge.mark_new_deck(save(original), snapshot)
    original = Presentation(BytesIO(saved))
    winner = slide_by_role(original, 'gp.winner')
    photo = picture(winner, 21, 'red')
    ident = winner.slide_id
    saved = save(original)
    snapshot['winner_details'] = {'student': {'tickets': 3.75, 'probability': 12.5, 'pool_size': 8,
                                               'method': 'random', 'grade': 7}}
    for faculty, ticket_count, gain in ((False, 3.75, 1), (True, 4.25, 2), (True, 4.25, 3)):
        if faculty:
            snapshot['winner_names']['faculty'] = 'Another teacher'
            snapshot['winner_keys']['faculty'] = 'next-faculty-award'
        else:
            snapshot['winner_names'].pop('faculty')
            snapshot['winner_keys'].pop('faculty')
        snapshot['winner_details']['student']['tickets'] = ticket_count
        snapshot['winner_details']['student']['next_ticket_gain'] = gain
        fresh = generate(snapshot)
        saved = merge.merge_deck(saved, fresh, snapshot)
        deck = Presentation(BytesIO(saved))
        actual, expected = slide_by_role(deck, 'gp.winner'), slide_by_role(Presentation(BytesIO(fresh)), 'gp.winner')
        assert len(deck.slides) == 9 and actual.slide_id == ident
        assert_pictures(actual, {21: photo})
        for name in ('winner_title', 'winner_stats_faculty', 'winner_stats_student', 'winner_name_student'):
            got, wanted = shapes(actual)[name], shapes(expected)[name]
            assert (got.text, got.left, got.width) == (wanted.text, wanted.left, wanted.width)
        assert f'{ticket_count:.2f} tickets' in shapes(actual)['winner_stats_student'].text
        assert f'+{gain} ticket' in shapes(actual)['winner_stats_student'].text
        assert shapes(actual)['winner_title'].text == ('Golden Plate winners' if faculty else 'Golden Plate winner')


def test_empty_winner_manually_filled_stays_editable_until_a_new_award(snapshot):
    snapshot.pop('winner_names')
    snapshot.pop('winner_keys')
    generated = generate(snapshot)
    doc = Presentation(BytesIO(merge.mark_new_deck(generated, snapshot)))
    page = slide_by_role(doc, 'gp.winner')
    shapes(page)['winner_name_student'].text = 'School-selected recipient'
    photo = picture(page, 21, 'gold')
    result = merge.merge_deck(save(doc), generated, snapshot)
    actual = slide_by_role(Presentation(BytesIO(result)), 'gp.winner')
    assert shapes(actual)['winner_name_student'].text == 'School-selected recipient'
    assert_pictures(actual, {21: photo})
    snapshot['winner_names'] = {'student': 'New recipient'}
    snapshot['winner_keys'] = {'student': 'new-award-key'}
    next_doc = Presentation(BytesIO(merge.merge_deck(result, generate(snapshot), snapshot)))
    assert_pictures(slide_by_role(next_doc, 'gp.winner.history'), {21: photo})
    assert_pictures(slide_by_role(next_doc, 'gp.winner'), {})
    assert shapes(slide_by_role(next_doc, 'gp.winner'))['winner_name_student'].text == 'New recipient'


def remove_slide(deck, slide):
    slide_id = next(n for n in deck.slides._sldIdLst if int(n.get('id')) == slide.slide_id)
    deck.part.drop_rel(slide_id.rId)
    deck.slides._sldIdLst.remove(slide_id)


def legacy_deck(fresh, snapshot):
    # The standalone overview retains the previous assembly cover's original
    # masthead, quarter-second transition, shape IDs and brand entrances.
    old = merge.Package(generate_deck('overview', 'dark', snapshot, platform='powerpoint'))
    package = merge.Package(fresh)
    _, part = merge._names(package)['overview']
    header = deepcopy(old.xml(old.slides()[0][1]))
    image_rel = package.xml(part).find('.//a:blip', merge.NS).get(f'{{{merge.R}}}embed')
    header.find('.//a:blip', merge.NS).set(f'{{{merge.R}}}embed', image_rel)
    package.put(part, header)
    result = Presentation(BytesIO(package.save()))
    remove_slide(result, slide_by_role(result, 'gp.intro'))
    remove_slide(result, slide_by_role(result, 'gp.outro'))
    return Presentation(BytesIO(save(result)))


def has_morph(slide):
    return bool(slide._element.xpath('.//*[local-name()="morph"]'))


@pytest.mark.parametrize('registered', [False, True])
@pytest.mark.parametrize('previous_default,chosen,expected', [('450', '450', '850'), ('450', '630', '630'), ('850', '450', '450')])
def test_results_morph_restores_stock_speed_and_keeps_owner_edits(snapshot, registered, previous_default, chosen, expected):
    current = generate(snapshot)
    model = Presentation(BytesIO(current))
    intro = slide_by_role(model, 'gp.intro')._element
    assert merge._named_timing(intro) == merge.EARLY_HANDOFF_TIMING
    if previous_default == '850':
        for cue in intro.xpath('.//p:timing//p:cond[@delay="1460"]'):
            cue.set('delay', '1650')
        for transition in intro.xpath('.//p:transition'):
            transition.set('advTm', '2283')
    duration = f'{{{merge.P14}}}dur'
    cover = slide_by_role(model, 'School Results')._element
    cover.xpath('.//*[local-name()="morph"]')[0].getparent().set(duration, previous_default)
    saved = save(model)
    if registered:
        saved = merge.mark_new_deck(saved, snapshot)
    model = Presentation(BytesIO(saved))
    cover = slide_by_role(model, 'School Results')._element
    cover.xpath('.//*[local-name()="morph"]')[0].getparent().set(duration, chosen)
    saved = save(model)
    for _ in range(2):
        saved = merge.merge_deck(saved, current, snapshot)
        updated = Presentation(BytesIO(saved))
        cover = slide_by_role(updated, 'School Results')._element
        assert cover.xpath('.//*[local-name()="morph"]')[0].getparent().get(duration) == expected
        for role, hold in [('gp.intro', '1500'), ('gp.outro', '2283')]:
            page = slide_by_role(updated, role)._element
            assert page.xpath('.//p:transition/@advTm') == [hold, hold]


@pytest.mark.parametrize('tracked', [False, True])
def test_legacy_cover_morphs_once_preserving_custom_order_notes_and_motion(snapshot, tracked):
    fresh = generate(snapshot)
    legacy = legacy_deck(fresh, snapshot)
    if tracked:
        package = merge.Package(merge.mark_new_deck(save(legacy), snapshot))
        registry = merge._state(package)
        registry['overview'].pop('transition')  # Pre-intro registry format.
        merge._save_state(package, registry)
        legacy = Presentation(BytesIO(package.save()))
    cover = slide_by_role(legacy, 'School Results')
    cover_id = cover.slide_id
    original = shapes(cover)
    picture_id, wordmark_id = original['Plate mark'].shape_id, original['Publisher'].shape_id
    original['Publisher'].text = 'Teacher wordmark'
    cover.notes_slide.notes_text_frame.add_paragraph().text = 'Introduce the lunch coordinator.'
    custom = legacy.slides.add_slide(legacy.slide_layouts[6])
    custom.shapes.add_textbox(Pt(48), Pt(160), Pt(400), Pt(40)).text = 'School announcements'
    ids = legacy.slides._sldIdLst
    ids.insert(0, ids[-1])  # The teacher's opening stays first.
    merged = save(legacy)
    expected = shapes(slide_by_role(Presentation(BytesIO(fresh)), 'School Results'))
    for _ in range(2):
        merged = merge.merge_deck(merged, fresh, snapshot)
        result = Presentation(BytesIO(merged))
        assert len(result.slides) == 10 and result.slides[0].slide_id == custom.slide_id
        assert result.slides[1]._element.cSld.get('name') == 'gp.intro'
        cover = result.slides[2]
        assert cover.slide_id == cover_id and has_morph(cover)
        actual = shapes(cover)
        assert 'Plate mark' not in actual and 'Publisher' not in actual
        for name in (*merge.BRAND_NAMES.values(), 'school'):
            assert (actual[name].left, actual[name].width) == (expected[name].left, expected[name].width)
        assert actual['school'].text_frame.paragraphs[0].alignment == expected['school'].text_frame.paragraphs[0].alignment
        assert actual['!!Golden Plate wordmark'].text == 'Teacher wordmark'
        assert actual['!!Golden Plate mark'].shape_id == picture_id
        animated = set(cover._element.xpath('.//p:timing//*[@spid]/@spid'))
        assert {str(picture_id), str(wordmark_id)}.isdisjoint(animated)
        assert str(actual['all_clean'].shape_id) in animated
        assert 'Introduce the lunch coordinator.' in cover.notes_slide.notes_text_frame.text


def interim_right_masthead(fresh, snapshot, tracked):
    interim = Presentation(BytesIO(fresh))
    cover = shapes(slide_by_role(interim, 'School Results'))
    cover[merge.MORPH_MARK].left = Pt(724)
    cover[merge.MORPH_WORDMARK].left, cover[merge.MORPH_WORDMARK].width = Pt(766), Pt(146)
    cover['school'].left = Pt(48)
    cover['school'].text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT
    saved = save(interim)
    if tracked:
        package = merge.Package(merge.mark_new_deck(saved, snapshot))
        registry = merge._state(package)
        registry['overview'].pop('original_masthead')  # Original right-hand release.
        merge._save_state(package, registry)
        saved = package.save()
    return saved


@pytest.mark.parametrize('tracked', [False, True])
def test_interim_right_masthead_restores_original_then_preserves_later_teacher_edits(snapshot, tracked):
    fresh = generate(snapshot)
    saved = interim_right_masthead(fresh, snapshot, tracked)
    native_original = Presentation(BytesIO(generate_deck('overview', 'dark', snapshot, platform='powerpoint')))
    original = shapes(native_original.slides[0])
    result = Presentation(BytesIO(merge.merge_deck(saved, fresh, snapshot)))
    cover = shapes(slide_by_role(result, 'School Results'))
    assert cover[merge.MORPH_MARK].left == Pt(48) and cover[merge.MORPH_WORDMARK].left == Pt(90)
    for prior, name in {**merge.BRAND_NAMES, 'school': 'school'}.items():
        expected, actual = original[prior], cover[name]
        assert (actual.left, actual.top, actual.width, actual.height) == (
            expected.left, expected.top, expected.width, expected.height)
    assert cover['school'].text_frame.paragraphs[0].alignment == PP_ALIGN.RIGHT

    # If someone later deliberately chooses those positions, the one-time
    # repair must not undo them during their next school data update.
    cover[merge.MORPH_MARK].left = Pt(724)
    cover[merge.MORPH_WORDMARK].left, cover[merge.MORPH_WORDMARK].width = Pt(766), Pt(146)
    cover['school'].left = Pt(48)
    cover['school'].text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT
    again = Presentation(BytesIO(merge.merge_deck(save(result), fresh, snapshot)))
    chosen = shapes(slide_by_role(again, 'School Results'))
    assert chosen[merge.MORPH_MARK].left == Pt(724)
    assert chosen[merge.MORPH_WORDMARK].left == Pt(766) and chosen[merge.MORPH_WORDMARK].width == Pt(146)
    assert chosen['school'].left == Pt(48) and chosen['school'].text_frame.paragraphs[0].alignment == PP_ALIGN.LEFT


def test_interim_edited_logo_and_label_keep_position_and_alignment(snapshot):
    fresh = generate(snapshot)
    edited = Presentation(BytesIO(interim_right_masthead(fresh, snapshot, tracked=True)))
    header = shapes(slide_by_role(edited, 'School Results'))
    header[merge.MORPH_MARK].top = Pt(34)
    header['school'].left = Pt(121)
    result = Presentation(BytesIO(merge.merge_deck(save(edited), fresh, snapshot)))
    actual = shapes(slide_by_role(result, 'School Results'))
    assert actual[merge.MORPH_MARK].left == Pt(724) and actual[merge.MORPH_MARK].top == Pt(34)
    assert actual[merge.MORPH_WORDMARK].left == Pt(90) and actual[merge.MORPH_WORDMARK].width == Pt(157.5)
    assert actual['school'].left == Pt(121) and actual['school'].text_frame.paragraphs[0].alignment == PP_ALIGN.LEFT


def test_reordered_hidden_and_deleted_intro_do_not_morph_a_teacher_slide(snapshot):
    fresh = generate(snapshot)
    source = merge.mark_new_deck(fresh, snapshot)
    deck = Presentation(BytesIO(source))
    intro = slide_by_role(deck, 'gp.intro')
    custom = deck.slides.add_slide(deck.slide_layouts[6])
    ids = deck.slides._sldIdLst
    ids.insert(1, ids[-1])
    updated = Presentation(BytesIO(merge.merge_deck(save(deck), fresh, snapshot)))
    assert updated.slides[0].slide_id == intro.slide_id and updated.slides[1].slide_id == custom.slide_id
    assert not has_morph(slide_by_role(updated, 'School Results'))
    ids = updated.slides._sldIdLst
    ids.append(ids[1])
    updated = Presentation(BytesIO(merge.merge_deck(save(updated), fresh, snapshot)))
    assert has_morph(slide_by_role(updated, 'School Results'))
    intro = slide_by_role(updated, 'gp.intro')
    intro._element.set('show', '0')
    updated = Presentation(BytesIO(merge.merge_deck(save(updated), fresh, snapshot)))
    assert not has_morph(slide_by_role(updated, 'School Results'))
    remove_slide(updated, slide_by_role(updated, 'gp.intro'))
    for _ in range(2):
        updated = Presentation(BytesIO(merge.merge_deck(save(updated), fresh, snapshot)))
        assert len(updated.slides) == 9
        assert all(s._element.cSld.get('name') != 'gp.intro' for s in updated.slides)
        assert not has_morph(slide_by_role(updated, 'School Results'))


def test_inserted_intro_joins_cover_section_and_preserves_native_compact_transition(snapshot):
    fresh = generate(snapshot)
    package = merge.Package(save(legacy_deck(fresh, snapshot)))
    roles = merge._names(package)
    cover_id, part = roles['overview']
    cover = package.xml(part)
    transition = merge._transition(cover)
    cover.replace(transition, deepcopy(transition.find('.//p:transition', merge.NS)))
    package.put(part, cover)
    pres = package.xml(merge.PRES)
    extlst = pres.find('p:extLst', merge.NS)
    if extlst is None:
        extlst = merge.ET.SubElement(pres, f'{{{merge.P}}}extLst')
    ext = merge.ET.SubElement(extlst, f'{{{merge.P}}}ext', uri='{521415D9-36F7-43E2-AB2F-B90AF26B5E84}')
    sections = merge.ET.SubElement(ext, f'{{{merge.P14}}}sectionLst')
    section = merge.ET.SubElement(sections, f'{{{merge.P14}}}section', name='Lunch evidence',
                                  id='{3A417B72-88D3-48D7-A171-0E4AD9861661}')
    members = merge.ET.SubElement(section, f'{{{merge.P14}}}sldIdLst')
    for ident, _ in package.slides():
        merge.ET.SubElement(members, f'{{{merge.P14}}}sldId', id=str(ident))
    package.put(merge.PRES, pres)
    result = merge.Package(merge.merge_deck(package.save(), fresh, snapshot))
    result_roles = merge._names(result)
    assert merge._transition_signature(merge._transition(result.xml(result_roles['overview'][1]))) == 'morph850'
    enrolled = result.xml(merge.PRES).findall(f'.//{{{merge.P14}}}section/{{{merge.P14}}}sldIdLst/*')
    assert [int(n.get('id')) for n in enrolled] == [ident for ident, _ in result.slides()]
    assert [int(n.get('id')) for n in enrolled[:2]] == [result_roles['intro'][0], cover_id]


def test_reused_deleted_intro_id_does_not_claim_teachers_replacement(snapshot):
    fresh = generate(snapshot)
    deck = Presentation(BytesIO(merge.mark_new_deck(fresh, snapshot)))
    original_id = deck.slides[0].slide_id
    remove_slide(deck, deck.slides[0])
    deck = Presentation(BytesIO(save(deck)))
    replacement = deck.slides.add_slide(deck.slide_layouts[6])
    replacement.shapes.add_textbox(Pt(48), Pt(90), Pt(400), Pt(60)).text = 'Spring athletics'
    ids = deck.slides._sldIdLst
    ids[-1].set('id', str(original_id))
    ids.insert(0, ids[-1])
    result = Presentation(BytesIO(merge.merge_deck(save(deck), fresh, snapshot)))
    assert len(result.slides) == 9
    assert result.slides[0].shapes[0].text == 'Spring athletics'
    assert all(s._element.cSld.get('name') != 'gp.intro' for s in result.slides)
    assert not has_morph(slide_by_role(result, 'School Results'))


def test_user_adjusted_cover_transition_and_logo_position_survive_upgrade(snapshot):
    fresh = generate(snapshot)
    deck = legacy_deck(fresh, snapshot)
    cover = slide_by_role(deck, 'School Results')
    shapes(cover)['Plate mark'].left = Pt(175)
    for variant in cover._element.xpath('.//p:transition'):
        variant[0].tag = f'{{{merge.P}}}push'
        variant[0].set('dir', 'l')
    result = Presentation(BytesIO(merge.merge_deck(save(deck), fresh, snapshot)))
    cover = slide_by_role(result, 'School Results')
    assert shapes(cover)['!!Golden Plate mark'].left == Pt(175)
    assert cover._element.xpath('.//p:transition/p:push[@dir="l"]')
    assert not has_morph(cover)


def test_legacy_six_slide_upgrade_preserves_order_and_imports_working_picture_layout(snapshot):
    initial = generate(snapshot)
    legacy = legacy_deck(initial, snapshot)
    winner = slide_by_role(legacy, 'gp.winner')
    remove_slide(legacy, winner)
    # Legacy six-page files also lack the dedicated winner layout and its rel.
    master = legacy.slide_master
    layout_id = next(n for n in master._element.sldLayoutIdLst
                     if master.part.related_part(n.rId) is winner.slide_layout.part)
    master.part.drop_rel(layout_id.rId)
    master._element.sldLayoutIdLst.remove(layout_id)
    ids = [s.slide_id for s in legacy.slides]
    recovered = merge.merge_deck(save(legacy), initial, snapshot)
    deck = Presentation(BytesIO(recovered))
    assert [s.slide_id for s in deck.slides if s._element.cSld.get('name') not in ('gp.intro', 'gp.winner', 'gp.outro')] == ids
    assert deck.slides[5]._element.cSld.get('name') == 'gp.winner'
    assert_pictures(deck.slides[5], {})
    assert deck.slides[5].slide_layout._element.cSld.get('name') == 'gp.winner'
    image = picture(deck.slides[5], 21, 'green')
    reloaded = Presentation(BytesIO(merge.merge_deck(save(deck), initial, snapshot)))
    assert_pictures(reloaded.slides[5], {21: image})
    assert len(reloaded.slides) == 9


def test_missing_data_hides_managed_pages_and_restores_only_automatically_hidden_pages(snapshot):
    full = generate(snapshot)
    deck = Presentation(BytesIO(merge.mark_new_deck(full, snapshot)))
    slide_by_role(deck, 'Session comparison')._element.set('show', '0')  # teacher hid the comparison
    short = dict(snapshot, previous=None, change=None)
    result = merge.merge_deck(save(deck), generate(short), short)
    small = Presentation(BytesIO(result))
    assert len(small.slides) == 9
    assert slide_by_role(small, 'Session comparison')._element.get('show') == slide_by_role(small, 'Clean-plate rate')._element.get('show') == '0'
    restored = Presentation(BytesIO(merge.merge_deck(result, full, snapshot)))
    assert slide_by_role(restored, 'Session comparison')._element.get('show') == '0'
    assert slide_by_role(restored, 'Clean-plate rate')._element.get('show') is None


def test_known_dirty_label_ink_follows_zero_counts_in_both_directions(snapshot):
    blob = merge.mark_new_deck(generate(snapshot), snapshot)
    for count in (0, 2):
        snapshot['latest'].update(dirty=count, very_dirty=count)
        fresh = generate(snapshot)
        blob = merge.merge_deck(blob, fresh, snapshot)
        native = Presentation(BytesIO(blob))
        source = Presentation(BytesIO(fresh))
        for name in merge.DIRTY_LABELS:
            def ink(slide):
                return shapes(slide)[name].text_frame.paragraphs[0].runs[0].font.color.rgb
            assert ink(slide_by_role(native, 'Winter Lunch')) == ink(slide_by_role(source, 'Winter Lunch'))


def test_unidentifiable_association_fails_without_overwriting():
    blank = save(Presentation())
    with pytest.raises(merge.MergeError):
        merge.merge_deck(blank, blank, {})


def previous_two_object_deck(snapshot):
    """Rebuild the shipped static two-object layout using its original native cues."""
    current_opening = exports.opening_pair
    current_motion = exports.add_slide_motion

    def opening(overview, school, theme):
        current, results = current_opening(overview, school, theme)
        source = {item.name: item for item in results.items}
        mark, word = source[merge.MORPH_MARK], source[merge.MORPH_WORDMARK]
        large_mark = replace(mark, x=195, y=216, width=mark.width * 3, height=mark.height * 3)
        large_word = replace(word, x=195 + (word.x - mark.x) * 3, y=216 + (word.y - mark.y) * 3,
                             width=word.width * 3, height=word.height * 3, size=word.size * 3,
                             tracking=word.tracking * 3)
        return replace(current, items=[large_mark, large_word]), results

    def animate(slide, template_index, overrides, **options):
        if template_index in motion.SIGNATURE_LAYOUTS:
            cues = [motion.Entrance(merge.MORPH_MARK, 60, 'lift', 0),
                    motion.Entrance(merge.MORPH_WORDMARK, 215, 'across', 0)]
            with patch.object(motion, 'slide_entrances', return_value=cues):
                return current_motion(slide, 0, overrides)
        return current_motion(slide, template_index, overrides, **options)

    with patch.object(exports, 'opening_pair', opening), patch.object(exports, 'add_slide_motion', animate):
        deck = Presentation(BytesIO(generate(snapshot)))
    remove_slide(deck, slide_by_role(deck, 'gp.outro'))
    return save(deck)


def assert_media_program(package, part, fresh, source_part):
    page = package.xml(part)
    film = dict(merge._shapes(page))[merge.SIGNATURE_FILM]
    expected = dict(merge._shapes(fresh.xml(source_part)))[merge.SIGNATURE_FILM]
    media_paths = []
    for node, attribute in (('videoFile', 'link'), ('media', 'embed'), ('blip', 'embed')):
        relation = f'{{{merge.R}}}' + attribute
        def resource(book, owner, shape):
            rid = next(n.get(relation) for n in shape.iter() if merge.ET.QName(n).localname == node)
            rel = book.relations(owner)[rid]
            assert rel.get('TargetMode') != 'External'
            return merge._resolve(owner, rel.get('Target'))
        actual_path = resource(package, part, film)
        assert package.read(actual_path) == fresh.read(resource(fresh, source_part, expected))
        media_paths.append(actual_path)
    assert media_paths[0] == media_paths[1]
    all_shape_ids = {merge._shape_info(obj).get('id') for _, obj in merge._shapes(page)}
    assert all(n.get('spid') in all_shape_ids for n in page.xpath('p:timing//*[@spid]', namespaces=merge.NS))
    movie_id = merge._shape_info(film).get('id')
    assert movie_id in page.xpath('.//p:video//p:spTgt/@spid', namespaces=merge.NS)
    return media_paths


@pytest.mark.parametrize('tracked', [False, True])
def test_tutorial_updates_previous_intro_and_places_timed_outro_before_teacher_slides(snapshot, tracked):
    fresh = generate(snapshot)
    old = previous_two_object_deck(snapshot)
    if tracked:
        old = merge.mark_new_deck(old, snapshot)
    deck = Presentation(BytesIO(old))
    intro = slide_by_role(deck, 'gp.intro')
    original_ids = {s.name: s.shape_id for s in intro.shapes}
    annotation = intro.shapes.add_textbox(Pt(48), Pt(405), Pt(360), Pt(30))
    annotation.text, annotation.name = 'Student council announcement', 'Student council'
    intro.notes_slide.notes_text_frame.add_paragraph().text = 'Pause for the organizers.'
    agenda = deck.slides.add_slide(deck.slide_layouts[6])
    agenda.shapes.add_textbox(Pt(48), Pt(90), Pt(400), Pt(60)).text = 'Next school event'
    saved = save(deck)
    source = merge.Package(fresh)
    templates = merge._names(source)
    for _ in range(2):
        saved = merge.merge_deck(saved, fresh, snapshot)
        result = Presentation(BytesIO(saved))
        assert len(result.slides) == 10 and result.slides[-1].slide_id == agenda.slide_id
        assert result.slides[-3]._element.cSld.get('name') == 'Be Green, Do Good'
        assert result.slides[-2]._element.cSld.get('name') == 'gp.outro'
        assert result.slides[0].slide_id == intro.slide_id
        actual_shapes = shapes(result.slides[0])
        assert all(actual_shapes[n].shape_id == i for n, i in original_ids.items())
        assert actual_shapes['Student council'].text == annotation.text
        assert 'Pause for the organizers.' in result.slides[0].notes_slide.notes_text_frame.text
        package = merge.Package(saved)
        roles = merge._names(package)
        media = [assert_media_program(package, roles[role][1], source, templates[role][1])
                 for role in ('intro', 'outro')]
        assert media[0] == media[1] and len([path for path in package.names if path.endswith('.mp4')]) == 1
        assert {t.get('advTm') for t in result.slides[0]._element.xpath('.//p:transition')} == {'1500'}
        assert all(t.get('advTm') is None for t in result.slides[-3]._element.xpath('.//p:transition'))
        assert all(int(t.get('advTm')) > 0 for t in result.slides[-2]._element.xpath('.//p:transition'))


def test_tutorial_preserves_custom_intro_and_explicitly_removed_bridge(snapshot):
    fresh = generate(snapshot)
    previous = previous_two_object_deck(snapshot)
    deck = Presentation(BytesIO(merge.mark_new_deck(previous, snapshot)))
    intro = slide_by_role(deck, 'gp.intro')
    shapes(intro)[merge.MORPH_WORDMARK].text = 'Our assembly welcome'
    closing = slide_by_role(deck, 'Be Green, Do Good')
    closing._element.set('show', '0')
    result = Presentation(BytesIO(merge.merge_deck(save(deck), fresh, snapshot)))
    opener = slide_by_role(result, 'gp.intro')
    assert set(shapes(opener)) == {merge.MORPH_MARK, merge.MORPH_WORDMARK}
    assert shapes(opener)[merge.MORPH_WORDMARK].text == 'Our assembly welcome'
    outro = slide_by_role(result, 'gp.outro')
    assert outro._element.get('show') == '0'
    remove_slide(result, outro)
    result = Presentation(BytesIO(merge.merge_deck(save(result), fresh, snapshot)))
    assert all(page._element.cSld.get('name') != 'gp.outro' for page in result.slides)


def test_moved_closing_gets_bridge_in_place_and_later_bridge_reordering_survives(snapshot):
    fresh = generate(snapshot)
    old = previous_two_object_deck(snapshot)
    deck = Presentation(BytesIO(merge.mark_new_deck(old, snapshot)))
    closing = slide_by_role(deck, 'Be Green, Do Good')
    ids = deck.slides._sldIdLst
    ids.insert(3, next(n for n in ids if int(n.get('id')) == closing.slide_id))
    before = [s.slide_id for s in deck.slides]
    result = Presentation(BytesIO(merge.merge_deck(save(deck), fresh, snapshot)))
    bridge = slide_by_role(result, 'gp.outro')
    assert [s.slide_id for s in result.slides] == [*before[:4], bridge.slide_id, *before[4:]]
    ids = result.slides._sldIdLst
    ids.insert(0, next(n for n in ids if int(n.get('id')) == bridge.slide_id))
    after = [s.slide_id for s in result.slides]
    synced = Presentation(BytesIO(merge.merge_deck(save(result), fresh, snapshot)))
    assert [s.slide_id for s in synced.slides] == after


def test_existing_deleted_signoff_does_not_get_an_orphan_bridge(snapshot):
    fresh = generate(snapshot)
    old = previous_two_object_deck(snapshot)
    deck = Presentation(BytesIO(merge.mark_new_deck(old, snapshot)))
    remove_slide(deck, slide_by_role(deck, 'Be Green, Do Good'))
    synced = Presentation(BytesIO(merge.merge_deck(save(deck), fresh, snapshot)))
    assert all(s._element.cSld.get('name') not in ('Be Green, Do Good', 'gp.outro') for s in synced.slides)


@pytest.mark.parametrize('manual', [False, True])
def test_outro_refreshes_only_the_previous_managed_advance_time(snapshot, manual):
    current = generate(snapshot)
    prior = Presentation(BytesIO(current))
    page = slide_by_role(prior, 'gp.outro')
    for transition in page._element.xpath('.//p:transition'):
        transition.set('advTm', '550')
    tracked = merge.mark_new_deck(save(prior), snapshot)
    if manual:
        customized = Presentation(BytesIO(tracked))
        for transition in slide_by_role(customized, 'gp.outro')._element.xpath('.//p:transition'):
            transition.set('advTm', '8500')
        tracked = save(customized)
    updated = Presentation(BytesIO(merge.merge_deck(tracked, current, snapshot)))
    transitions = slide_by_role(updated, 'gp.outro')._element.xpath('.//p:transition')
    assert {t.get('advTm') for t in transitions} == {'8500' if manual else '2283'}


def previous_tutorial_timing(root):
    timing = root.find('p:timing', merge.NS)
    for node in timing.findall('.//p:cmd/p:cBhvr/p:cTn', merge.NS):
        node.set('dur', '3500')
    for condition in timing.iter(f'{{{merge.P}}}cond'):
        old_delay = {'950': '2800', '1650': '3425', '1460': '3425'}.get(condition.get('delay'))
        if old_delay:
            condition.set('delay', old_delay)
    assert merge._named_timing(root) == merge.PREVIOUS_BOOKEND_TIMING


def previous_click_intro(snapshot, tracked):
    current = generate(snapshot)
    prior = Presentation(BytesIO(current))
    page = slide_by_role(prior, 'gp.intro')
    previous_tutorial_timing(page._element)
    for transition in page._element.xpath('.//p:transition'):
        transition.set('advClick', '1')
        transition.attrib.pop('advTm')
    saved = save(prior)
    if tracked:
        package = merge.Package(merge.mark_new_deck(saved, snapshot))
        state = merge._state(package)
        state['intro'].pop('transition')  # The prior release tracked the film but not slide advance.
        merge._save_state(package, state)
        saved = package.save()
    return current, saved


@pytest.mark.parametrize('stored', ['unmarked', 'old_registry', 'compact', 'renumbered'])
def test_previous_stock_tutorial_advances_automatically_after_sync(snapshot, stored):
    current, prior = previous_click_intro(snapshot, stored == 'old_registry')
    if stored == 'compact':
        deck = Presentation(BytesIO(prior))
        intro = slide_by_role(deck, 'gp.intro')
        transition = merge._transition(intro._element)
        intro._element.replace(transition, deepcopy(transition.find('.//p:transition', merge.NS)))
        prior = save(deck)
    elif stored == 'renumbered':
        deck = Presentation(BytesIO(prior))
        intro = slide_by_role(deck, 'gp.intro')
        for obj in intro.shapes:
            props = merge._shape_info(obj._element)
            props.set('id', str(int(props.get('id')) + 10))
        for target in intro._element.xpath('.//p:timing//*[@spid]'):
            target.set('spid', str(int(target.get('spid')) + 10))
        prior = save(deck)
    for _ in range(2):
        prior = merge.merge_deck(prior, current, snapshot)
        deck = Presentation(BytesIO(prior))
        intro = slide_by_role(deck, 'gp.intro')
        variants = intro._element.xpath('.//p:transition')
        assert len(variants) == 2
        assert all(t.get('advClick') == '0' and t.get('advTm') == '1500' for t in variants)
        assert has_morph(slide_by_role(deck, 'School Results'))


@pytest.mark.parametrize('edit', ['timer', 'transition', 'removed', 'animation', 'no_animation', 'manual_after_upgrade'])
def test_intro_sync_keeps_teacher_advance_and_click_sequences(snapshot, edit):
    current, prior = previous_click_intro(snapshot, edit != 'no_animation')
    if edit == 'manual_after_upgrade':
        prior = merge.merge_deck(prior, current, snapshot)
    deck = Presentation(BytesIO(prior))
    intro = slide_by_role(deck, 'gp.intro')
    variants = intro._element.xpath('.//p:transition')
    if edit == 'timer':
        for item in variants:
            item.set('advTm', '9200')
    elif edit == 'transition':
        for item in variants:
            item[0].tag = f'{{{merge.P}}}push'
            item[0].set('dir', 'l')
    elif edit == 'removed':
        intro._element.remove(merge._transition(intro._element))
    elif edit == 'no_animation':
        intro._element.remove(intro._element.find('p:timing', merge.NS))
    elif edit == 'animation':
        clock = intro._element.xpath('.//p:timing//p:cTn[@presetClass="entr"]')[0]
        clock.find('p:stCondLst/p:cond', merge.NS).set('delay', '12000')
    else:
        for item in variants:
            item.set('advClick', '1')
            item.attrib.pop('advTm')
    chosen = merge._signature(merge._transition(intro._element))
    saved = save(deck)
    for _ in range(2):
        saved = merge.merge_deck(saved, current, snapshot)
        updated = slide_by_role(Presentation(BytesIO(saved)), 'gp.intro')
        assert merge._signature(merge._transition(updated._element)) == chosen
        if edit == 'no_animation':
            assert updated._element.find('p:timing', merge.NS) is None


@pytest.mark.parametrize('registered', [False, True])
@pytest.mark.parametrize('intro_setting', ['2283', '4050', '0', 'click'])
def test_short_intro_updates_stock_handoff_and_preserves_teacher_outro(snapshot, registered, intro_setting):
    current = generate(snapshot)
    school = Presentation(BytesIO(current))
    quick_intro = slide_by_role(school, 'gp.intro')._element
    for node in quick_intro.xpath('.//p:timing//p:cond[@delay="1460"]'):
        node.set('delay', '1650')
    assert merge._named_timing(quick_intro) == merge.QUICK_BOOKEND_TIMING
    for transition in quick_intro.xpath('.//p:transition'):
        transition.set('advTm', '2283')  # The shipped short intro initially waited after the movie.
    morph = slide_by_role(school, 'School Results')._element.xpath('.//*[local-name()="morph"]')[0]
    duration = f'{{{merge.P14}}}dur'
    morph.getparent().set(duration, '850')
    previous = save(school)
    if registered:
        previous = merge.mark_new_deck(previous, snapshot)
    school = Presentation(BytesIO(previous))
    keep_morph = intro_setting == 'click'
    if keep_morph:
        morph = slide_by_role(school, 'School Results')._element.xpath('.//*[local-name()="morph"]')[0]
        morph.getparent().set(duration, '670')
    for transition in slide_by_role(school, 'gp.intro')._element.xpath('.//p:transition'):
        if intro_setting == 'click':
            transition.set('advClick', '1')
            transition.attrib.pop('advTm')
        else:
            transition.set('advTm', intro_setting)
    for transition in slide_by_role(school, 'gp.outro')._element.xpath('.//p:transition'):
        transition.set('advTm', '0')  # A teacher chose an immediate exit as well.
    previous = save(school)
    expected = {'2283': ('0', '1500'), '4050': ('0', '4050'), 'click': ('1', None),
                '0': ('0', '0' if registered else '1500')}[intro_setting]
    original = merge.Package(previous)
    source = merge.Package(current)
    for _ in range(2):
        previous = merge.merge_deck(previous, current, snapshot)
        result = merge.Package(previous)
        overview = result.xml(merge._names(result)['overview'][1])
        morph = overview.xpath('.//*[local-name()="morph"]')[0]
        assert morph.getparent().get(duration) == ('670' if keep_morph else '850')
        for role, advance in [('intro', expected), ('outro', ('0', '0'))]:
            part = merge._names(result)[role][1]
            root = result.xml(part)
            assert [(t.get('advClick'), t.get('advTm')) for t in root.findall('.//p:transition', merge.NS)] == [advance] * 2
            assert merge._signature(root.find('p:timing', merge.NS)) == merge._signature(source.xml(part).find('p:timing', merge.NS))
            for name in merge.BOOKEND_LINKS:
                assert asset_bytes(result, part, name) == asset_bytes(original, part, name)


@pytest.fixture
def previous_line_media(snapshot, monkeypatch):
    # Small distinct media payloads stand in for the retired movie and picture
    # so the repository need not ship the retired graphic twice.
    current = generate(snapshot)
    prior = merge.Package(current)
    programs = merge._names(prior)
    previous = {merge.SIGNATURE_FILM: b'previous stock movie', merge.MORPH_MARK: b'previous stock picture'}
    for role in ('intro', 'outro'):
        part = programs[role][1]
        for name, data in previous.items():
            path, _ = merge._bookend_links(prior, part, name)
            prior.put(path, data)
        root = prior.xml(part)
        previous_tutorial_timing(root)
        for variant in root.xpath('.//p:transition', namespaces=merge.NS):
            variant.set('advTm', '3500')
        prior.put(part, prior.xml(part))
    monkeypatch.setitem(merge.PREVIOUS_BOOKEND_MEDIA, '101A16', {name: {merge._digest(data)} for name, data in previous.items()})
    return current, prior.save(), previous


def asset_bytes(package, part, name):
    return package.read(merge._bookend_links(package, part, name)[0])


@pytest.mark.parametrize('tracked', [False, True])
def test_quicker_tutorial_replaces_line_media_once_and_retires_only_unused_stock(previous_line_media, snapshot, tracked):
    current, prior, old_media = previous_line_media
    if tracked:
        prior = merge.mark_new_deck(prior, snapshot)
    source = merge.Package(current)
    before = None
    for _ in range(2):
        prior = merge.merge_deck(prior, current, snapshot)
        merged = merge.Package(prior)
        programs, expected = merge._names(merged), merge._names(source)
        paths = []
        for role in ('intro', 'outro'):
            part = programs[role][1]
            shared = []
            for name in old_media:
                path, _ = merge._bookend_links(merged, part, name)
                assert merged.read(path) == asset_bytes(source, expected[role][1], name)
                shared.append(path)
            paths.append(shared)
            assert merge._named_timing(merged.xml(part)) == merge._named_timing(source.xml(expected[role][1]))
            assert {n.get('advTm') for n in merged.xml(part).xpath('.//p:transition', namespaces=merge.NS)} == {'1500' if role == 'intro' else '2283'}
        assert paths[0] == paths[1]
        assert len([n for n in merged.names if n.endswith('.mp4')]) == 1
        assert not {merged.read(n) for n in merged.names if n.startswith('ppt/media/')} & set(old_media.values())
        if before is not None:
            assert before == merged.names
        before = merged.names


@pytest.mark.parametrize('registered', [False, True])
def test_desktop_line_timer_updates_then_respects_teacher_setting(previous_line_media, snapshot, registered):
    current, prior, _ = previous_line_media
    if registered:
        prior = merge.mark_new_deck(prior, snapshot)
    school = Presentation(BytesIO(prior))
    for role in ('gp.intro', 'gp.outro'):
        root = slide_by_role(school, role)._element
        previous = merge._transition(root)
        root.replace(previous, deepcopy(previous.find('.//p:transition', merge.NS)))
    restored = Presentation(BytesIO(merge.merge_deck(save(school), current, snapshot)))
    for role in ('gp.intro', 'gp.outro'):
        transitions = slide_by_role(restored, role)._element.xpath('.//p:transition')
        assert [(t.get('advClick'), t.get('advTm')) for t in transitions] == [('0', '1500' if role == 'gp.intro' else '2283')] * 2
        for transition in transitions:
            transition.set('advTm', '3500')  # An explicit teacher choice after the timing update.
    edited = save(restored)
    for _ in range(2):
        edited = merge.merge_deck(edited, current, snapshot)
        deck = Presentation(BytesIO(edited))
        for role in ('gp.intro', 'gp.outro'):
            transitions = slide_by_role(deck, role)._element.xpath('.//p:transition')
            assert [(t.get('advClick'), t.get('advTm')) for t in transitions] == [('0', '3500')] * 2


def test_quicker_tutorial_updates_only_managed_uses_of_shared_movie_and_picture(previous_line_media, snapshot):
    current, prior, old_media = previous_line_media
    model = Presentation(BytesIO(prior))
    extra = model.slides.add_slide(model.slide_layouts[6])
    original = merge.Package(save(model))
    intro = merge._names(original)['intro'][1]
    other = dict(original.slides())[extra.slide_id]
    for part in (intro, other):
        root = original.xml(part)
        original_shapes = dict(merge._shapes(original.xml(intro)))
        for name in old_media:
            copy = merge._copy_shape(original_shapes[name], original, intro, original, part)
            merge._shape_info(copy).set('id', str(merge._new_shape_id(root)))
            merge._shape_info(copy).set('name', 'School copy of ' + name)
            root.find('p:cSld/p:spTree', merge.NS).append(copy)
        original.put(part, root)
    saved = merge.mark_new_deck(original.save(), snapshot)
    expected_extra = original.read(other), original.read(merge._rels(other))
    before = None
    for _ in range(2):
        saved = merge.merge_deck(saved, current, snapshot)
        result = merge.Package(saved)
        assert (result.read(other), result.read(merge._rels(other))) == expected_extra
        assert len([n for n in result.names if n.endswith('.mp4')]) == 2
        for name, previous in old_media.items():
            assert asset_bytes(result, intro, name) != previous
            for part in (intro, other):
                school_copy = dict(merge._shapes(result.xml(part)))['School copy of ' + name]
                for tag, attribute, _ in merge.BOOKEND_LINKS[name]:
                    rid = next(school_copy.iter(tag)).get(f'{{{merge.R}}}' + attribute)
                    path = merge._resolve(part, result.relations(part)[rid].get('Target'))
                    assert result.read(path) == previous
        if before is not None:
            assert before == result.names
        before = result.names


def test_replaced_video_and_picture_are_kept_independently(previous_line_media, snapshot):
    current, prior, _ = previous_line_media
    source = merge.Package(current)
    original = merge.Package(merge.mark_new_deck(prior, snapshot))
    programs = merge._names(original)
    personal = {'intro': (merge.SIGNATURE_FILM, 'ppt/media/teacher.mp4', b'school film'),
                'outro': (merge.MORPH_MARK, 'ppt/media/teacher.png', b'school picture')}
    for role, (name, path, data) in personal.items():
        part = programs[role][1]
        old, refs = merge._bookend_links(original, part, name)
        original.put(path, data)
        original.declare(path, original.content_type(old))
        for node, key, rel in refs:
            node.set(key, original.link(part, rel.get('Type'), path))
        original.put(part, original.xml(part))
    saved = original.save()
    for _ in range(2):
        saved = merge.merge_deck(saved, current, snapshot)
        result = merge.Package(saved)
        for role, (custom_name, _, custom_bytes) in personal.items():
            part = programs[role][1]
            unchanged_name, = (n for n in merge.BOOKEND_LINKS if n != custom_name)
            assert asset_bytes(result, part, custom_name) == custom_bytes
            assert asset_bytes(result, part, unchanged_name) == asset_bytes(source, merge._names(source)[role][1], unchanged_name)
        assert merge._named_timing(result.xml(programs['intro'][1])) == merge.PREVIOUS_BOOKEND_TIMING
        assert merge._named_timing(result.xml(programs['outro'][1])) == merge._named_timing(source.xml(programs['outro'][1]))
        assert {n.get('advTm') for n in result.xml(programs['intro'][1]).xpath('.//p:transition', namespaces=merge.NS)} == {'3500'}


@pytest.mark.parametrize('registered', [False, True])
def test_quicker_tutorial_keeps_custom_playback_and_retargets_renumbered_stock(previous_line_media, snapshot, registered):
    current, old, media = previous_line_media
    if registered:
        package = merge.Package(merge.mark_new_deck(old, snapshot))
        state = merge._state(package)
        for role in ('intro', 'outro'):
            state[role].pop('bookend_timing')  # Older registries tracked only the ID-specific signature.
        merge._save_state(package, state)
        old = package.save()
    doc = Presentation(BytesIO(old))
    intro = slide_by_role(doc, 'gp.intro')
    intro._element.xpath('.//p:cmd/p:cBhvr/p:cTn')[0].set('dur', '6700')
    custom_timing = merge._named_timing(intro._element)
    outro = slide_by_role(doc, 'gp.outro')
    outro.shapes.add_textbox(Pt(24), Pt(340), Pt(660), Pt(35)).text = 'School presentation cue'
    for shape in outro.shapes:
        props = merge._shape_info(shape._element)
        props.set('id', str(int(props.get('id')) + 40))
    for node in outro._element.xpath('.//p:timing//*[@spid]'):
        node.set('spid', str(int(node.get('spid')) + 40))
    for transition in outro._element.xpath('.//p:transition'):
        transition.set('advTm', '4050' if not registered else '7000')
    expected = merge.Package(current)
    edited = save(doc)
    for _ in range(2):
        edited = merge.merge_deck(edited, current, snapshot)
        result = merge.Package(edited)
        roles = merge._names(result)
        intro, outro = roles['intro'][1], roles['outro'][1]
        assert merge._named_timing(result.xml(intro)) == custom_timing
        assert asset_bytes(result, intro, merge.SIGNATURE_FILM) == media[merge.SIGNATURE_FILM]
        assert asset_bytes(result, intro, merge.MORPH_MARK) == media[merge.MORPH_MARK]
        assert {t.get('advTm') for t in result.xml(intro).xpath('.//p:transition', namespaces=merge.NS)} == {'3500'}
        assert merge._named_timing(result.xml(outro)) == merge._named_timing(expected.xml(merge._names(expected)['outro'][1]))
        assert asset_bytes(result, outro, merge.SIGNATURE_FILM) == asset_bytes(expected, merge._names(expected)['outro'][1], merge.SIGNATURE_FILM)
        assert {t.get('advTm') for t in result.xml(outro).xpath('.//p:transition', namespaces=merge.NS)} == {'7000' if registered else '2283'}
        assert 'School presentation cue' in result.xml(outro).xpath('.//a:t/text()', namespaces=merge.NS)
