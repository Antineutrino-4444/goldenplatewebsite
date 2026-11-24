from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile

import pytest
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from src.services.presentation_exports import generate_deck
from src.services.presentation_intro import INTRO_MARKER, MORPH_MARK, MORPH_WORDMARK, OUTRO_MARKER, SIGNATURE_FILM


P14 = 'http://schemas.microsoft.com/office/powerpoint/2010/main'
P159 = 'http://schemas.microsoft.com/office/powerpoint/2015/09/main'
NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'}


@pytest.fixture(params=['dark', 'light'])
def assembly(request):
    snapshot = dict(school_name='North Campus', school_code='NC', generated_at='2026-11-20T13:00:00+00:00',
                    totals=dict(clean=0, total=0, clean_percentage=0, session_count=0),
                    latest=None, previous=None, change=None)
    blob = generate_deck('assembly', request.param, snapshot)
    return Presentation(BytesIO(blob)), blob, request.param, snapshot


def test_tutorial_signature_morph_preserves_the_original_results_masthead(assembly):
    deck, _, theme, snapshot = assembly
    opening, results = deck.slides[0], deck.slides[1]
    source = {s.name: s for s in opening.shapes}
    destination = {s.name: s for s in results.shapes}
    assert source[MORPH_MARK].shape_type == destination[MORPH_MARK].shape_type == MSO_SHAPE_TYPE.PICTURE
    assert source[MORPH_MARK].image.size == (448, 448)
    assert destination[MORPH_MARK].image.size == (768, 768)
    assert source[MORPH_WORDMARK].text == destination[MORPH_WORDMARK].text == 'golden plate'
    assert source[MORPH_WORDMARK].text_frame.paragraphs[0].runs[0].font.name == 'Georgia'
    assert destination[MORPH_WORDMARK].text_frame.paragraphs[0].runs[0].font.name == 'Newsreader'
    assert source[MORPH_WORDMARK].top > source[MORPH_MARK].top + source[MORPH_MARK].height
    for name in (MORPH_MARK, MORPH_WORDMARK):
        assert 2 * source[name].left + source[name].width == deck.slide_width
        assert not results._element.xpath(f'.//p:timing//*[@spid="{destination[name].shape_id}"]')
    canonical = Presentation(BytesIO(generate_deck('overview', theme, snapshot))).slides[0]
    standalone = {s.name: s for s in canonical.shapes}
    for receiving, original in [(MORPH_MARK, 'Plate mark'), (MORPH_WORDMARK, 'Publisher'), ('school', 'school')]:
        shape, reference = destination[receiving], standalone[original]
        assert (shape.left, shape.top, shape.width, shape.height) == (
            reference.left, reference.top, reference.width, reference.height)
        if shape.has_text_frame:
            assert shape.text_frame._txBody.xml == reference.text_frame._txBody.xml
    assert destination[MORPH_WORDMARK].left + destination[MORPH_WORDMARK].width < destination['school'].left

    # The two logo sequences advance automatically. The results slide owns
    # the incoming Morph and waits for the presenter after building its figures.
    for slide in deck.slides:
        transitions = slide._element.xpath('.//p:transition')
        assert transitions
        role = slide._element.cSld.get('name')
        if role in (INTRO_MARKER, OUTRO_MARKER):
            advance = '1500' if role == INTRO_MARKER else '2283'
            assert all(t.get('advClick') == '0' and t.get('advTm') == advance for t in transitions)
        else:
            assert all(t.get('advClick') == '1' and t.get('advTm') is None for t in transitions)
        morphs = list(slide._element.iter(f'{{{P159}}}morph'))
        if slide.part == results.part:
            assert len(morphs) == 1 and morphs[0].get('option') == 'byObject'
            assert morphs[0].getparent().get(f'{{{P14}}}dur') == '850'
            choice = morphs[0].getparent().getparent()
            assert choice.nsmap[choice.get('Requires')] == P159
            assert transitions[-1].find('p:fade', NS) is not None
        else:
            assert not morphs


