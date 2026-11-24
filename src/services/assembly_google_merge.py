"""Plan revision-guarded Google Slides updates from a fresh native conversion.

Google normalizes object sizes and text metrics on import. Work in the native
coordinate system so editable text and graphics stay aligned with the download.
"""
import math
import re
from uuid import uuid4


class GoogleMergeError(ValueError):
    pass


ROLES = ('overview', 'intro', 'breakdown', 'comparison', 'rates', 'winner', 'reminders', 'signoff', 'outro')
OPTIONAL = {'breakdown', 'comparison', 'rates'}
NOTES_START, NOTES_END = '[Golden Plate results]', '[/Golden Plate results]'
INACTIVE = '[gp-session-slide-inactive]'
MOTION_ONLY = '[gp-motion-only]'
API_TEXT_FRAME = '[gp-native-text-frame]'
# Imported PowerPoint text boxes have zero insets. The Slides API does not
# expose insets and adds 6.75 pt on each edge to boxes it creates.
NATIVE_TEXT_INSET = 6.75 * 12700
LEGACY_NOTES = {
    'overview': 'Start with the number of clean plates the school has recorded.',
    'breakdown': 'Each segment shows its category',
    'comparison': 'Compare the number of plates alongside the clean-plate rate.',
    'rates': 'Read both clean-plate rates on the same scale.',
    'reminders': 'Students can stop eating when they feel full.',
}
PHOTO_SLOTS = {'gp.winner.photo.left': 'student', 'gp.winner.photo.right': 'faculty'}


def _new_id():
    return 'gp_' + uuid4().hex


def _parts(element):
    return element.get('shape', {}).get('text', {}).get('textElements', [])


def _text(element):
    content = ''.join(part.get('textRun', {}).get('content', '') for part in _parts(element))
    return content.removesuffix('\n')


def _notes(page):
    notes = page.get('slideProperties', {}).get('notesPage', {})
    ident = notes.get('notesProperties', {}).get('speakerNotesObjectId')
    speaker = next((obj for obj in notes.get('pageElements', []) if obj.get('objectId') == ident), {})
    return ident, _text(speaker)


def _marked(page):
    found = {}
    role = None
    for obj in page.get('pageElements', []):
        prefix, _, rest = obj.get('title', '').partition('.')
        name, _, key = rest.partition('.')
        if prefix != 'gp' or name not in ROLES or not key:
            continue
        if key in found or (role is not None and role != name):
            raise GoogleMergeError('More than one object matches a Golden Plate field. Keep its original alt title on just one object.')
        role = name
        found[key] = obj
    return role, found


def _ownership(page_id):
    return f'[gp-slide-owner:{page_id}]'


def _anchor(fields):
    return next((key for key in ('school', 'winner_title', 'title', 'Be Green') if key in fields), next(iter(fields)))


def _owned(page, fields):
    return any(_ownership(page['objectId']) in field.get('description', '') for field in fields.values())


def _native_pages(doc, *, source=False):
    candidates = {}
    for page in doc.get('slides', []):
        role, fields = _marked(page)
        if role:
            candidates.setdefault(role, []).append((page, fields))
        elif source:
            raise GoogleMergeError('Google did not preserve the assembly layout markers. The linked presentation was kept.')
        if source and len(fields) != len(page.get('pageElements', [])):
            raise GoogleMergeError('Google could not identify every field in the new assembly layout.')
    result = {}
    for role, options in candidates.items():
        # Duplicating a slide copies its alt text, but changes its slide ID.
        # Only the original has an ownership stamp matching its own native ID.
        owners = [(page, fields) for page, fields in options if _owned(page, fields)]
        if len(options) == 1:
            result[role] = options[0]
        elif not source and len(owners) == 1:
            result[role] = owners[0]
        else:
            raise GoogleMergeError('Two slides have the same unregistered Golden Plate fields. Clear the managed alt titles on the extra copy to resume updates.')
    if source and (set(ROLES) - OPTIONAL - result.keys()):
        raise GoogleMergeError('The new Google assembly is missing a required slide.')
    return result


def _legacy_role(page):
    _, notes = _notes(page)
    for role, prefix in LEGACY_NOTES.items():
        if any(line.startswith(prefix) for line in notes.splitlines()):
            return role
    texts = {_text(obj) for obj in page.get('pageElements', [])}
    if {'Be Green,', 'Do Good'} <= texts or {'Be Green', 'Do Good'} <= texts:
        return 'signoff'


