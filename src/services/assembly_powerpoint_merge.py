"""Refresh managed data in a saved OneDrive presentation, retaining its native package."""
from base64 import b32decode, b32encode
from copy import copy, deepcopy
from difflib import SequenceMatcher
from hashlib import sha256
from io import BytesIO
import json
import posixpath
import re
from zipfile import BadZipFile, ZipFile, ZIP_DEFLATED

from lxml import etree as ET

from .presentation_intro import INTRO_MARKER, MORPH_MARK, MORPH_WORDMARK, OUTRO_MARKER, SIGNATURE_FILM


P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
NS = {'p': P, 'a': A, 'r': R}
PRES = 'ppt/presentation.xml'
TYPES = '[Content_Types].xml'
ORDER = ('intro', 'overview', 'latest', 'table', 'chart', 'winner', 'reminders', 'closing', 'outro')
SIGNATURES = {
    'overview': ('all_clean', 'share'), 'latest': ('distribution', 'student_clean'),
    'table': ('prev_total', 'delta_rate'), 'chart': ('prev_track', 'curr_track'),
    'reminders': ('Portion choice', 'Plate count'), 'closing': ('Be Green', 'Do Good'),
}
BRAND_NAMES = {'Plate mark': MORPH_MARK, 'Publisher': MORPH_WORDMARK}
P14 = 'http://schemas.microsoft.com/office/powerpoint/2010/main'
MC = 'http://schemas.openxmlformats.org/markup-compatibility/2006'
WINNERS = {'student': '21', 'faculty': '22'}
DIRTY_LABELS = ('Dirty plates label', 'Very dirty plates label')
# These names are persistent PowerPoint object IDs shared with the animation
# builder. Match only their shipped copy, leaving school-written names intact.
COMPARISON_LABELS = {'Previous lunch label': ('Previous lunch', 'Previous session'),
                     'Latest lunch label': ('Latest lunch', 'Latest session')}
LEGACY_SESSION_LABELS = {
    'overview': {'latest_heading': ('Latest lunch', 'Latest session')},
    'latest': {'title': ('Latest lunch', 'Latest session')},
    'table': {'title': ('Lunch to lunch', 'Session comparison'), **COMPARISON_LABELS},
    'chart': COMPARISON_LABELS,
}
LEGACY_SESSION_CUES = {
    'overview': 'Start with the number of clean plates the school has recorded. The goal and latest lunch put the total in context. Only lunches with recorded plates count.',
    'latest': 'Each segment shows its category’s share of the plates recorded at this lunch. The clean-plate rate includes both students and faculty.',
    'table': 'Compare the number of plates alongside the clean-plate rate. The rate helps compare lunches when attendance differs.',
    'chart': 'Read both clean-plate rates on the same scale. Each bar shows the share of recorded plates that was clean at that lunch.',
}
COMPARISON_NOTE_RESULT = r'(?:Rate comparison unavailable|No change in clean-plate rate|[\d.]+ percentage points? (?:higher|lower))\.'
TAG = 'GOLDENPLATE_ASSEMBLY_V1'
# Older connected files predate media checksums in the registry. Match the
# previous tutorial and line-animation assets only for the matching theme.
PREVIOUS_BOOKEND_MEDIA = {
    '101A16': {
        SIGNATURE_FILM: {
            'a34130ce04c788aa83234d7325bcfe5307ea4919fceba77af49bba2a2e9f10ee',
            'fbcd4ccc42118bca33ad7a16226e3078ddf7da3d3b12207bc106f19706aee853',
            '2b558742909069ad006a7f47a816bd2922f54f110e85e858a25ba78315b180f3',
            'a152d92c5c3df25f7541752ab30282e81694fe4631d467a2fe94e441788b1834',
        },
        MORPH_MARK: {
            'b21ee27f13639af40550cb9f693da3f54b99c09816fe47f9b119b09b78c84068',
            '141981e2e8bde16d3ddf9dff40ae99052b8131efaafdaf284f22b1721a407d2f',
        },
    },
    'F8F7F0': {
        SIGNATURE_FILM: {
            '7f79b606be9240424dbce6dd86c264fa50e321183ab897fa1b3d524f28e6054c',
            'f5cb4fa89b0051204737227cfc9bf79f15f5141cf17e54d9dff6a7ce40a53c07',
            '52c89430e8e99a4d2098e518eaa95e8c45d5e0125b423d751b0984180466ffe2',
            '6d2cce808456312bf01c5978875dde5489c59238cbb61f7fb1777c1b74f6896a',
        },
        MORPH_MARK: {
            '77f7265c44ad58e19797fc94d34f0098735828a75968cee7a63ffcdcd03404f4',
            '5b021c969b8da700d026407f52871b48861ea876a0c9ca05a9d03b3248939ec1',
        },
    },
}
BOOKEND_LINKS = {
    SIGNATURE_FILM: ((f'{{{A}}}videoFile', 'link', R + '/video'),
                     (f'{{{P14}}}media', 'embed', 'http://schemas.microsoft.com/office/2007/relationships/media')),
    MORPH_MARK: ((f'{{{A}}}blip', 'embed', R + '/image'),),
}
# The previous two-object intro did not track graphic/style baselines. These
# are the shipped native shapes (both themes, the two title widths and both
# stock image resolutions). A teacher's graphic or revision must not be retired.
LEGACY_BRAND = {
    MORPH_MARK: {
        'd8ecba9763ef0fc1bda722037c2e7a0c62835a9e4837511857de2e50aaae4613',
        'f1d168dfa1a1474bad650dfbbd6624e9e26706a3a5c674e160b14a773489b809',
    },
    MORPH_WORDMARK: {
        '590ec8c100257942315c2b841d7ae9c1e7f1e01482b37bc486869cff591d5527',
        'e85473a9e75c68f71a06fe094ad9ab89845d7b3a8948bce3946d8d8b1f9c5ab2',
        'e937a3f5cf0217a913cf24efaebd17405629190e1c5664b91b118f498d9118fa',
        'a19dbf5dd50e2622840255384d85ba4c0d6751022201e3df8f9d45a2d3195a12',
    },
}
LEGACY_INTRO_TIMING = '9b1ebb175fcd119698ebb98d58cbe0b38cf5db148c761a7b8f89e73a6c130c4a'
# The 3.5-second tutorial, gold-line and spiral releases shared this complete
# native playback sequence, independent of the target shapes' PowerPoint IDs.
PREVIOUS_BOOKEND_TIMING = '5b82784480aeff500b6504b5c8552453b3447d87a0fe725c022a85d4aef69cc9'
# The first short reveal handed off to its editable plate at 1,650 ms on both slides.
QUICK_BOOKEND_TIMING = '15bf241138e0b3fa1b058416b3ec3c129873f864ac14f6fc8689813bad07f77b'
# The 1,460 ms intro handoff first shipped with a 450 ms incoming Morph.
EARLY_HANDOFF_TIMING = '925e896bfb172180b5713e4696b4929c22d21d3f07d3d3af0e4496110dd8913c'


class MergeError(ValueError):
    """The original file must be left untouched."""


def _digest(value):
    return sha256(value).hexdigest()


def _signature(element):
    # Office is free to change namespace prefixes and attribute ordering on save.
    if element is None:
        return None
    def content(node):
        return [node.tag, sorted(node.attrib.items()), (node.text or '').strip(),
                [content(child) for child in node if isinstance(child.tag, str)]]
    return _digest(json.dumps(content(element), ensure_ascii=False).encode())


def _rels(part):
    directory, name = posixpath.split(part)
    return posixpath.join(directory, '_rels', name + '.rels')