def test_one_offline_signature_film_drives_both_bookends(assembly):
    deck, blob, theme, snapshot = assembly
    # The dark film is the supplied 4K master. The light film uses its frame timing.
    reveal_films = {
        'dark': 'bad223619751f92e550835242979dda3354472bcd41c5ec3236e3c5a53580e45',
        'light': '2b70d850d8ca31eafa30f43be5f235c69662c509bf75419e738f7fce952bee48',
    }
    assert [s.text for s in deck.slides[-2].shapes] == ['Be Green,', 'Do Good']
    with ZipFile(BytesIO(blob)) as package:
        films = [name for name in package.namelist() if name.startswith('ppt/media/') and name.endswith('.mp4')]
        assert len(films) == 1 and sha256(package.read(films[0])).hexdigest() == reveal_films[theme]

    for page, marker in [(deck.slides[0], INTRO_MARKER), (deck.slides[-1], OUTRO_MARKER)]:
        assert page._element.cSld.get('name') == marker
        assert page.notes_slide.notes_text_frame.text == snapshot['school_name']
        film, plate, word = page.shapes
        assert [s.name for s in page.shapes] == [SIGNATURE_FILM, MORPH_MARK, MORPH_WORDMARK]
        assert film.shape_type == MSO_SHAPE_TYPE.MEDIA
        assert (film.left, film.top, film.width, film.height) == (0, 0, deck.slide_width, deck.slide_height)
        assert (plate.left.pt, plate.top.pt, plate.width.pt, plate.height.pt) == (424, 174, 112, 112)
        assert (word.left.pt, word.top.pt, word.width.pt, word.height.pt) == (325, 294, 310, 37)
        assert not film._element.xpath('.//a:hlinkClick')
        media_rels = [r for r in page.part.rels.values() if r.reltype.rsplit('/', 1)[-1] in {'media', 'video'}]
        assert len(media_rels) == 2 and not any(r.is_external for r in media_rels)
        assert all(str(r.target_part.partname)[1:] == films[0] for r in media_rels)
        assert len(page._element.xpath('p:timing')) == 1
        assert page._element.xpath('.//p:cond[@evt="onBegin"]/p:tn[@val="2"]')
        assert not page._element.xpath('.//p:cTn[@nodeType="clickEffect" or @repeatCount]')
        assert len(page._element.xpath(f'.//p:video//p:spTgt[@spid="{film.shape_id}"]')) == 1
        play = page._element.xpath('.//p:cTn[@presetClass="mediacall"]')[0]
        assert play.find('p:stCondLst/p:cond', NS).get('delay') == '0'
        cmd = play.find('.//p:cmd', NS)
        assert cmd.get('cmd') == 'playFrom(0.0)'
        assert cmd.find('p:cBhvr/p:tgtEl/p:spTgt', NS).get('spid') == str(film.shape_id)
        assert cmd.find('p:cBhvr/p:cTn', NS).get('dur') == '1733'

        rise = page._element.xpath(f'.//p:cTn[@presetClass][.//p:spTgt[@spid="{word.shape_id}"]]')
        assert {node.get('presetClass') for node in rise} == {'entr', 'path'}
        assert all(node.get('accel') == node.get('decel') == '50000' for node in rise)
        assert all(node.find('p:stCondLst/p:cond', NS).get('delay') == '950' for node in rise)
        assert page._element.xpath('.//p:animEffect[@filter="wipe(down)"]/p:cBhvr/p:cTn[@dur="500"]')
        assert page._element.xpath('.//p:animMotion/p:cBhvr/p:cTn[@dur="500"]')
        for shape, kind in [(plate, 'entr'), (film, 'exit')]:
            handoff = page._element.xpath(f'.//p:cTn[@presetClass="{kind}"][.//p:spTgt[@spid="{shape.shape_id}"]]')
            assert len(handoff) == 1
            expected = '1460' if marker == INTRO_MARKER else '1650'
            assert handoff[0].find('p:stCondLst/p:cond', NS).get('delay') == expected