def _measure(dim):
    unit = dim.get('unit', 'EMU')
    if unit not in ('PT', 'EMU'):
        raise GoogleMergeError('The Google presentation has an unsupported page measurement.')
    return dim.get('magnitude', 0) * (12700 if unit == 'PT' else 1)


def _geometry(obj, *, original=None):
    size = obj['size']
    old = original['size'] if original else size
    w, h = (_measure(size[key]) / _measure(old[key]) for key in ('width', 'height'))
    t = obj.get('transform', {})
    unit = t.get('unit', 'EMU')
    # Protobuf omits zero scalar values. scaleX/scaleY default to zero in
    # partial transform objects; an omitted transform is the identity.
    identity = 1 if not t else 0
    return dict(scaleX=t.get('scaleX', identity) * w, scaleY=t.get('scaleY', identity) * h,
                shearX=t.get('shearX', 0) * h, shearY=t.get('shearY', 0) * w,
                translateX=_measure({'magnitude': t.get('translateX', 0), 'unit': unit}),
                translateY=_measure({'magnitude': t.get('translateY', 0), 'unit': unit}), unit='EMU')


def _api_text_frame(obj):
    transform = _geometry(obj)
    w, h = (_measure(obj['size'][axis]) for axis in ('width', 'height'))
    transform['scaleX'] += 2 * NATIVE_TEXT_INSET / w
    transform['scaleY'] += 2 * NATIVE_TEXT_INSET / h
    transform['translateX'] -= NATIVE_TEXT_INSET
    transform['translateY'] -= NATIVE_TEXT_INSET
    return {**obj, 'transform': transform}


def _same_frame(a, b):
    if not a.get('size') or not b.get('size'):
        return False
    first, second = _geometry(a, original=b), _geometry(b)
    return all(math.isclose(first[k], second[k], rel_tol=1e-5,
                            abs_tol=1270 if k.startswith('translate') else 1e-5) for k in first if k != 'unit')


def _pick(value, fields):
    return {name: value[name] for name in fields if name in value}


def _update(kind, ident, key, props):
    return {kind: {'objectId': ident, key: props, 'fields': ','.join(props)}}


def _alt(obj, ident, description=None):
    return {'updatePageElementAltText': {'objectId': ident, 'title': obj['title'],
                                         'description': obj.get('description', '') if description is None else description}}


def _text_requests(ident, old, new):
    result = []
    before, after = _text(old), _text(new)
    if before != after:
        if before:
            result.append({'deleteText': {'objectId': ident, 'textRange': {'type': 'ALL'}}})
        if after:
            result.append({'insertText': {'objectId': ident, 'text': after, 'insertionIndex': 0}})
    if not after:
        return result
    limit = len(after.encode('utf-16-le')) // 2
    for category, method, allowed in (
        ('textRun', 'updateTextStyle',
         ('fontFamily', 'weightedFontFamily', 'fontSize', 'foregroundColor', 'bold', 'italic', 'underline',
          'strikethrough', 'smallCaps', 'baselineOffset', 'backgroundColor')),
        ('paragraphMarker', 'updateParagraphStyle',
         ('alignment', 'lineSpacing', 'spaceAbove', 'spaceBelow', 'indentStart', 'indentEnd', 'indentFirstLine',
          'spacingMode', 'direction')),
    ):
        def ranges(element):
            return [(part.get('startIndex', 0), part.get('endIndex', limit + 1),
                     _pick(part[category].get('style', {}), allowed)) for part in _parts(element) if category in part]

        prior, desired = ranges(old), ranges(new)
        if not desired or (before == after and prior == desired):
            continue
        fields = set().union(*(style.keys() for _, _, style in prior + desired))
        if not fields:
            continue
        # Style the mandatory final newline through ALL, then override individual
        # runs/paragraphs using the native UTF-16 ranges. This reproduces mixed
        # sizes, colors, emphasis and leading in the two Quick Reminders blocks.
        base = desired[-1][2]
        common = {'objectId': ident, 'fields': ','.join(sorted(fields))}
        result.append({method: {**common, 'textRange': {'type': 'ALL'}, 'style': base}})
        for start, end, style in desired:
            end = min(end, limit)
            if start < end and style != base:
                result.append({method: {**common, 'style': style,
                                        'textRange': {'type': 'FIXED_RANGE', 'startIndex': start, 'endIndex': end}}})
    return result