def _resolve(part, target):
    if target.startswith('/'):
        return target.lstrip('/')
    return posixpath.normpath(posixpath.join(posixpath.dirname(part), target))


def _xml(name):
    return ET.Element(name)


class Package:
    def __init__(self, data):
        self.archive = ZipFile(BytesIO(data))
        entries = self.archive.infolist()
        self.names = set(self.archive.namelist())
        if len(self.names) != len(entries) or any(n.startswith('_xmlsignatures/') for n in self.names):
            raise MergeError('The saved PowerPoint cannot be updated without altering its signed or ambiguous contents.')
        if len(entries) > 12000 or sum(i.file_size for i in entries) > 512 * 1024 * 1024:
            raise MergeError('The presentation is too large to merge safely.')
        if any(i.flag_bits & 1 for i in entries):
            raise MergeError('The protected presentation cannot be updated automatically.')
        self.changed = {}
        self.parsed = {}
        self.media = {}

    def read(self, path):
        if path in self.changed:
            return self.changed[path]
        return self.archive.read(path)

    def xml(self, path):
        if path not in self.parsed:
            self.parsed[path] = ET.fromstring(self.read(path), ET.XMLParser(resolve_entities=False, no_network=True))
        return self.parsed[path]

    def put(self, path, value):
        self.names.add(path)
        if isinstance(value, ET._Element):
            self.parsed[path] = value
            value = ET.tostring(value, encoding='UTF-8', xml_declaration=True, standalone=True)
        self.changed[path] = value

    def relations(self, part):
        path = _rels(part)
        if path not in self.names:
            return {}
        return {r.get('Id'): r for r in self.xml(path)}

    def related(self, part, kind):
        return next((_resolve(part, rel.get('Target')) for rel in self.relations(part).values()
                     if rel.get('Type') == R + '/' + kind), None)

    def link(self, owner, kind, target, *, external=False):
        path = _rels(owner)
        rels = self.xml(path) if path in self.names else _xml(f'{{{REL}}}Relationships')
        relative = target if external else posixpath.relpath(target, posixpath.dirname(owner))
        for relation in rels:
            if (relation.get('Type') == kind and relation.get('TargetMode') == ('External' if external else None)
                    and relation.get('Target') == relative):
                return relation.get('Id')
        used = {r.get('Id') for r in rels}
        n = 1
        while f'rId{n}' in used:
            n += 1
        ident = f'rId{n}'
        rel = ET.SubElement(rels, f'{{{REL}}}Relationship', Id=ident, Type=kind, Target=relative)
        if external:
            rel.set('TargetMode', 'External')
        self.put(path, rels)
        return ident

    def media_part(self, data, extension):
        key = (extension, _digest(data))
        if key not in self.media:
            for path in self.names:
                if path.startswith('ppt/media/') and path.endswith(extension) and _digest(self.read(path)) == key[1]:
                    self.media[key] = path
                    break
        return self.media.get(key)

    def allocate(self, preferred):
        if preferred not in self.names:
            return preferred
        stem, extension = posixpath.splitext(preferred)
        prefix = re.sub(r'\d+$', '', stem)
        n = 1
        while f'{prefix}{n}{extension}' in self.names:
            n += 1
        return f'{prefix}{n}{extension}'

    def content_type(self, path):
        types = self.xml(TYPES)
        for child in types:
            if child.get('PartName') == '/' + path:
                return child.get('ContentType')
        ext = path.rsplit('.', 1)[-1]
        return next(n.get('ContentType') for n in types if n.get('Extension') == ext)

    def declare(self, path, content_type):
        try:
            if self.content_type(path) == content_type:
                return
        except StopIteration:
            pass
        root = self.xml(TYPES)
        ET.SubElement(root, f'{{{CT}}}Override', PartName='/' + path, ContentType=content_type)
        self.put(TYPES, root)

    def slides(self):
        rels = self.relations(PRES)
        return [(int(n.get('id')), _resolve(PRES, rels[n.get(f'{{{R}}}id')].get('Target')))
                for n in self.xml(PRES).find('p:sldIdLst', NS)]

    def save(self):
        output = BytesIO()
        old = self.archive
        with ZipFile(output, 'w', compression=ZIP_DEFLATED) as new:
            new.comment = old.comment
            for info in old.infolist():
                if info.filename not in self.names:
                    continue
                new.writestr(copy(info), self.changed[info.filename] if info.filename in self.changed else old.read(info))
            for path, value in self.changed.items():
                if path not in old.NameToInfo:
                    new.writestr(path, value)
        return output.getvalue()


def _shape_info(shape):
    return next((n for child in shape for n in child if n.tag == f'{{{P}}}cNvPr'), None)


def _shapes(slide):
    tree = slide.find('p:cSld/p:spTree', NS)
    return [(info.get('name', ''), obj) for obj in tree if (info := _shape_info(obj)) is not None
            and obj.tag != f'{{{P}}}nvGrpSpPr']


def _role(slide):
    title = slide.find('p:cSld', NS).get('name')
    if title in (INTRO_MARKER, 'gp.winner', OUTRO_MARKER):
        return title.removeprefix('gp.')
    names = {name for name, _ in _shapes(slide)}
    return next((role for role, keys in SIGNATURES.items() if all(key in names for key in keys)), None)


def _tags(package, write=False):
    given = package.related(PRES, 'tags')
    if not given and not write:
        return None, None
    if given:
        return given, package.xml(given)
    path = package.allocate('ppt/tags/tag1.xml')
    taglist = ET.Element(f'{{{P}}}tagLst', nsmap={'p': P})
    ident = package.link(PRES, R + '/tags', path)
    pres = package.xml(PRES)
    data = pres.find('p:custDataLst', NS)
    if data is None:
        data = ET.Element(f'{{{P}}}custDataLst')
        after = {'kinsoku', 'defaultTextStyle', 'modifyVerifier', 'extLst'}
        pos = next((i for i, item in enumerate(pres) if ET.QName(item).localname in after), len(pres))
        pres.insert(pos, data)
    ET.SubElement(data, f'{{{P}}}tags', {f'{{{R}}}id': ident})
    package.put(PRES, pres)
    package.declare(path, 'application/vnd.openxmlformats-officedocument.presentationml.tags+xml')
    return path, taglist


def _state(package):
    _, tags = _tags(package)
    if tags is None:
        return {}
    values = {item.get('name'): item.get('val') for item in tags}
    if TAG not in values:
        return {}
    count = int(values[TAG])
    if not 1 <= count <= 1024:
        raise MergeError('Unrecognized managed slide metadata.')
    encoded = ''.join(values[f'{TAG}_{i:04}'] for i in range(count))
    result = json.loads(b32decode(encoded, casefold=True))
    if not isinstance(result, dict):
        raise MergeError('Unrecognized managed slide metadata.')
    return result


def _save_state(package, state):
    path, tags = _tags(package, write=True)
    for node in list(tags):
        if node.get('name') == TAG or re.fullmatch(TAG + r'_\d{4}', node.get('name', '')):
            tags.remove(node)
    # PowerPoint's native Tags API can uppercase values. Small, uppercase-safe
    # segments survive an Office save without placing private names in metadata.
    payload = json.dumps(state, sort_keys=True, separators=(',', ':')).encode()
    encoded = b32encode(payload).decode('ascii')
    chunks = [encoded[i:i + 200] for i in range(0, len(encoded), 200)]
    ET.SubElement(tags, f'{{{P}}}tag', name=TAG, val=str(len(chunks)))
    for i, chunk in enumerate(chunks):
        ET.SubElement(tags, f'{{{P}}}tag', name=f'{TAG}_{i:04}', val=chunk)
    package.put(path, tags)


