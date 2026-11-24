from copy import deepcopy

import pytest

from assembly_google_fixtures import native_deck, notes, registered, textbox
from src.services import assembly_google_merge as merge


def by_role(doc, role):
    return next(page for page in doc['slides'] if page['objectId'] == 'slide_' + role)


def image(ident, title, description=''):
    obj = textbox(ident, title, '')
    obj.pop('shape')
    obj.update(image={'contentUrl': 'https://images.example/' + ident}, description=description)
    return obj


def test_noop_keeps_user_slides_notes_static_copy_and_visual_edits():
    saved, source = native_deck(), native_deck()
    saved['slides'].insert(2, {'objectId': 'personal', 'pageElements': [textbox('handout', 'My examples', 'Lunch')]})
    before = by_role(saved, 'reminders')
    after = by_role(source, 'reminders')
    for obj in [before, after]:
        obj['pageElements'][0]['description'] = '[gp-template:fedcba0011223344]'
    before['pageElements'][0]['shape']['text']['textElements'][1]['textRun']['content'] = 'Teacher’s wording\n'
    before['pageElements'][0]['transform']['translateY'] = 12000
    before['pageElements'].append(textbox('bonus', 'My extra reminder', 'Preview'))
    before['slideProperties']['notesPage'] = notes('slide_reminders', 'Opening\n' + merge._notes(after)[1] + '\nClosing')
    for page in saved['slides']:
        if page['objectId'] != 'personal':
            obj = page['pageElements'][0]
            obj['description'] = (obj['description'] + ' ' + merge._ownership(page['objectId'])).strip()
    assert merge.plan_update(saved, source) == ([], {})


@pytest.mark.parametrize('changed,untagged', [(False, False), (True, False), (False, True), (True, True)])
def test_winner_photo_follows_the_actual_award_with_or_without_imported_title(changed, untagged):
    saved, source = native_deck(), native_deck()
    old_key = 'a' * 64
    for doc, award in [(saved, old_key), (source, 'b' * 64 if changed else old_key)]:
        page = by_role(doc, 'winner')
        suffix = ' [gp-award:' + award + ']'
        page['pageElements'].append(textbox('student', 'gp.winner.winner_name_student', 'Same-name student', suffix))
        obj = image('studentPhoto', 'gp.winner.gp.winner.photo.left', 'Student winner photo' + suffix)
        if doc is saved and untagged:
            obj['title'] = obj['description'] = ''
        if doc is saved:
            obj['image']['contentUrl'] = 'https://teacher.example/private-photo'
        page['pageElements'].append(obj)
    ops, _ = merge.plan_update(saved, source)
    swaps = [req['replaceImage'] for req in ops if 'replaceImage' in req]
    assert len(swaps) == int(changed)
    if changed:
        assert swaps[0]['imageObjectId'] == 'studentPhoto' and swaps[0]['url'] == 'https://images.example/studentPhoto'
    assert 'teacher.example' not in str(ops)
    assert not any('deleteObject' in req or 'createImage' in req for req in ops)


def test_saved_cover_first_deck_opens_on_results_after_refresh():
    saved, fresh = registered(native_deck()), native_deck()
    by_role(fresh, 'intro')['slideProperties']['isSkipped'] = True
    saved['slides'][0], saved['slides'][1] = saved['slides'][1], saved['slides'][0]
    before = deepcopy(saved)
    ops, _ = merge.plan_update(saved, fresh)
    assert {'updateSlidesPosition': {'slideObjectIds': ['slide_overview'], 'insertionIndex': 0}} in ops
    assert merge._skip(by_role(saved, 'intro'), True) in ops
    # Adding an introduction before the managed pair is an explicit teacher choice.
    before['slides'].insert(0, {'objectId': 'teacher-opening', 'pageElements': []})
    ops, _ = merge.plan_update(before, fresh)
    assert not any('updateSlidesPosition' in op for op in ops)