def _image_url(obj):
    url = obj['image'].get('contentUrl', '')
    if not url.startswith('https://'):
        raise GoogleMergeError('Google did not return the image needed for the new assembly layout.')
    return url


def _template_hash(obj):
    return next(iter(re.findall(r'\[gp-template:([0-9a-f]{16})\]', obj.get('description', ''))), None)


def _award(obj):
    return next(iter(re.findall(r'\[gp-award:(none|[0-9a-f]{64})\]', obj.get('description', ''))), None)


def _object_requests(old, new, page_id, *, photos_changed=False):
    ident = old['objectId'] if old else _new_id()
    result = []
    description = new.get('description', '')
    layout = new
    if new.get('shape', {}).get('shapeType') == 'TEXT_BOX' and (
            not old or API_TEXT_FRAME in old.get('description', '')):
        layout = _api_text_frame(new)
        description = (description + ' ' + API_TEXT_FRAME).strip()
    if not old:
        props = {'pageObjectId': page_id, 'size': layout['size'], 'transform': _geometry(layout)}
        if 'image' in new:
            result.append({'createImage': {'objectId': ident, 'elementProperties': props, 'url': _image_url(new)}})
        elif new.get('shape', {}).get('shapeType') in {'TEXT_BOX', 'RECTANGLE', 'ROUND_RECTANGLE', 'ELLIPSE'}:
            result.append({'createShape': {'objectId': ident, 'elementProperties': props, 'shapeType': new['shape']['shapeType']}})
        else:
            raise GoogleMergeError('The new assembly contains an unsupported Google object. The original presentation was kept.')
    elif not _same_frame(layout, old):
        result.append({'updatePageElementTransform': {'objectId': ident, 'applyMode': 'ABSOLUTE',
                                                      'transform': _geometry(layout, original=old)}})
    if 'image' in new:
        if old and photos_changed:
            result.append({'replaceImage': {'imageObjectId': ident, 'url': _image_url(new),
                                            'imageReplaceMethod': 'CENTER_INSIDE'}})
    else:
        fields = ('shapeBackgroundFill', 'outline', 'contentAlignment')
        props = _pick(new['shape'].get('shapeProperties', {}), fields)
        if props and props != _pick((old or {}).get('shape', {}).get('shapeProperties', {}), fields):
            result.append(_update('updateShapeProperties', ident, 'shapeProperties', props))
        result.extend(_text_requests(ident, old or {}, new))
    if not old or old.get('title') != new['title'] or old.get('description', '') != description:
        result.append(_alt(new, ident, description))
    return result, ident


def _skip(page, value):
    return _update('updateSlideProperties', page['objectId'], 'slideProperties', {'isSkipped': value})


def _update_notes(ident, old, fresh):
    if not fresh:
        return []
    if NOTES_START not in fresh or NOTES_END not in fresh:
        raise GoogleMergeError('The new assembly speaker notes have no update markers.')
    if old.count(NOTES_START) == old.count(NOTES_END) == 1 and old.index(NOTES_START) < old.index(NOTES_END):
        before, _, tail = old.partition(NOTES_START)
        _, _, after = tail.partition(NOTES_END)
        updated = before + fresh + after
    elif NOTES_START in old or NOTES_END in old:
        raise GoogleMergeError('Repair the Golden Plate speaker-note markers on the linked slide to resume updates.')
    else:
        updated = (old + '\n\n' if old else '') + fresh
    if updated == old:
        return []
    if not ident:
        raise GoogleMergeError('Google could not identify the speaker notes on the linked slide.')
    # Replace only our section, preserving any teacher formatting outside it.
    start = len(before.encode('utf-16-le')) // 2 if NOTES_START in old else len(old.encode('utf-16-le')) // 2
    ops = []
    if NOTES_START in old:
        end = len(old[:old.index(NOTES_END) + len(NOTES_END)].encode('utf-16-le')) // 2
        ops.append({'deleteText': {'objectId': ident, 'textRange': {'type': 'FIXED_RANGE', 'startIndex': start, 'endIndex': end}}})
    addition = fresh if NOTES_START in old or not old else '\n\n' + fresh
    ops.append({'insertText': {'objectId': ident, 'insertionIndex': start, 'text': addition}})
    return ops