def _notes(package, part):
    path = package.related(part, 'notesSlide')
    if not path:
        return None, None
    body = package.xml(path).xpath('.//p:sp[p:nvSpPr/p:nvPr/p:ph[@type="body"]]/p:txBody', namespaces=NS)
    return path, body[0] if body else None


def _text(element):
    return '\n'.join(''.join(p.itertext(f'{{{A}}}t')) for p in element.findall('.//a:p', NS))


def _note_hash(p):
    return _digest(''.join(p.itertext(f'{{{A}}}t')).encode())


def _names(package):
    found = {}
    for ident, part in package.slides():
        role = _role(package.xml(part))
        if role:
            if role in found:
                raise MergeError('More than one slide matches a managed role.')
            found[role] = (ident, part)
    return found


def _winner_keys(snapshot):
    keys = snapshot.get('winner_keys') or {}
    names = snapshot.get('winner_names') or {}
    return {role: _digest(str(keys.get(role) or names[role]).encode()) for role in WINNERS
            if keys.get(role) or names.get(role)}


def _record(package, ident, part, role, snapshot):
    root = package.xml(part)
    _, notes = _notes(package, part)
    slide_title = root.find('p:cSld', NS).get('name', '')
    state = {'id': ident, 'title': _digest(slide_title.encode()), 'notes': [_note_hash(p) for p in notes.findall('a:p', NS)] if notes is not None else [],
             'timing': _signature(root.find('p:timing', NS)),
             'bodies': {name: _signature(body) for name, shape in _shapes(root)
                        if _data_shape(role, name) and (body := shape.find('p:txBody', NS)) is not None},
             'frames': {name: _frame(shape) for name, shape in _shapes(root) if _data_shape(role, name)}}
    if role == 'intro' and SIGNATURE_FILM in dict(_shapes(root)):
        state['film_upgrade_checked'] = True
    if role in ('intro', 'outro'):
        state['bookend_timing'] = _named_timing(root)
        state['media_sha256'] = {}
        for name in BOOKEND_LINKS:
            media, _ = _bookend_links(package, part, name)
            if media:
                state['media_sha256'][name] = _digest(package.read(media))
    if role in ('intro', 'overview', 'outro'):
        state['transition'] = _transition_signature(_transition(root))
    if role == 'overview' and MORPH_MARK in dict(_shapes(root)):
        state['original_masthead'] = True
    if role == 'latest':
        state['label_inks'] = {name: _signature(obj.find('.//a:rPr/a:solidFill', NS))
                               for name, obj in _shapes(root) if name in DIRTY_LABELS}
    if role == 'winner':
        state['awards'] = _winner_keys(snapshot)
        state['fields'] = {name: _digest(_text(obj).encode()) for name, obj in _shapes(root)
                           if name.startswith(('winner_name_', 'winner_role_', 'winner_stats_')) or name == 'winner_title'}
    return state


def mark_new_deck(blob, snapshot):
    package = Package(blob)
    state = {role: _record(package, ident, part, role, snapshot)
             for role, (ident, part) in _names(package).items()}
    if 'overview' not in state:
        raise MergeError('Unrecognized assembly presentation.')
    _save_state(package, state)
    return package.save()


class Importer:
    """Copy a newly needed generated slide and its relationships into the original package."""

    def __init__(self, source, target, cover, reserved_ids=()):
        self.source, self.target = source, target
        self.reserved_ids = set(reserved_ids)
        self.layout = target.related(cover, 'slideLayout')
        self.master = target.related(self.layout, 'slideMaster') if self.layout else None
        self.copied = {}

    def copy(self, part):
        if part in self.copied:
            return self.copied[part]
        content_type = self.source.content_type(part)
        if content_type.endswith('slideLayout+xml'):
            layout_name = self.source.xml(part).find('p:cSld', NS).get('name')
            if layout_name != 'gp.winner':
                if not self.layout:
                    raise MergeError('The assembly layout could not be identified.')
                return self.layout
            for path in self.target.names:
                if re.fullmatch(r'ppt/slideLayouts/[^/]+\.xml', path):
                    if self.target.xml(path).find('p:cSld', NS).get('name') == layout_name:
                        return path
        if content_type.endswith('slideMaster+xml'):
            if not self.master:
                raise MergeError('The assembly master could not be identified.')
            return self.master
        if content_type.endswith('notesMaster+xml'):
            master = self.target.related(PRES, 'notesMaster')
            if not master:
                raise MergeError('The notes master is missing.')
            return master
        blob = self.source.read(part)
        if content_type.startswith(('image/', 'video/', 'audio/')):
            existing = self.target.media_part(blob, posixpath.splitext(part)[1])
            if existing:
                self.copied[part] = existing
                return existing
        path = self.target.allocate(part)
        self.copied[part] = path
        self.target.put(path, blob)
        self.target.declare(path, content_type)
        if _rels(part) in self.source.names:
            rels = deepcopy(self.source.xml(_rels(part)))
            for rel in rels:
                if rel.get('TargetMode') != 'External':
                    dest = self.copy(_resolve(part, rel.get('Target')))
                    rel.set('Target', posixpath.relpath(dest, posixpath.dirname(path)))
            self.target.put(_rels(path), rels)
        if content_type.endswith('slideLayout+xml'):
            # Register the new picture layout with the original managed slide master.
            rid = self.target.link(self.master, R + '/slideLayout', path)
            master = self.target.xml(self.master)
            layouts = master.find('p:sldLayoutIdLst', NS)
            used = {int(n.get('id')) for item in self.target.names if re.fullmatch(r'ppt/slideMasters/[^/]+\.xml', item)
                    for n in self.target.xml(item).findall('p:sldLayoutIdLst/p:sldLayoutId', NS)}
            new_id = max(used | {2147483648}) + 1
            ET.SubElement(layouts, f'{{{P}}}sldLayoutId', {'id': str(new_id), f'{{{R}}}id': rid})
            self.target.put(self.master, master)
        return path

    def slide(self, source_part, before_id=None, *, after_id=None):
        path = self.copy(source_part)
        pres = self.target.xml(PRES)
        ids = pres.find('p:sldIdLst', NS)
        ident = max({255, *self.reserved_ids, *(int(n.get('id')) for n in ids)}) + 1
        rid = self.target.link(PRES, R + '/slide', path)
        node = ET.Element(f'{{{P}}}sldId', {'id': str(ident), f'{{{R}}}id': rid})
        at = next((i for i, n in enumerate(ids) if int(n.get('id')) == before_id), len(ids))
        if after_id is not None:
            at = next(i + 1 for i, n in enumerate(ids) if int(n.get('id')) == after_id)
        # Keep a teacher's native PowerPoint sections in step with the slide list.
        if len(ids):
            anchor = str(after_id) if after_id is not None else ids[at if at < len(ids) else -1].get('id')
            sections = pres.findall(f'.//{{{P14}}}section/{{{P14}}}sldIdLst/{{{P14}}}sldId')
            match = next((n for n in sections if n.get('id') == anchor), None)
            if match is not None:
                group = match.getparent()
                group.insert(group.index(match) + int(after_id is not None or at == len(ids)), ET.Element(match.tag, id=str(ident)))
        ids.insert(at, node)
        self.target.put(PRES, pres)
        return ident, path


def _new_shape_id(root):
    return max((int(n.get('id')) for n in root.iter(f'{{{P}}}cNvPr')), default=0) + 1


