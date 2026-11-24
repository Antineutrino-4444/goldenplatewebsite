"""Import-safe Slides artwork and semantic titles used by cloud refreshes."""
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
from io import BytesIO

from PIL import Image, ImageDraw
from lxml import etree
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Pt

from src.services.presentation_reels import CATEGORIES
from src.services.presentation_winner import WINNER_PHOTOS


SLIDE_ROLES = ('overview', 'breakdown', 'comparison', 'rates', 'reminders', 'signoff',
               'winner', 'intro', 'outro')


def google_text_top(item):
    # Slides puts the visible ink of the large, top-aligned Newsreader lines
    # lower than PowerPoint. Move their frames together to keep the signoff's
    # original spacing and the headline clear of the overview subtitle.
    if item.face == 'Newsreader' and item.name in ('all_clean', 'Be Green', 'Do Good'):
        return item.y - .16 * item.size
    return item.y


def _award_description(role, snapshot, description):
    person = (snapshot.get('winner_keys') or {}).get(role) or (snapshot.get('winner_names') or {}).get(role)
    key = sha256(str(person).encode()).hexdigest() if person else 'none'
    return f'{description} [gp-award:{key}]'


def mark_google_objects(slide, template_index, snapshot):
    # Drive imports OOXML alt text into PageElement.title/description. Shape
    # names alone are not stable once a presentation is converted to Slides.
    for shape in slide.shapes:
        props = shape._element.xpath('./*/p:cNvPr')[0]
        props.set('title', f'gp.{SLIDE_ROLES[template_index]}.{shape.name}')
        if shape.name in ('winner_name_student', 'winner_name_faculty'):
            role = shape.name.removeprefix('winner_name_')
            props.set('descr', _award_description(role, snapshot, role.title() + ' winner'))
        # A refresh can preserve manual edits when that source object hasn't
        # changed. Hash semantic shape content and media, independent of the
        # local OOXML numeric identifiers, which can shift on another export.
        content = deepcopy(shape._element)
        content.xpath('./*/p:cNvPr')[0].attrib.pop('id')
        desc = props.get('descr', '')
        for blip in content.xpath('.//a:blip'):
            embed = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed'
            image_hash = sha256(slide.part.related_part(blip.get(embed)).blob).hexdigest()
            blip.set(embed, image_hash)
            desc = f'{desc} [gp-image:{image_hash[:16]}]'.strip()
        digest = sha256(etree.tostring(content, method='c14n', exclusive=True)).hexdigest()[:16]
        props.set('descr', f'{desc} [gp-template:{digest}]'.strip())


def add_google_photo_targets(slide, background, snapshot):
    # Google Slides can replace an existing image with a crop in the same
    # frame. Match the slide paper so an unfilled slot is unobtrusive on stage.
    image = BytesIO()
    Image.new('RGB', (164, 205), '#' + background).save(image, 'PNG')
    for role, (name, description, x) in zip(('student', 'faculty'), WINNER_PHOTOS.values(), strict=True):
        image.seek(0)
        picture = slide.shapes.add_picture(image, Pt(x), Pt(168), Pt(164), Pt(205))
        picture.name = name
        picture._element.nvPicPr.cNvPr.set('descr', _award_description(role, snapshot, description))


@lru_cache(maxsize=8)
def _corner_mask(paper, right):
    # Two small native image objects clip the fill. Compound PowerPoint paths
    # with holes are not reliable editable geometry in Google Slides.
    size = 160
    image = Image.new('RGBA', (size, size), '#' + paper if paper else (0, 0, 0, 0))
    if paper:
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((0, 0, 2 * size - 1, size - 1), radius=.4 * size, fill=(0, 0, 0, 0))
    if right:
        image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    target = BytesIO()
    image.save(target, 'PNG')
    return target.getvalue()


def _bar_masks(slide, track, paper):
    # Cover the entry path without a freeform aperture. The rate chart places
    # these wings below its overlying session labels.
    wing = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Pt(track.y), Pt(track.x), Pt(track.height))
    wing.fill.solid()
    wing.fill.fore_color.rgb = RGBColor.from_string(paper)
    wing.line.fill.background()
    wing.shadow.inherit = False
    for ref in wing._element.xpath('p:style/a:effectRef'):
        ref.set('idx', '0')
    wing.name = f'{track.name} entrance mask'
    masks = [wing]
    for side in ('left', 'right'):
        right = side == 'right'
        x = track.x + track.width - track.height if right else track.x
        shape = slide.shapes.add_picture(BytesIO(_corner_mask(paper, right)),
                                         Pt(x), Pt(track.y), Pt(track.height), Pt(track.height))
        shape.name = f'{track.name} {side} corner'
        shape._element.nvPicPr.cNvPr.set('descr', f'Rounded {side} edge of the bar')
        masks.append(shape)
    return masks


def _fill_tip(slide, track, fill, rounded):
    # Slides cannot change a rectangle into a rounded rectangle in place.
    # Keep the animated live fill rectangular at every possible value and
    # clip only its advancing tip. At a split color boundary the clip clears.
    clip = _corner_mask(track.color if rounded else None, True)
    x = max(track.x, track.x + fill.width - track.height)
    if rounded:
        x = track.x + fill.width - track.height
    tip = slide.shapes.add_picture(BytesIO(clip), Pt(x), Pt(track.y), Pt(track.height), Pt(track.height))
    tip.name = track.name + ' fill right corner'
    return tip


def add_google_bar_layers(slide, page, meter_track, meter_fill, *, seed, corner_fraction):
    objects = {shape.name: shape for shape in slide.shapes}
    items = {item.name: item for item in page.items}
    if 'distribution' in items:
        for _, label in CATEGORIES:
            share = objects.get(label + ' share')
            if share is not None:
                objects['distribution']._element.addnext(share._element)
        _bar_masks(slide, items['distribution'], page.background)
    elif page.template_index == 3:
        layers = []
        for prefix in ('prev', 'curr'):
            for suffix in ('_track', '_fill'):
                if prefix + suffix in objects:
                    layers.append(objects[prefix + suffix])
            track = items[prefix + '_track']
            if seed:
                fill = items[prefix + '_fill']
                rounded = not fill.hidden and 2 * corner_fraction * track.height <= fill.width < track.width
                layers.append(_fill_tip(slide, track, fill, rounded))
            layers.extend(_bar_masks(slide, track, page.background))
        # Session names can extend into an entrance mask's left wing. Keep
        # every layer of both chart bars below the editable labels.
        for position, shape in enumerate(layers, 2):
            slide.shapes._spTree.insert(position, shape._element)
    elif meter_track and meter_fill is not None:
        if seed:
            fill = items['Clean plates toward milestone']
            excess = items['Clean plates above milestone']
            rounded = not fill.hidden and excess.hidden and 2 * meter_track.radius <= fill.width < meter_track.width
            _fill_tip(slide, meter_track, fill, rounded)
        _bar_masks(slide, meter_track, page.background)