def initialize_native_pages(saved):
    pages = _native_pages(saved, source=True)
    requests = []
    for role, (page, fields) in pages.items():
        anchor = fields[_anchor(fields)]
        if not _owned(page, fields):
            requests.append(_alt(anchor, anchor['objectId'],
                                 (anchor.get('description', '') + ' ' + _ownership(page['objectId'])).strip()))
        if (role in OPTIONAL and any(INACTIVE in obj.get('description', '') for obj in fields.values())
                and not page.get('slideProperties', {}).get('isSkipped')):
            requests.append(_skip(page, True))
    return requests


def _winner_photo(role, previous, desired, fields, page, page_width):
    # Replace image retains the original title. An independently pasted image
    # can occupy precisely the same frame instead, or sit on top of it.
    matching = [obj for obj in page.get('pageElements', []) if 'image' in obj
                and not obj.get('title', '').startswith('gp.') and _same_frame(desired, obj)]
    if len(matching) > 1:
        raise GoogleMergeError('More than one photo occupies the same winner frame. Keep one photo in the frame to resume updates.')
    overlay = next(iter(matching), None)
    if not previous:
        previous, overlay = overlay, None
    if not previous:
        return None, False, None
    old_award = _award(previous) or _award(fields.get('winner_name_' + role, {}))
    changed = not old_award or old_award != _award(desired)
    parked = None
    if changed and overlay:
        # Keep the separate photo editable offstage when the award changes.
        frame = _geometry(overlay)
        frame['translateX'] = page_width + 12700
        parked = {'updatePageElementTransform': {'objectId': overlay['objectId'], 'applyMode': 'ABSOLUTE', 'transform': frame}}
    return previous, changed, parked


def _field_requests(page, page_id, fields, desired, page_width):
    requests = []
    layer_ids, restack = [], False
    anchor_key = _anchor(desired)
    for key, obj in desired.items():
        # The Slides API cannot attach a timing sequence to an object it
        # creates. Only update these temporary playback frames when they
        # already exist with their imported entrance and exit cues.
        if key not in fields and MOTION_ONLY in obj.get('description', ''):
            continue
        if key == anchor_key:
            caption = re.sub(r' *\[gp-slide-owner:[A-Za-z0-9_:-]+\]', '', obj.get('description', ''))
            obj = {**obj, 'description': (caption + ' ' + _ownership(page_id)).strip()}
        previous = fields.get(key)
        photo_role = PHOTO_SLOTS.get(key)
        changed = False
        if photo_role:
            previous, changed, parked = _winner_photo(photo_role, previous, obj, fields, page, page_width)
            if parked:
                requests.append(parked)
        if previous and not changed and previous.get('title') == obj['title']:
            before, after = _template_hash(previous), _template_hash(obj)
            original_desc = previous.get('description', '').removesuffix(API_TEXT_FRAME).rstrip()
            if after and before == after and original_desc == obj.get('description', ''):
                # The source field is unchanged: retain manual typography,
                # position, animations and any teacher-authored copy.
                layer_ids.append(previous['objectId'])
                continue
            if 'image' in obj and not photo_role and before and after and before != after:
                media = r'\[gp-image:([0-9a-f]{16})\]'
                before_media = re.findall(media, previous.get('description', ''))
                after_media = re.findall(media, obj.get('description', ''))
                changed = not after_media or before_media != after_media
        if previous and (('image' in previous) != ('image' in obj)
                         or previous.get('shape', {}).get('shapeType') != obj.get('shape', {}).get('shapeType')):
            requests.append({'deleteObject': {'objectId': previous['objectId']}})
            previous = None
        ops, ident = _object_requests(previous, obj, page_id, photos_changed=changed)
        requests.extend(ops)
        layer_ids.append(ident)
        restack |= previous is None
    for key in fields.keys() - desired.keys():
        requests.append({'deleteObject': {'objectId': fields[key]['objectId']}})
    if page and restack:
        # Put managed objects under teacher-added overlays in their exact
        # source order; selective bar additions must not cover captions.
        requests.extend({'updatePageElementsZOrder': {'pageElementObjectIds': [ident], 'operation': 'SEND_TO_BACK'}}
                        for ident in reversed(layer_ids))
    return requests