def _copy_shape(shape, origin, src_part, target, dst_part, importer=None):
    result = deepcopy(shape)
    relations = origin.relations(src_part)
    for node in result.iter():
        for key, value in list(node.attrib.items()):
            if key.startswith('{' + R + '}') and value:
                rel = relations[value]
                external = rel.get('TargetMode') == 'External'
                dest = rel.get('Target') if external else _resolve(src_part, rel.get('Target'))
                if importer and not external:
                    dest = importer.copy(dest)
                node.set(key, target.link(dst_part, rel.get('Type'), dest, external=external))
    return result


def _bookend_links(package, part, name):
    pictures = [shape for label, shape in _shapes(package.xml(part)) if label == name]
    if len(pictures) != 1 or pictures[0].tag != f'{{{P}}}pic':
        return None, []
    if name == MORPH_MARK and pictures[0].find('.//a:videoFile', NS) is not None:
        return None, []  # The owner replaced the picture with a video.
    relationships = package.relations(part)
    links = []
    paths = set()
    for tag, attribute, kind in BOOKEND_LINKS[name]:
        nodes = list(pictures[0].iter(tag))
        if len(nodes) != 1:
            return None, []
        if name == MORPH_MARK and nodes[0].get(f'{{{R}}}link'):
            return None, []  # An embedded preview can accompany an externally linked image.
        key = f'{{{R}}}{attribute}'
        rel = relationships.get(nodes[0].get(key))
        if rel is None or rel.get('Type') != kind or rel.get('TargetMode') == 'External':
            return None, []
        paths.add(_resolve(part, rel.get('Target')))
        links.append((nodes[0], key, rel))
    return (paths.pop(), links) if len(paths) == 1 else (None, [])


def _update_signature_asset(name, source, src_part, target, dst_part, history, importer):
    old_path, links = _bookend_links(target, dst_part, name)
    new_path, _ = _bookend_links(source, src_part, name)
    if not old_path or not new_path:
        return False, None
    digest = _digest(target.read(old_path))
    if digest == _digest(source.read(new_path)):
        return True, None
    prior = history.get('media_sha256', {}).get(name)
    if prior:
        stock = {prior}
    else:
        paper = source.xml(src_part).find('p:cSld/p:bg/p:bgPr/a:solidFill/a:srgbClr', NS)
        stock = PREVIOUS_BOOKEND_MEDIA.get(paper.get('val'), {}).get(name, ()) if paper is not None else ()
    if digest not in stock:
        return False, None
    # Change only the managed object's links. A teacher's copy can reuse the
    # exact same file and relationship ID on the very same slide.
    destination = importer.copy(new_path)
    for node, key, rel in links:
        node.set(key, target.link(dst_part, rel.get('Type'), destination))
    page = target.xml(dst_part)
    target.put(dst_part, page)
    used = {v for node in page.iter() for k, v in node.attrib.items() if k.startswith('{' + R + '}')}
    rels = target.xml(_rels(dst_part))
    for _, _, rel in links:
        if rel.get('Id') not in used:
            rels.remove(rel)
    target.put(_rels(dst_part), rels)
    return True, old_path


def _discard_unreferenced_stock_media(package, candidates):
    # Relationship owners can be slides, layouts, masters, notes or custom
    # parts. Retain each previous asset if anything in the package uses it.
    for path in package.names:
        if not candidates:
            return
        directory, filename = posixpath.split(path)
        if posixpath.basename(directory) != '_rels' or not filename.endswith('.rels'):
            continue
        owner = posixpath.join(posixpath.dirname(directory), filename[:-5])
        for rel in package.xml(path):
            if rel.get('TargetMode') != 'External':
                candidates.discard(_resolve(owner, rel.get('Target')))
    types = package.xml(TYPES)
    for path in candidates:
        if _rels(path) in package.names:
            continue
        package.names.discard(path)
        package.changed.pop(path, None)
        for override in types.findall(f'{{{CT}}}Override'):
            if override.get('PartName') == '/' + path:
                types.remove(override)
                package.put(TYPES, types)


def _stock_brand_shape(package, part, shape):
    clone = deepcopy(shape)
    _shape_info(clone).set('id', '0')  # Native IDs and relationship IDs can change on save.
    relations = package.relations(part)
    for node in clone.iter():
        for key, value in list(node.attrib.items()):
            if key.startswith('{' + R + '}') and value:
                rel = relations[value]
                if rel.get('TargetMode') == 'External':
                    return False
                node.set(key, _digest(package.read(_resolve(part, rel.get('Target')))))
    return _signature(clone) in LEGACY_BRAND[_shape_info(shape).get('name')]


def _upgrade_intro(source, src_part, target, dst_part, old, importer):
    if old.get('film_upgrade_checked'):
        return False
    fresh, saved = source.xml(src_part), target.xml(dst_part)
    program = dict(_shapes(fresh))
    saved_shapes = _shapes(saved)
    prior = dict(saved_shapes)
    if any(sum(name == role for name, _ in saved_shapes) != 1 for role in LEGACY_BRAND):
        return False
    if SIGNATURE_FILM not in program or SIGNATURE_FILM in prior:
        return False
    if _signature(saved.find('p:cSld/p:bg', NS)) != _signature(fresh.find('p:cSld/p:bg', NS)):
        return False  # A full-frame film would conceal the teacher's background.
    old_timing = saved.find('p:timing', NS)
    # Membership in a prior registry alone does not authorize replacing the
    # owner's custom animation, even if it targets only the two brand shapes.
    if _signature(old_timing) not in (LEGACY_INTRO_TIMING, old.get('timing', LEGACY_INTRO_TIMING)):
        return False
    if any(not _stock_brand_shape(target, dst_part, prior[name]) for name in LEGACY_BRAND):
        return False
    new_timing = fresh.find('p:timing', NS)
    if new_timing is None:
        raise MergeError('The generated tutorial has no playback sequence.')
    tree = saved.find('p:cSld/p:spTree', NS)
    remap = {}
    for name, shape in program.items():
        replacement = _copy_shape(shape, source, src_part, target, dst_part, importer)
        original = prior.get(name)
        if original is not None:
            ident = _shape_info(original).get('id')
            tree.replace(original, replacement)
        else:
            ident = str(_new_shape_id(saved))
            # A full-canvas film belongs behind any teacher-added annotations.
            first_shape = next(obj for _, obj in _shapes(saved))
            tree.insert(tree.index(first_shape), replacement)
        remap[_shape_info(shape).get('id')] = ident
        _shape_info(replacement).set('id', ident)
    timing = _copy_shape(new_timing, source, src_part, target, dst_part, importer)
    for node in timing.iter():
        if 'spid' in node.attrib:
            node.set('spid', remap[node.get('spid')])
    if old_timing is not None:
        saved.replace(old_timing, timing)
    else:
        next_node = saved.find('p:extLst', NS)
        saved.insert(saved.index(next_node) if next_node is not None else len(saved), timing)
    target.put(dst_part, saved)
    return True


def _picture_role(pic):
    ph = pic.find('p:nvPicPr/p:nvPr/p:ph', NS)
    idx = ph.get('idx') if ph is not None else None
    return next((role for role, index in WINNERS.items() if index == idx), None)


def _keep_unchanged_pictures(target, old_part, new_part, unchanged):
    root = target.xml(new_part)
    for _, pic in _shapes(target.xml(old_part)):
        if pic.tag != f'{{{P}}}pic' or _picture_role(pic) not in unchanged:
            continue
        idx = WINNERS[_picture_role(pic)]
        matches = root.xpath('./p:cSld/p:spTree/p:sp[p:nvSpPr/p:nvPr/p:ph[@idx=$idx]]',
                             namespaces=NS, idx=idx)
        if len(matches) == 1:
            placeholder = matches[0]
            replacement = _copy_shape(pic, target, old_part, target, new_part)
            _shape_info(replacement).set('id', _shape_info(placeholder).get('id'))
            placeholder.getparent().replace(placeholder, replacement)
    target.put(new_part, root)