def test_preserves_generated_notes_boundary_and_utf16_offsets_for_custom_notes():
    start, end = merge.NOTES_START, merge.NOTES_END
    old, new = f'🎉 Teacher\n{start}\n135\n{end}\nDebrief', f'{start}\n149\n{end}'
    ops = merge._update_notes('speaker', old, new)
    cut, paste = ops[0]['deleteText']['textRange'], ops[1]['insertText']
    assert cut['startIndex'] == len('🎉 Teacher\n'.encode('utf-16-le')) // 2
    assert cut['endIndex'] - cut['startIndex'] == len(f'{start}\n135\n{end}')
    assert paste['insertionIndex'] == cut['startIndex'] and paste['text'] == new
    with pytest.raises(merge.GoogleMergeError):
        merge._update_notes('speaker', f'{start} without end', new)


def test_optional_seeded_slides_toggle_and_leave_other_manual_skips_intact():
    saved, source = native_deck(), native_deck()
    old = by_role(saved, 'rates')
    new = by_role(source, 'rates')
    new['pageElements'][0]['description'] = merge.INACTIVE
    assert [op for op in merge.initialize_native_pages(source) if 'updateSlideProperties' in op] == [merge._skip(new, True)]
    ops, _ = merge.plan_update(saved, source)
    assert merge._skip(old, True) in ops
    old['pageElements'][0]['description'] = merge.INACTIVE
    old['slideProperties']['isSkipped'] = True
    new['pageElements'][0]['description'] = ''
    by_role(saved, 'comparison')['slideProperties']['isSkipped'] = True
    ops, _ = merge.plan_update(saved, source)
    assert [r for r in ops if 'updateSlideProperties' in r] == [merge._skip(old, False)]


def test_legacy_upgrade_keeps_original_slides_custom_slide_and_notes():
    original = {'objectId': 'old_overview', 'pageElements': [textbox('custom_photo_caption', '', 'My class')],
                'slideProperties': {'notesPage': notes('old_overview', merge.LEGACY_NOTES['overview'] + ' teacher cue')}}
    teacher = {'objectId': 'teacher_slide', 'pageElements': [textbox('custom', '', 'Take the survey')]}
    saved = {'revisionId': 'rev', 'slides': [teacher, original]}
    source = native_deck()
    ops, pending = merge.plan_update(saved, source)
    assert [r for r in ops if 'updateSlideProperties' in r] == [merge._skip(original, True)]
    assert not any('deleteObject' in r for r in ops)
    assert 'teacher_slide' not in str(ops) and 'custom_photo_caption' not in str(ops)
    assert [r['createSlide']['insertionIndex'] for r in ops if 'createSlide' in r][:2] == [1, 2]
    assert len(pending) == 9
    new = {'slides': [{'objectId': ident, 'slideProperties': {'notesPage': notes(ident, '')}} for ident in pending]}
    assert len(merge.notes_after_creation(new, pending)) == 9


def test_mixed_type_in_reminder_uses_native_utf16_ranges_and_paragraph_styles():
    new = textbox('new', 'gp.reminders.Portion choice', '')
    new['shape']['text']['textElements'] = [
        {'endIndex': 3, 'paragraphMarker': {'style': {'alignment': 'START'}}},
        {'endIndex': 2, 'textRun': {'content': '🎉', 'style': {'bold': True, 'fontSize': {'unit': 'PT', 'magnitude': 51}}}},
        {'startIndex': 2, 'endIndex': 3, 'textRun': {'content': '\n', 'style': {'bold': False}}},
        {'startIndex': 3, 'endIndex': 8, 'paragraphMarker': {'style': {'alignment': 'CENTER'}}},
        {'startIndex': 3, 'endIndex': 7, 'textRun': {'content': 'more', 'style': {'italic': True}}},
        {'startIndex': 7, 'endIndex': 8, 'textRun': {'content': '\n', 'style': {'bold': False}}},
    ]
    ops = merge._text_requests('original', {}, new)
    assert ops[0]['insertText']['text'] == '🎉\nmore'
    runs = [r['updateTextStyle'] for r in ops if 'updateTextStyle' in r]
    assert any(r['style'].get('bold') and r['textRange']['endIndex'] == 2 for r in runs)
    assert any(r['style'].get('italic') and r['textRange']['startIndex'] == 3 for r in runs)
    paragraphs = [r['updateParagraphStyle'] for r in ops if 'updateParagraphStyle' in r]
    assert any(p['textRange'] == {'type': 'ALL'} and p['style']['alignment'] == 'CENTER' for p in paragraphs)
    assert any(p['textRange'].get('endIndex') == 3 and p['style']['alignment'] == 'START' for p in paragraphs)


