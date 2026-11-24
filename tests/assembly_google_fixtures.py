"""Small native Slides fixtures. No OAuth, Drive or network calls."""
from hashlib import sha256

from pptx.enum.shapes import MSO_SHAPE_TYPE

from src.services.assembly_google_merge import NOTES_END, NOTES_START, ROLES


def textbox(ident, title, words, description=''):
    return {
        'objectId': ident, 'title': title, 'description': description,
        'size': {axis: {'unit': 'EMU', 'magnitude': 3000000} for axis in ('width', 'height')},
        'transform': {'unit': 'EMU', 'translateX': 25000, 'translateY': 50000, 'scaleX': 1, 'scaleY': 0.25},
        'shape': {'shapeType': 'TEXT_BOX', 'text': {'textElements': [
            {'paragraphMarker': {'style': {'alignment': 'START'}}},
            {'textRun': {'content': words + '\n', 'style': {'fontFamily': 'Georgia'}}},
        ]}},
    }


def notes(page_id, value):
    ident = page_id + '_notes'
    return {'objectId': page_id + '_notes_page', 'notesProperties': {'speakerNotesObjectId': ident},
            'pageElements': [textbox(ident, '', value)]}


def native_deck(words='120', revision='revision-1'):
    slides = []
    for role in ROLES:
        page_id = 'slide_' + role
        slides.append({'objectId': page_id, 'pageElements': [textbox(role + '_value', 'gp.' + role + '.value', words)],
                       'slideProperties': {'notesPage': notes(page_id, NOTES_START + '\n' + words + '\n' + NOTES_END)}})
    return {'revisionId': revision, 'slides': slides}


def _rgb(value):
    return {name: channel / 255 for name, channel in zip(('red', 'green', 'blue'), bytes.fromhex(value), strict=True)}


def from_powerpoint(deck):
    """Expose managed fields and their native-equivalent geometry, fill and type."""
    result = []
    for native in deck.slides:
        objects = []
        for shape in native.shapes:
            props = shape._element.xpath('./*/p:cNvPr')[0]
            title = props.get('title', '')
            ident = 'object_' + sha256(title.encode()).hexdigest()[:16]
            obj = textbox(ident, title, shape.text if shape.has_text_frame else '', props.get('descr', ''))
            objects.append(obj)
            # Google normalizes the object's base size and encodes effective
            # width/height in its transform, including invisible bar segments.
            obj['transform'].update(translateX=shape.left, translateY=shape.top,
                                    scaleX=shape.width / 3000000, scaleY=shape.height / 3000000)
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                obj.pop('shape')
                obj['image'] = {'contentUrl': 'https://images.example/' + ident}
                continue
            if shape.shape_type != MSO_SHAPE_TYPE.TEXT_BOX:
                preset = shape._element.xpath('p:spPr/a:prstGeom/@prst')
                obj['shape']['shapeType'] = {'roundRect': 'ROUND_RECTANGLE', 'ellipse': 'ELLIPSE'}.get(
                    preset[0] if preset else '', 'RECTANGLE')
            colors = shape._element.xpath('p:spPr/a:solidFill/a:srgbClr/@val')
            if colors or shape._element.xpath('p:spPr/a:noFill'):
                fill = {'solidFill': {'color': {'rgbColor': _rgb(colors[0] if colors else 'FFFFFF')}, 'alpha': 1}}
                if not colors:
                    fill['propertyState'] = 'NOT_RENDERED'
                obj['shape']['shapeProperties'] = {'shapeBackgroundFill': fill}
            if shape.has_text_frame and shape.text_frame.paragraphs[0].runs:
                run = shape.text_frame.paragraphs[0].runs[0]
                style = obj['shape']['text']['textElements'][1]['textRun']['style']
                rgb = run._r.xpath('a:rPr/a:solidFill/a:srgbClr/@val')
                if rgb:
                    style['foregroundColor'] = {'opaqueColor': {'rgbColor': _rgb(rgb[0])}}
                if run.font.size:
                    style['fontSize'] = {'magnitude': run.font.size.pt, 'unit': 'PT'}
        role = objects[0]['title'].split('.')[1]
        page_id = 'slide_' + role
        result.append({'objectId': page_id, 'pageElements': objects,
                       'slideProperties': {'isSkipped': native._element.get('show') == '0',
                                           'notesPage': notes(page_id, native.notes_slide.notes_text_frame.text)}})
    return {'revisionId': 'native-revision', 'slides': result}


def registered(doc):
    """Apply setup's nine native ownership stamps without changing a field."""
    from src.services.assembly_google_merge import initialize_native_pages
    fields = {obj['objectId']: obj for page in doc['slides'] for obj in page['pageElements']}
    for op in initialize_native_pages(doc):
        if 'updatePageElementAltText' in op:
            update = op['updatePageElementAltText']
            fields[update['objectId']]['description'] = update['description']
    return doc