def _update_notes(source, src_part, target, dst_part, role, old):
    _, fresh = _notes(source, src_part)
    path, saved = _notes(target, dst_part)
    if saved is None or fresh is None:
        return
    original = saved.findall('a:p', NS)
    hashes = old.get('notes', [])
    # Only replace paragraphs that we previously generated. Teacher paragraphs,
    # added presenter cues, links, and other note placeholders retain their XML.
    managed = [p for p in original if _note_hash(p) in hashes]
    if hashes and not managed:
        return
    new = fresh.findall('a:p', NS)
    if not hashes:
        new_hashes = [_note_hash(p) for p in new]
        if [_note_hash(p) for p in original] == new_hashes:
            return
        managed = [p for p in original if _note_hash(p) in new_hashes]
        # Older assemblies have no per-paragraph baseline. Their notes start
        # with a fixed template cue and the registered school name. Recognize
        # only the generated data sentence in that exact block.
        if len(original) >= 3 and len(new) >= 3 and [_note_hash(p) for p in original[:2]] == new_hashes[:2]:
            line = ''.join(original[2].itertext(f'{{{A}}}t'))
            comparison = r'Previous session: .+ Latest session: .+ Clean-plate rates: .+ in the latest session\. ' + COMPARISON_NOTE_RESULT
            signatures = {
                'overview': r'[\d,]+ clean plates?\. .+',
                'latest': r'.+, .+\. [\d,]+ of [\d,]+ recorded plates? (?:was|were) clean\.',
                'table': comparison, 'chart': comparison,
            }
            if role in signatures and re.fullmatch(signatures[role], line, re.DOTALL) and original[2] not in managed:
                managed.append(original[2])
    pos = saved.index(managed[0]) if managed else len(saved)
    for p in managed:
        saved.remove(p)
    for index, p in enumerate(new):
        saved.insert(pos + index, deepcopy(p))
    target.put(path, target.xml(path))


def _set_session_text(node, replacement):
    runs = list(node.iter(f'{{{A}}}t'))
    if len(runs) == 1:
        runs[0].text = replacement
        return
    # PowerPoint can split a template sentence into styled/hyperlinked runs.
    # Keep unchanged characters in their original runs, including names.
    before = ''.join(run.text or '' for run in runs)
    edits = SequenceMatcher(None, before, replacement, autojunk=False).get_opcodes()
    start = 0
    for index, run in enumerate(runs):
        end = start + len(run.text or '')
        chunks = []
        for kind, left, right, new_left, new_right in edits:
            if kind == 'equal' and max(start, left) < min(end, right):
                chunks.append(before[max(start, left):min(end, right)])
            elif kind in ('insert', 'replace') and (start <= left < end or left == end == len(before) and index == len(runs) - 1):
                chunks.append(replacement[new_left:new_right])
        run.text = ''.join(chunks)
        start = end


def _migrate_session_copy(package, part, role, old, school_name):
    root = package.xml(part)
    labels = LEGACY_SESSION_LABELS[role]
    changed = False
    shapes = _shapes(root)
    unique = {name for name in labels if sum(saved_name == name for saved_name, _ in shapes) == 1}
    for name, shape in shapes:
        if name in unique and _text(shape) == labels[name][0]:
            _set_session_text(shape, labels[name][1])
            changed = True
    header = root.find('p:cSld', NS)
    if role == 'table' and header.get('name') == 'Lunch to lunch':
        header.set('name', 'Session comparison')
        changed = True
    if changed:
        package.put(part, root)
    path, body = _notes(package, part)
    if body is None:
        return
    paragraphs = body.findall('a:p', NS)
    text = [''.join(p.itertext(f'{{{A}}}t')) for p in paragraphs]
    hashes = old.get('notes', [])
    trusted_block = len(text) >= 2 and text[:2] == [LEGACY_SESSION_CUES[role], school_name]
    for index, (paragraph, line) in enumerate(zip(paragraphs, text)):
        previous = _note_hash(paragraph)
        if previous not in hashes and (hashes or not trusted_block):
            continue
        if line == LEGACY_SESSION_CUES[role]:
            new = (line.replace('at this lunch', 'during this session').replace('at that lunch', 'during that session')
                   .replace('lunches', 'sessions').replace('lunch', 'session'))
        elif role in ('table', 'chart') and (index == 2 or previous in hashes):
            # Session names can contain the word Lunch. Match the generated
            # separators after the count sentences and leave both names verbatim.
            new = re.sub(r'^Previous lunch: (.+? of [\d,]+ recorded plates? (?:was|were) clean\.) Latest lunch: '
                         r'(.+? of [\d,]+ recorded plates? (?:was|were) clean\.) Clean-plate rates: '
                         r'(.+? previously and .+?) at the latest lunch\.(?= ' + COMPARISON_NOTE_RESULT + r'\Z)',
                         r'Previous session: \1 Latest session: \2 Clean-plate rates: \3 in the latest session.', line,
                         flags=re.DOTALL)
        else:
            continue
        if new != line:
            _set_session_text(paragraph, new)
            if previous in hashes:
                hashes = [_note_hash(paragraph) if value == previous else value for value in hashes]
                old['notes'] = hashes
            package.put(path, package.xml(path))


def _geometry(shape):
    return shape.find('p:spPr/a:xfrm', NS)


def _frame(shape):
    xfrm = _geometry(shape)
    return _signature(xfrm)


def _data_shape(role, name):
    if role in ('intro', 'outro'):
        return False
    if name in ('school', 'stamp'):
        return True
    if role == 'winner':
        return name == 'winner_title' or name.startswith(('winner_name_', 'winner_role_', 'winner_stats_'))
    if role == 'overview' and name != 'latest_heading':
        return (name in ('all_clean', 'share', 'goal_label', 'rate_heading', 'change_heading', 'change_units',
                         'progress_track', 'Progress meter window', 'All-time clean plate share')
                or name.startswith(('latest_', 'Clean plates toward ', 'Clean plates above ')))
    if role == 'latest':
        return (name in DIRTY_LABELS or name in ('latest_name', 'latest_date', 'latest_counts', 'rate', 'student_clean', 'faculty_clean',
                         'dirty', 'very_dirty', 'distribution') or ' roll ' in name
                or name.endswith((' share', ' zero marker', ' window')))
    if role in ('table', 'chart'):
        return name.startswith(('prev_', 'curr_', 'delta_')) or name == 'rate_comparison'
    return False


def _replace_prop(parent, previous, fresh):
    if fresh is not None:
        if previous is not None:
            parent.replace(previous, deepcopy(fresh))
        elif ET.QName(fresh).localname in ('bodyPr', 'pPr', 'rPr', 'xfrm'):
            parent.insert(0, deepcopy(fresh))
        else:
            parent.append(deepcopy(fresh))