def test_timed_frame_updates_in_place_only_if_it_already_has_its_imported_timing():
    saved, fresh = registered(native_deck()), native_deck()
    frame = textbox('fresh_frame', 'gp.rates.bar motion frame 01', '25', merge.MOTION_ONLY)
    by_role(fresh, 'rates')['pageElements'].append(frame)
    operations, _ = merge.plan_update(saved, fresh)
    assert not any('createShape' in r or 'createImage' in r for r in operations)
    existing = deepcopy(frame)
    existing['objectId'] = 'imported_with_entrance'
    existing['shape']['text']['textElements'][1]['textRun']['content'] = '17\n'
    by_role(saved, 'rates')['pageElements'].append(existing)
    operations, _ = merge.plan_update(saved, fresh)
    assert any(r.get('insertText', {}).get('objectId') == existing['objectId'] for r in operations)
    assert not any('deleteObject' in r or 'createShape' in r for r in operations)


def test_duplicate_managed_slides_or_unmarked_source_fail_before_writing():
    for scope in ('saved', 'source'):
        saved, source = native_deck(), native_deck()
        if scope == 'saved':
            saved['slides'].append(deepcopy(saved['slides'][0]))
        else:
            source['slides'][0]['pageElements'][0].pop('title')
        with pytest.raises(merge.GoogleMergeError):
            merge.plan_update(saved, source)


def test_teacher_copy_of_managed_slide_can_precede_original_without_stealing_updates():
    saved, source = registered(native_deck()), native_deck()
    original = by_role(saved, 'winner')
    duplicate = deepcopy(original)
    duplicate['objectId'] = 'teachers_copy'
    duplicate['pageElements'][0]['objectId'] = 'teachers_object'
    saved['slides'].insert(0, duplicate)
    by_role(source, 'winner')['pageElements'][0]['shape']['text']['textElements'][1]['textRun']['content'] = 'New winner\n'
    ops, _ = merge.plan_update(saved, source)
    assert any(op.get('insertText', {}).get('objectId') == 'winner_value' for op in ops)
    assert 'teachers_copy' not in str(ops) and 'teachers_object' not in str(ops)


def test_separately_pasted_photo_in_the_old_winner_slot_is_kept_offstage_on_rotation():
    saved, source = native_deck(), native_deck()
    for doc, award in [(saved, 'a' * 64), (source, 'b' * 64)]:
        by_role(doc, 'winner')['pageElements'].append(image('slot', 'gp.winner.gp.winner.photo.left',
                                                           '[gp-award:' + award + ']'))
    by_role(saved, 'winner')['pageElements'].append(image('manual_photo', 'Raffle winner'))
    ops, _ = merge.plan_update(saved, source)
    parked = [op['updatePageElementTransform'] for op in ops if op.get('updatePageElementTransform', {}).get('objectId') == 'manual_photo']
    assert len(parked) == 1 and parked[0]['transform']['translateX'] > 960 * 12700
    assert not any(op.get('deleteObject', {}).get('objectId') == 'manual_photo' for op in ops)