def plan_update(saved, fresh):
    """Return native batchUpdate requests and notes for server-assigned new notes IDs."""
    source, current = _native_pages(fresh, source=True), _native_pages(saved)
    if not saved.get('slides') or not saved.get('revisionId'):
        raise GoogleMergeError('Google did not confirm the current editable version of the presentation.')
    ids = [page['objectId'] for page in saved['slides']]
    page_width = _measure(saved.get('pageSize', {}).get('width', {'unit': 'PT', 'magnitude': 960}))
    requests, pending_notes = [], {}
    # Earlier Google exports began with a skipped cover. Move that original
    # leading pair once, preserving teacher introductions and custom ordering.
    if 'intro' in current and 'overview' in current and source['intro'][0].get('slideProperties', {}).get('isSkipped'):
        cover, overview = current['intro'][0], current['overview'][0]
        if ids[:2] == [cover['objectId'], overview['objectId']]:
            requests.append({'updateSlidesPosition': {'slideObjectIds': [overview['objectId']], 'insertionIndex': 0}})
            ids[:2] = [overview['objectId'], cover['objectId']]
            if not cover.get('slideProperties', {}).get('isSkipped'):
                requests.append(_skip(cover, True))
    legacy = {}
    if not current:
        for page in saved['slides']:
            role = _legacy_role(page)
            if role and role not in legacy:
                legacy[role] = page['objectId']
                if not page.get('slideProperties', {}).get('isSkipped'):
                    requests.append(_skip(page, True))
        if not legacy:
            raise GoogleMergeError('The original Golden Plate slides could not be identified. Restore a managed slide to resume updates.')
    positions = {**legacy, **{r: page['objectId'] for r, (page, _) in current.items()}}
    for index, role in enumerate(ROLES):
        page, fields = current.get(role, ({}, {}))
        if role not in source:
            if role in OPTIONAL and fields:
                anchor = next(iter(fields.values()))
                if INACTIVE not in anchor.get('description', ''):
                    requests.extend([_skip(page, True), _alt(anchor, anchor['objectId'], anchor.get('description', '') + '\n' + INACTIVE)])
            continue
        fresh_page, desired = source[role]
        if page:
            page_id = page['objectId']
            inactive = any(INACTIVE in obj.get('description', '') for obj in desired.values())
            was_inactive = any(INACTIVE in obj.get('description', '') for obj in fields.values())
            is_skipped = page.get('slideProperties', {}).get('isSkipped', False)
            if role in OPTIONAL and ((inactive and not is_skipped) or (was_inactive and not inactive and is_skipped)):
                requests.append(_skip(page, inactive))
        else:
            page_id = _new_id()
            next_anchor = next((positions[r] for r in ROLES[index:] if r in positions), None)
            previous = next((positions[r] for r in reversed(ROLES[:index]) if r in positions), None)
            insert_at = ids.index(next_anchor) if next_anchor else (ids.index(previous) + 1 if previous else len(ids))
            requests.append({'createSlide': {'objectId': page_id, 'insertionIndex': insert_at,
                                             'slideLayoutReference': {'predefinedLayout': 'BLANK'}}})
            ids.insert(insert_at, page_id)
            if (role == 'intro' and fresh_page.get('slideProperties', {}).get('isSkipped')
                    or role in OPTIONAL and any(INACTIVE in obj.get('description', '') for obj in desired.values())):
                requests.append(_skip({'objectId': page_id}, True))
            background = fresh_page.get('pageProperties', {}).get('pageBackgroundFill')
            if background:
                requests.append(_update('updatePageProperties', page_id, 'pageProperties', {'pageBackgroundFill': background}))
        positions[role] = page_id
        requests.extend(_field_requests(page, page_id, fields, desired, page_width))
        _, note = _notes(fresh_page)
        if note:
            if page:
                note_id, old_note = _notes(page)
                requests.extend(_update_notes(note_id, old_note, note))
            else:
                pending_notes[page_id] = note
    return requests, pending_notes


def notes_after_creation(saved, pending):
    pages = {page['objectId']: page for page in saved.get('slides', [])}
    if not set(pending) <= pages.keys():
        raise GoogleMergeError('The new Google slides changed while updating. The next sync will read the latest version.')
    return [op for ident, note in pending.items() for op in _update_notes(*_notes(pages[ident]), note)]