def _refresh_text(shape, source, previous_hash):
    saved = shape.find('p:txBody', NS)
    fresh = source.find('p:txBody', NS)
    if saved is None or fresh is None or _signature(saved) == _signature(fresh):
        return
    if _signature(saved) == previous_hash:
        shape.replace(saved, deepcopy(fresh))
        return
    if _text(shape) == _text(source):
        return
    # A teacher restyled this textbox, or it predates shape baselines. Carry
    # their local run/paragraph properties (including links) onto the new
    # data and keep the new line breaks fitted for the updated text.
    replacement = deepcopy(fresh)
    for tag in ('a:bodyPr', 'a:lstStyle'):
        _replace_prop(replacement, replacement.find(tag, NS), saved.find(tag, NS))
    paragraphs = saved.findall('a:p', NS)
    for index, paragraph in enumerate(replacement.findall('a:p', NS)):
        if not paragraphs:
            break
        original = paragraphs[min(index, len(paragraphs) - 1)]
        source_runs = original.findall('a:r', NS)
        for j, run in enumerate(paragraph.findall('a:r', NS)):
            if source_runs:
                old_run = source_runs[min(j, len(source_runs) - 1)]
                _replace_prop(run, run.find('a:rPr', NS), old_run.find('a:rPr', NS))
        _replace_prop(paragraph, paragraph.find('a:pPr', NS), original.find('a:pPr', NS))
        _replace_prop(paragraph, paragraph.find('a:endParaRPr', NS), original.find('a:endParaRPr', NS))
    shape.replace(saved, replacement)


def _transition(root):
    for item in root:
        if item.tag == f'{{{P}}}transition' or (
                item.tag == f'{{{MC}}}AlternateContent' and item.find('.//p:transition', NS) is not None):
            return item
    return None


def _transition_signature(node):
    if node is None:
        return None
    # PowerPoint can save a supported transition directly instead of retaining
    # the generated compatibility branches. Match only the two exact presets.
    variants = [node] if node.tag == f'{{{P}}}transition' else node.findall('.//p:transition', NS)
    presets = set()
    for transition in variants:
        if (len(transition) != 1 or transition.get('advClick', '1') not in ('1', 'true')
                or set(transition.attrib) - {'advClick', f'{{{P14}}}dur'}):
            return _signature(node)
        effect = transition[0]
        duration = transition.get(f'{{{P14}}}dur')
        if effect.tag == f'{{{P}}}fade' and not effect.attrib and duration in (None, '250'):
            if duration:
                presets.add('fade250')
        elif (ET.QName(effect).localname == 'morph' and effect.get('option') == 'byObject'
              and len(effect.attrib) == 1 and duration in ('850', '450')):
            presets.add('morph' + duration)
        else:
            return _signature(node)
    morphs = presets - {'fade250'}
    if morphs:
        return morphs.pop() if len(morphs) == 1 else _signature(node)
    return 'fade250' if 'fade250' in presets else _signature(node)


def _stock_bookend_hold(node, role, saved_timing):
    if node is None:
        return None
    normalized = deepcopy(node)
    variants = [normalized] if normalized.tag == f'{{{P}}}transition' else normalized.findall('.//p:transition', NS)
    times = {item.get('advTm') for item in variants}
    # An unregistered deck may have a teacher's advance setting. Only infer
    # defaults actually shipped with this animation and this slide role.
    if saved_timing == PREVIOUS_BOOKEND_TIMING:
        holds = {'3500', '4050'}
    elif saved_timing == QUICK_BOOKEND_TIMING:
        holds = {'2283', '0'} if role == 'intro' else {'2283'}
    else:
        holds = {'1500'} if role == 'intro' else set()
    if len(times) != 1 or not times <= holds:
        return None
    for item in variants:
        if item.get('advClick') not in ('0', 'false'):
            return None
        item.attrib.pop('advTm')
        item.set('advClick', '1')
    return times.pop() if _transition_signature(normalized) == 'fade250' else None


def _named_timing(root):
    # Imported slides can have different native shape IDs while retaining the
    # exact same movie, effect targets and playback sequence.
    timing = root.find('p:timing', NS)
    if timing is None:
        return None
    normalized = deepcopy(timing)
    targets = {_shape_info(shape).get('id'): name for name, shape in _shapes(root)}
    for node in normalized.iter():
        if 'spid' in node.attrib:
            node.set('spid', targets.get(node.get('spid'), ''))
    return _signature(normalized)


def _refresh_bookend(role, source, src_part, target, part, history, importer, retired_media, upgraded_intro):
    root, fresh = target.xml(part), source.xml(src_part)
    actual_timing, next_timing = _named_timing(root), _named_timing(fresh)
    known_timings = {history['bookend_timing']} if 'bookend_timing' in history else {PREVIOUS_BOOKEND_TIMING, QUICK_BOOKEND_TIMING}
    if not next_timing or not actual_timing or (actual_timing != next_timing and actual_timing not in known_timings):
        return False  # Keep a teacher's playback cues with their film and matching final frame.
    source_shapes = dict(_shapes(fresh))
    saved_shapes = [(name, shape) for name, shape in _shapes(root) if name in source_shapes]
    if sorted(name for name, _ in saved_shapes) != sorted(source_shapes):
        return False  # An owner removed, renamed or duplicated a target.
    stock_film = False
    for name in BOOKEND_LINKS:
        current_asset, retired = _update_signature_asset(name, source, src_part, target, part, history, importer)
        if retired:
            retired_media.add(retired)
        if name == SIGNATURE_FILM:
            stock_film = current_asset
    if not stock_film:
        return False  # A school video can have a different running time.
    if actual_timing != next_timing:
        timing = deepcopy(fresh.find('p:timing', NS))
        ids = {_shape_info(source_shapes[name]).get('id'): _shape_info(shape).get('id') for name, shape in saved_shapes}
        for node in timing.iter():
            if 'spid' in node.attrib:
                node.set('spid', ids[node.get('spid')])
        root.replace(root.find('p:timing', NS), timing)
        target.put(part, root)
    previous, required = _transition(root), _transition(fresh)
    if previous is None or required is None or _signature(previous) == _signature(required):
        return True
    actual = _transition_signature(previous)
    previously_click_advanced = role == 'intro' and (upgraded_intro or actual_timing == PREVIOUS_BOOKEND_TIMING)
    expected = history.get('transition', 'fade250' if previously_click_advanced else None)
    old_hold = _stock_bookend_hold(previous, role, actual_timing)
    if old_hold is not None:
        original = deepcopy(required)
        variants = [original] if original.tag == f'{{{P}}}transition' else original.findall('.//p:transition', NS)
        for variant in variants:
            variant.set('advTm', old_hold)
        if 'transition' not in history or expected == _signature(original):
            expected = actual  # Also handles a desktop save collapsing the compatibility branches.
    if actual == expected:
        root.replace(previous, deepcopy(required))
        target.put(part, root)
    return True


def _cover_transition(source, target, fresh, current, baseline, history, previous_intro_timing):
    cover_id, part = current['overview']
    root = target.xml(part)
    actual = _transition(root)
    morph = _transition(source.xml(fresh['overview'][1]))
    fade = _transition(source.xml(fresh['reminders'][1]))
    if morph is None or fade is None:
        raise MergeError('The assembly transition is unavailable.')
    ids = [ident for ident, _ in target.slides()]
    index = ids.index(cover_id)
    intro = current.get('intro')
    adjacent = bool(intro and index and ids[index - 1] == intro[0]
                    and target.xml(intro[1]).get('show') not in ('0', 'false'))
    desired = morph if adjacent else fade
    actual_hash = _transition_signature(actual)
    desired_hash = _transition_signature(desired)
    known = history.get('transition')
    # In an unmarked deck the preceding animation distinguishes the stock 450 ms
    # Morph from a teacher selecting that speed on an older, 850 ms edition.
    previous_morph = 'morph450' if previous_intro_timing == EARLY_HANDOFF_TIMING else 'morph850'
    managed = actual_hash == known if 'transition' in history else actual_hash in (
        _transition_signature(fade), _transition_signature(morph), previous_morph)
    if managed and actual_hash != desired_hash:
        if actual is not None:
            root.replace(actual, deepcopy(desired))
        else:
            next_node = next((n for n in root if n.tag in (f'{{{P}}}timing', f'{{{P}}}extLst')), None)
            root.insert(root.index(next_node) if next_node is not None else len(root), deepcopy(desired))
        target.put(part, root)
    baseline['transition'] = desired_hash if managed else known or desired_hash


