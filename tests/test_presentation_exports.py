from io import BytesIO
from zipfile import ZipFile

import pytest
from lxml import etree
from pptx import Presentation

from src.services.presentation_exports import PALETTES, generate_deck


NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}


@pytest.fixture
def results():
    latest = dict(name='Community Lunch', date='2026-11-18', student_clean=85, faculty_clean=5,
                  clean=90, dirty=8, very_dirty=2, total=100, clean_percentage=90)
    prior = dict(latest, name='Autumn Lunch', date='2026-11-09', student_clean=43, faculty_clean=2,
                 clean=45, dirty=12, very_dirty=3, total=60, clean_percentage=75)
    return dict(school_name='Aurora School', school_code='AUR', generated_at='2026-11-20T13:00:00+00:00',
                totals=dict(clean=135, total=160, clean_percentage=84.4, session_count=2),
                latest=latest, previous=prior, change=dict(clean=45, total=40, clean_percentage_points=15.0))


@pytest.mark.parametrize('theme', ('light', 'dark'))
@pytest.mark.parametrize('platform', ('powerpoint', 'google-slides'))
def test_assembly_exports_editable_dated_results_with_expected_motion(results, theme, platform):
    doc = generate_deck('assembly', theme, results, platform)
    opened = Presentation(BytesIO(doc))
    assert len(opened.slides) == 4
    assert str(opened.slides[0].background.fill.fore_color.rgb) == PALETTES[theme].paper
    with ZipFile(BytesIO(doc)) as archive:
        roots = [etree.fromstring(archive.read(f'ppt/slides/slide{i}.xml')) for i in range(1, 5)]
    for root in roots:
        assert bool(root.find('p:transition', NS) is not None) == (platform == 'powerpoint')
        valid_ids = set(root.xpath('//p:cNvPr/@id', namespaces=NS))
        assert set(root.xpath('//p:spTgt/@spid', namespaces=NS)) <= valid_ids
        assert root.xpath('//a:t[text()="Records as of Nov 20, 2026 at 13:00 UTC"]', namespaces=NS)
    assert ('wipe(right)' in roots[0].xpath('//p:animEffect/@filter', namespaces=NS)) == (platform == 'powerpoint')
    assert ('fade' in roots[2].xpath('//p:animEffect/@filter', namespaces=NS)) == (platform == 'powerpoint')
    for text in ('Community Lunch', 'Autumn Lunch', '+45', '+15 pts'):
        assert text in roots[2].xpath('//a:t/text()', namespaces=NS)
    overview = generate_deck('overview', theme, results, platform)
    assert len(Presentation(BytesIO(overview)).slides) == 1
    with ZipFile(BytesIO(overview)) as archive:
        assert archive.read('ppt/slides/slide1.xml') == etree.tostring(roots[0], encoding='UTF-8', xml_declaration=True, standalone=True)


def test_empty_and_first_result_are_distinguished(results):
    results.update(previous=None, change=None)
    results['latest'].update(name='Lunch & <Thursday>\x00', clean=0, student_clean=0, faculty_clean=0,
                             total=10, clean_percentage=0)
    deck = Presentation(BytesIO(generate_deck('assembly', 'light', results)))
    assert len(deck.slides) == 3
    text = [shape.text for shape in deck.slides[0].shapes if shape.has_text_frame]
    assert 'Lunch & <Thursday>' in text
    assert 'First recorded lunch' in text
    assert '0 of 10 plates were clean' in text
    results.update(latest=None, totals=dict(clean=0, total=0, clean_percentage=0, session_count=0))
    deck = Presentation(BytesIO(generate_deck('assembly', 'dark', results)))
    assert len(deck.slides) == 2
    assert 'No plates recorded yet' in [shape.text for shape in deck.slides[0].shapes if shape.has_text_frame]


@pytest.mark.parametrize(('clean', 'goal_text', 'goal_width', 'extra_width'), [
    (0, '100 to the 100-plate goal', 0, 0),
    (50, '50 to the 100-plate goal', 199, 0),
    (100, '100-plate goal reached', 398, 0),
    (200, '100 above the 100-plate goal', 199, 199),
])
def test_overview_displays_school_count_milestone_and_recorded_share(results, clean, goal_text, goal_width, extra_width):
    results.update(milestone=100, totals=dict(clean=clean, total=clean * 2, clean_percentage=50 if clean else 0,
                                              session_count=2 if clean else 0))
    page = Presentation(BytesIO(generate_deck('overview', 'dark', results))).slides[0]
    labels = [shape.text for shape in page.shapes if shape.has_text_frame]
    assert goal_text in labels
    assert (f'50% of {clean * 2} recorded plates' if clean else 'No plates recorded yet') in labels
    widths = {shape.name: shape.width.pt for shape in page.shapes}
    assert widths.get('Clean plates toward milestone', 0) == pytest.approx(goal_width)
    assert widths.get('Clean plates above milestone', 0) == pytest.approx(extra_width)


@pytest.mark.parametrize('theme', ('light', 'dark'))
def test_printable_results_as_pdf(results, theme):
    for kind, pages in [('assembly', 4), ('overview', 1)]:
        pdf = generate_deck(kind, theme, results, 'pdf')
        assert pdf.startswith(b'%PDF-')
        assert b'/Count ' + str(pages).encode() + b' ' in pdf