def _migrate_masthead(root, destination, old):
    saved, fresh = (dict(_shapes(slide)) for slide in (root, destination))
    legacy = [name for name in BRAND_NAMES if name in saved]
    if legacy:
        # Before the intro existed, the objects were already in their intended
        # positions. Rename them in place, retaining native IDs and user edits.
        for original in legacy:
            alias = BRAND_NAMES[original]
            if alias in saved:
                raise MergeError('Two objects claim the same Morph destination.')
            if alias in fresh and saved[original].tag == fresh[alias].tag:
                _shape_info(saved[original]).set('name', alias)
        return True
    if old.get('original_masthead'):
        return False

    # One earlier intro release put the matched objects on the right. Detect
    # its original native frames, not merely an object somewhere on that side.
    # An untracked deck needs two matching frames to establish its provenance.
    interim = {MORPH_MARK: (724, None), MORPH_WORDMARK: (766, 146), 'school': (48, None)}
    matches = []
    for name, (left, width) in interim.items():
        if name not in saved or name not in fresh or saved[name].tag != fresh[name].tag:
            continue
        expected = deepcopy(_geometry(fresh[name]))
        expected.find('a:off', NS).set('x', str(left * 12700))
        if width is not None:
            expected.find('a:ext', NS).set('cx', str(width * 12700))
        if _signature(expected) == _frame(saved[name]):
            matches.append(name)
    if len(matches) < 2 and not old.get('transition'):
        return False
    for name in matches:
        shape = saved[name]
        _replace_prop(shape.find('p:spPr', NS), _geometry(shape), _geometry(fresh[name]))
        if name == 'school':
            for paragraph in shape.findall('.//a:pPr', NS):
                if paragraph.get('algn', 'l') == 'l':
                    paragraph.set('algn', 'r')
    # A deliberately moved school label should keep its text alignment, too.
    # The generic data binder can still update its wording and fitted lines.
    if 'school' not in matches and 'school' in saved and 'school' in old.get('frames', {}):
        if _frame(saved['school']) != old['frames']['school']:
            old['bodies'] = {name: value for name, value in old.get('bodies', {}).items() if name != 'school'}
    return False


def _remove_old_brand_fades(cover):
    # Unmarked older decks can contain custom animation groups. Remove the
    # former two auto-fades without replacing the owner's full timeline.
    ids = {_shape_info(obj).get('id') for name, obj in _shapes(cover) if name in BRAND_NAMES.values()}
    timing = cover.find('p:timing', NS)
    if timing is None:
        return
    for clock in timing.findall('.//p:cTn[@presetClass="entr"][@presetID="10"]', NS):
        targets = {n.get('spid') for n in clock.findall('.//p:spTgt', NS)}
        effect = clock.getparent()
        if targets and targets <= ids and effect.tag == f'{{{P}}}par' and len(effect) == 1:
            effect.getparent().remove(effect)
    remaining = {n.get('spid') for n in timing.findall('.//p:spTgt', NS)}
    for build in timing.findall('p:bldLst/*', NS):
        if build.get('spid') in ids - remaining:
            build.getparent().remove(build)


def _update_slide(source, src_part, target, dst_part, role, old, importer):
    root = target.xml(dst_part)
    tree = root.find('p:cSld/p:spTree', NS)
    fresh = source.xml(src_part)
    new_items = _shapes(fresh)
    saved = {}
    for name, shape in _shapes(root):
        if name in saved and _data_shape(role, name):
            raise MergeError('Two shapes use the same managed data name.')
        saved.setdefault(name, shape)
    if role == 'latest':
        header = root.find('p:cSld', NS)
        title = header.get('name', '')
        old_name = saved.get('latest_name')
        if _digest(title.encode()) == old.get('title') or (old_name is not None and title == _text(old_name)):
            header.set('name', fresh.find('p:cSld', NS).get('name', 'Latest session'))
    current = set()
    remap = {}
    previous_frames = old.get('frames', {})
    skipped = set()
    # Use the fresh names for optional data objects. All unrelated teacher
    # objects stay in place, including pictures, charts, groups and OLE parts.
    for index, (name, item) in enumerate(new_items):
        dest = saved.get(name)
        ident = _shape_info(item).get('id')
        if not _data_shape(role, name):
            # Desktop PowerPoint renames a picture when an empty slot is filled.
            # The native placeholder idx survives pasting, renaming and cropping.
            if role == 'winner':
                placeholder = item.find('p:nvSpPr/p:nvPr/p:ph', NS)
                if placeholder is not None and placeholder.get('idx') in WINNERS.values():
                    idx = placeholder.get('idx')
                    dest = next((obj for _, obj in _shapes(root)
                                 if any(ph.get('idx') == idx for ph in obj.iter(f'{{{P}}}ph'))), None)
            if dest is None:
                skipped.add(ident)
            else:
                remap[ident] = _shape_info(dest).get('id')
            continue
        current.add(name)
        if dest is None:
            # A shape a teacher explicitly removed from a marked deck stays removed.
            if name in previous_frames:
                skipped.add(ident)
                continue
            clone = _copy_shape(item, source, src_part, target, dst_part, importer)
            _shape_info(clone).set('id', str(_new_shape_id(root)))
            follower = next((saved[n] for n, _ in new_items[index + 1:] if n in saved), None)
            if follower is None:
                tree.append(clone)
            else:
                tree.insert(tree.index(follower), clone)
            saved[name] = dest = clone
        else:
            if dest.tag != item.tag:
                raise MergeError('A managed shape has been replaced by a different object.')
            props = _shape_info(dest)
            if name in old.get('hidden_shapes', ()):
                props.attrib.pop('hidden', None)
            custom_winner = role == 'winner' and name.startswith('winner_')
            previous = old.get('fields', {}).get(name)
            # Preserve manually entered names, including a fallback filled by the teacher.
            manual = custom_winner and ((previous and _digest(_text(dest).encode()) != previous)
                                        or (not previous and _text(dest).strip() and _text(dest) != _text(item)))
            if role == 'overview' and name == 'change_heading':
                manual = _text(dest) not in ('', 'First recorded lunch', 'First recorded session',
                                             'Change from previous lunch', 'Change from previous session')
            if not manual:
                _refresh_text(dest, item, old.get('bodies', {}).get(name))
            if role == 'latest' and name in DIRTY_LABELS:
                ink = item.find('.//a:rPr/a:solidFill', NS)
                prior = old.get('label_inks', {}).get(name)
                for style in dest.findall('.//a:rPr', NS):
                    original = style.find('a:solidFill', NS)
                    if ink is not None and (prior is None or _signature(original) == prior):
                        _replace_prop(style, original, ink)
            props = dest.find('p:spPr', NS)
            source_props = item.find('p:spPr', NS)
            if props is not None and source_props is not None:
                if _frame(dest) == previous_frames.get(name) or (name not in previous_frames and
                        (name.endswith((' share', '_fill')) or name.startswith(('Clean plates ', 'All-time clean ')))):
                    _replace_prop(props, _geometry(dest), _geometry(item))
                if name.endswith((' share', '_fill', ' window')) or name.startswith(('Clean plates ', 'All-time clean ')):
                    geometry = props.xpath('./a:custGeom|./a:prstGeom', namespaces=NS)
                    source_geometry = source_props.xpath('./a:custGeom|./a:prstGeom', namespaces=NS)
                    if source_geometry:
                        _replace_prop(props, geometry[0] if geometry else None, source_geometry[0])
        remap[ident] = _shape_info(dest).get('id')
    hidden = []
    for name, shape in saved.items():
        if _data_shape(role, name) and name not in current:
            _shape_info(shape).set('hidden', '1')
            hidden.append(name)
    old_timing = root.find('p:timing', NS)
    if role not in ('intro', 'outro') and _signature(old_timing) == old.get('timing'):
        new_timing = fresh.find('p:timing', NS)
        if new_timing is not None and not skipped:
            timing = deepcopy(new_timing)
            for node in timing.iter():
                if 'spid' in node.attrib:
                    if node.get('spid') not in remap:
                        raise MergeError('A managed animation target could not be identified.')
                    node.set('spid', remap[node.get('spid')])
            if old_timing is None:
                tail = root.find('p:extLst', NS)
                root.insert(root.index(tail), timing) if tail is not None else root.append(timing)
            else:
                root.replace(old_timing, timing)
        elif old_timing is not None and new_timing is None:
            root.remove(old_timing)
    target.put(dst_part, root)
    _update_notes(source, src_part, target, dst_part, role, old)
    return hidden


def _merge(existing, generated, snapshot):
    source, target = Package(generated), Package(existing)
    fresh = _names(source)
    state = _state(target)
    by_id = dict(target.slides())
    if state:
        current = {role: (info['id'], by_id[info['id']]) for role, info in state.items()
                   if role in ORDER and info['id'] in by_id}
        for role, (_, part) in list(current.items()):
            slide = target.xml(part)
            if role in ('intro', 'outro') and _role(slide) != role:
                # PowerPoint may reuse a deleted slide ID when a teacher adds a
                # replacement page. Do not claim that new page or reinsert ours.
                del current[role]
                continue
            recognized = (_role(slide) == role if role in ('intro', 'winner', 'outro') else
                          any(name in SIGNATURES[role] for name, _ in _shapes(slide)))
            if not recognized:
                raise MergeError('The saved PowerPoint slide identifiers no longer match the connected assembly.')
    else:
        current = _names(target)
    if 'overview' not in current or 'overview' not in fresh:
        raise MergeError('The saved PowerPoint could not be identified as the connected assembly.')
    for role in ('intro', 'outro'):
        if role in fresh and role not in state and role not in current:
            matches = [(i, part) for i, part in by_id.items() if _role(target.xml(part)) == role]
            if len(matches) > 1:
                raise MergeError('More than one saved slide matches the new branded slide.')
            if matches:
                current[role] = matches[0]
    cover_history = state.get('overview', {}).copy()
    previous_intro_timing = _named_timing(target.xml(current['intro'][1])) if 'intro' in current and 'transition' not in cover_history else None
    importer = Importer(source, target, current['overview'][1], (info['id'] for info in state.values()))
    retired_media = set()
    for index, role in enumerate(ORDER):
        old = state.get(role, {}).copy()
        if role in LEGACY_SESSION_LABELS and role in current:
            _migrate_session_copy(target, current[role][1], role, old, snapshot['school_name'])
        if role not in fresh:
            if role in current and role in ('latest', 'table', 'chart'):
                ident, part = current[role]
                node = target.xml(part)
                if not old:
                    old = {'id': ident}  # Preserve unmarked, already-hidden slides and their private notes.
                if node.get('show') not in ('0', 'false'):
                    node.set('show', '0')
                    target.put(part, node)
                    old['auto_hidden'] = True
                state[role] = old
            continue
        _, src_part = fresh[role]
        if role not in current and old:
            continue  # The owner intentionally removed this previously managed slide.
        before = next((current[next_role][0] for next_role in ORDER[index + 1:] if next_role in current), None)
        previous_part = current.get(role, (None, None))[1]
        after = None
        archive = False
        teacher_hidden = False
        if role == 'outro' and previous_part is None:
            if 'closing' not in current:
                continue  # A teacher removed the signoff before this upgrade.
            after, closing_part = current['closing']
            teacher_hidden = target.xml(closing_part).get('show') in ('0', 'false')
        unchanged = set()
        if role == 'winner' and previous_part:
            saved = target.xml(previous_part)
            keys = _winner_keys(snapshot)
            previous_keys = old.get('awards', {})
            changed = {r for r in WINNERS if previous_keys.get(r) != keys.get(r)}
            unchanged = {r for r in WINNERS if keys.get(r) and r not in changed}
            photos = [_picture_role(pic) for pic in saved.iter(f'{{{P}}}pic')
                      if _shape_info(pic).get('name') != 'Plate mark']
            fields = old.get('fields', {})
            fresh_fields = dict(_shapes(source.xml(src_part)))
            manually_named = {r for r in changed for name, shape in _shapes(saved)
                              if name == 'winner_name_' + r and _text(shape).strip()
                              and _digest(_text(shape).encode()) != fields.get(name)
                              and _text(shape) != _text(fresh_fields[name])}
            archive = bool(changed and (set(photos) & changed or None in photos or manually_named))
        if archive:
            after = current[role][0]
            prior = target.xml(previous_part)
            teacher_hidden = prior.get('show') in ('0', 'false')
            prior.set('show', '0')
            prior.find('p:cSld', NS).set('name', 'gp.winner.history')
            target.put(previous_part, prior)
        if previous_part is None or archive:
            ident, part = importer.slide(src_part, before, after_id=after)
            if teacher_hidden:
                active = target.xml(part)
                active.set('show', '0')
                target.put(part, active)
            if archive:
                _keep_unchanged_pictures(target, previous_part, part, unchanged)
            hidden = []
            replace_timing = True
        else:
            ident, part = current[role]
            root = target.xml(part)
            if old.get('auto_hidden'):
                root.attrib.pop('show', None)
            replace_timing = _signature(root.find('p:timing', NS)) == old.get('timing')
            migrated = False
            if role == 'overview' and 'intro' in fresh:
                migrated = _migrate_masthead(root, source.xml(src_part), old)
            upgraded_intro = role == 'intro' and _upgrade_intro(source, src_part, target, part, old, importer)
            if upgraded_intro:
                replace_timing = True
                _update_notes(source, src_part, target, part, role, old)
                hidden = []
            else:
                hidden = _update_slide(source, src_part, target, part, role, old, importer)
            if role in ('intro', 'outro') and SIGNATURE_FILM in dict(_shapes(root)):
                replace_timing = _refresh_bookend(role, source, src_part, target, part, old, importer, retired_media,
                                                   upgraded_intro)
            if migrated:
                _remove_old_brand_fades(root)
                target.put(part, root)
        baseline = _record(source, ident, src_part, role, snapshot)
        baseline['hidden_shapes'] = hidden
        baseline['timing'] = _signature(target.xml(part).find('p:timing', NS)) if replace_timing else old.get('timing')
        state[role] = baseline
        current[role] = (ident, part)
    if 'intro' in fresh:
        _cover_transition(source, target, fresh, current, state['overview'], cover_history, previous_intro_timing)
    _discard_unreferenced_stock_media(target, retired_media)
    _save_state(target, state)
    return target.save()


def merge_deck(existing, generated, snapshot):
    try:
        return _merge(existing, generated, snapshot)
    except (BadZipFile, KeyError, IndexError, AttributeError, TypeError, ValueError, StopIteration, OSError, RuntimeError, ET.XMLSyntaxError) as error:
        raise MergeError('The saved PowerPoint could not be safely updated. Its existing contents were kept.') from error
