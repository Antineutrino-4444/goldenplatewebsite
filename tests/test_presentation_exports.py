from io import BytesIO
import re
from zipfile import ZipFile

import pytest
from lxml import etree
from pptx import Presentation

from src.services import presentation_fonts
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
    assert len(opened.slides) == 6
    assert str(opened.slides[0].background.fill.fore_color.rgb) == PALETTES[theme].paper
    with ZipFile(BytesIO(doc)) as archive:
        roots = [etree.fromstring(archive.read(f'ppt/slides/slide{i}.xml')) for i in range(1, 7)]
    for index, root in enumerate(roots):
        assert bool(root.find('p:transition', NS) is not None) == (platform == 'powerpoint')
        valid_ids = set(root.xpath('//p:cNvPr/@id', namespaces=NS))
        assert set(root.xpath('//p:spTgt/@spid', namespaces=NS)) <= valid_ids
        if index < 5:
            assert root.xpath('//a:t[text()="Records as of Nov 20, 2026 at 13:00 UTC"]', namespaces=NS)
    assert ('wipe(right)' in roots[0].xpath('//p:animEffect/@filter', namespaces=NS)) == (platform == 'powerpoint')
    assert ('fade' in roots[2].xpath('//p:animEffect/@filter', namespaces=NS)) == (platform == 'powerpoint')
    for text in ('Community Lunch', 'Autumn Lunch', '+45', '+15%', 'Latest − previous'):
        assert text in roots[2].xpath('//a:t/text()', namespaces=NS)
    assert opened.slides[1]._element.cSld.get('name') == 'Community Lunch'
    last_texts = roots[4].xpath('//a:t/text()', namespaces=NS)
    assert any('portion' in text.lower() for text in last_texts)
    assert any('plate' in text.lower() for text in last_texts)
    assert len(roots[4].xpath('//p:pic', namespaces=NS)) == 1  # Logo only.
    first, second = opened.slides[5].shapes
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
        assert archive.read('ppt/slides/slide1.xml') == etree.tostring(roots[0], encoding='UTF-8', xml_declaration=True, standalone=True)


def test_empty_and_first_result_are_distinguished(results):
    results.update(previous=None, change=None)
    results['latest'].update(name='Lunch & <Thursday>\x00', clean=1, student_clean=1, faculty_clean=0,
                             dirty=0, very_dirty=0, total=1, clean_percentage=100)
    results['totals'].update(clean=1, total=1, clean_percentage=100, session_count=1)
    deck = Presentation(BytesIO(generate_deck('assembly', 'light', results)))
    assert len(deck.slides) == 4
    assert [line.text for line in deck.slides[-1].shapes] == ['Be Green,', 'Do Good']
    labels = {shape.name: ' '.join(shape.text.split()) for shape in deck.slides[0].shapes if shape.has_text_frame}
    assert labels['all_clean'] == '1 clean plate'
    assert labels['share'] == '100% of 1 recorded plate across 1 lunch'
    assert labels['latest_name'] == 'Lunch & <Thursday>'
    assert labels['latest_counts'] == '1 of 1 plate was clean'
    assert labels['change_heading'] == 'First recorded lunch'
    assert 'latest_change' not in labels and 'change_units' not in labels
    breakdown_counts = next(shape for shape in deck.slides[1].shapes if shape.name == 'latest_counts')
    assert ' '.join(breakdown_counts.text.split()) == '1 of 1 plate was clean'
    assert '1 of 1 plate was clean.' in deck.slides[0].notes_slide.notes_text_frame.text
    assert '1 of 1 recorded plate was clean.' in deck.slides[1].notes_slide.notes_text_frame.text
    results['latest'].update(clean=0, student_clean=0, dirty=10, total=10, clean_percentage=0)
    results['totals'].update(clean=0, total=10, clean_percentage=0)
    page = Presentation(BytesIO(generate_deck('overview', 'light', results))).slides[0]
    labels = {shape.name: ' '.join(shape.text.split()) for shape in page.shapes if shape.has_text_frame}
    assert labels['latest_rate'] == '0%' and labels['latest_counts'] == '0 of 10 plates were clean'
    results.update(latest=None, totals=dict(clean=0, total=0, clean_percentage=0, session_count=0))
    deck = Presentation(BytesIO(generate_deck('assembly', 'dark', results)))
    assert len(deck.slides) == 3
    labels = {shape.name: shape.text for shape in deck.slides[0].shapes if shape.has_text_frame}
    assert labels['all_clean'] == '0 clean plates'
    assert labels['share'] == 'No plates recorded yet'
    assert labels['latest_name'] == 'No lunch results yet'
    assert not {'goal_label', 'progress_track', 'latest_date', 'latest_counts', 'rate_heading',
                'latest_rate', 'change_heading', 'latest_change', 'change_units'}.intersection(labels)


@pytest.mark.parametrize('custom', [False, True])
def test_full_school_or_custom_label_fits_masthead_on_every_results_slide(results, custom):
    long_name = ('École internationale des sciences et des arts de la communauté de la vallée du Saint-Laurent '
                 'et du Centre régional des programmes bilingues pour les élèves du secondaire')
    actual_name = 'Aurora School' if custom else long_name
    results.update(school_name=actual_name, school_label=long_name if custom else None)
    deck = Presentation(BytesIO(generate_deck('assembly', 'dark', results)))
    for slide in list(deck.slides)[:-1]:
        shapes = {shape.name: shape for shape in slide.shapes}
        label = shapes['school']
        assert ' '.join(label.text.splitlines()) == long_name
        assert len(label.text.splitlines()) > 1
        assert label.top >= 0 and label.top + label.height < shapes['Masthead rule'].top
        assert label.left >= shapes['Publisher'].left + shapes['Publisher'].width
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
    page = deck.slides[0]
    labels = [' '.join(shape.text.split()) for shape in page.shapes if shape.has_text_frame]
    assert goal_text in labels
    assert (f'50% of {clean * 2} recorded plates across 2 lunches' if clean else 'No plates recorded yet') in labels
    widths = {shape.name: shape.width.pt for shape in page.shapes}
    # Chromium quantizes CSS layout to 1/64 pixel when compiling the source.
    browser_unit_pt = .75 / 64
    assert widths['progress_track'] == pytest.approx(398, abs=browser_unit_pt)
    assert widths.get('Clean plates toward milestone', 0) == pytest.approx(goal_width, abs=browser_unit_pt)
    assert widths.get('Clean plates above milestone', 0) == pytest.approx(extra_width, abs=browser_unit_pt)
    fills = {shape.name: str(shape.fill.fore_color.rgb) for shape in page.shapes
             if shape.name in ('Clean plates toward milestone', 'Clean plates above milestone')}
    if goal_width:
        swatch = next(shape for shape in deck.slides[1].shapes if shape.name == 'Student clean plates key')
        assert fills['Clean plates toward milestone'] == str(swatch.fill.fore_color.rgb)
    if extra_width:
        change = next(shape for shape in page.shapes if shape.name == 'latest_change')
        assert fills['Clean plates above milestone'] == str(change.text_frame.paragraphs[0].runs[0].font.color.rgb)


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
    assert shapes['latest_heading'].text == 'Latest lunch'
    assert ' '.join(shapes['rate_heading'].text.split()) == 'Clean-plate rate'
    assert shapes['latest_rate'].text == '90%'
    assert ' '.join(shapes['latest_counts'].text.split()) == '90 of 100 plates were clean'
    assert ' '.join(shapes['change_heading'].text.split()) == 'Change from previous lunch'
    assert shapes['latest_change'].text == '−1' and shapes['change_units'].text == 'percentage point'


@pytest.mark.parametrize('theme', ('light', 'dark'))
def test_printable_results_as_pdf(results, theme):
    for kind, pages in [('assembly', 6), ('overview', 1)]:
        pdf = generate_deck(kind, theme, results, 'pdf')
        assert pdf.startswith(b'%PDF-')
        assert b'/Count ' + str(pages).encode() + b' ' in pdf


@pytest.mark.parametrize('theme', ('light', 'dark'))
def test_latest_lunch_chart_and_legend_follow_the_school_snapshot(results, theme):
    latest = results['latest']
    latest.update(student_clean=6, faculty_clean=0, dirty=3, very_dirty=1,
                  total=10, clean=6, clean_percentage=60)
    deck = Presentation(BytesIO(generate_deck('assembly', theme, results, 'google-slides')))
    shapes = {shape.name: shape for shape in deck.slides[1].shapes}
    assert shapes['latest_counts'].text == '6 of 10 plates were clean'
    assert shapes['rate'].text == '60%'
    assert shapes['faculty_clean'].text == '0'
    assert 'Faculty clean plates share' not in shapes
    track = shapes['distribution']
    left = track.left
    for label, fraction in [('Student clean plates', .6), ('Dirty plates', .3), ('Very dirty plates', .1)]:
        segment = shapes[label + ' share']
        assert segment.left == pytest.approx(left, abs=1)
        assert segment.width == pytest.approx(track.width * fraction, abs=1)
        assert segment.fill.fore_color.rgb == shapes[label + ' key'].fill.fore_color.rgb
        left = segment.left + segment.width
    assert left == pytest.approx(track.left + track.width, abs=1)


@pytest.mark.parametrize(('previous_rate', 'latest_rate', 'change', 'summary'), [
    (0, 100, '+100%', '100 percentage points higher'),
    (100, 0, '−100%', '100 percentage points lower'),
    (75.2, 74.2, '−1%', '1 percentage point lower'),
    (50, 51, '+1%', '1 percentage point higher'),
    (72.4, 74.1, '+1.7%', '1.7 percentage points higher'),
    (12.5, 12.5, '0%', 'No change in clean-plate rate'),
])
def test_comparison_chart_uses_a_fixed_scale_and_absolute_point_difference(
        results, previous_rate, latest_rate, change, summary):
    for key, rate in [('previous', previous_rate), ('latest', latest_rate)]:
        clean = round(10 * rate)
        results[key].update(clean_percentage=rate, total=1000, clean=clean, student_clean=clean,
                            faculty_clean=0, dirty=1000 - clean, very_dirty=0)
    deck = Presentation(BytesIO(generate_deck('assembly', 'light', results)))
    table = {shape.name: shape for shape in deck.slides[2].shapes}
    chart = {shape.name: shape for shape in deck.slides[3].shapes}
    assert table['delta_rate'].text == change
    assert ' '.join(chart['rate_comparison'].text.split()) == summary
    assert chart['prev_track'].left == chart['curr_track'].left
    assert chart['prev_track'].width == chart['curr_track'].width
    for prefix, rate, session in [('prev', previous_rate, results['previous']), ('curr', latest_rate, results['latest'])]:
        track, fill = chart[prefix + '_track'], chart[prefix + '_fill']
        assert fill.left == track.left
        assert fill.width == pytest.approx(track.width * rate / 100, abs=1)
        assert chart[prefix + '_rate'].text == f'{rate:g}%'
        assert chart[prefix + '_name'].text == session['name']
        assert chart[prefix + '_counts'].text == f"{session['clean']:,} of 1,000 plates were clean"
    assert {'0%', '100%'} <= {shape.text for shape in chart.values() if shape.has_text_frame}
    assert summary in deck.slides[3].notes_slide.notes_text_frame.text


def test_missing_or_invalid_rates_use_actual_counts_and_missing_result_is_explicit(results):
    results.pop('change')
    del results['previous']['clean_percentage']
    results['latest']['clean_percentage'] = -3
    deck = Presentation(BytesIO(generate_deck('assembly', 'dark', results)))
    chart = {shape.name: shape for shape in deck.slides[3].shapes}
    assert chart['prev_rate'].text == '75%' and chart['curr_rate'].text == '90%'
    assert chart['rate_comparison'].text == '15 percentage points higher'
    results['previous'].update(clean=0, total=0)
    deck = Presentation(BytesIO(generate_deck('assembly', 'dark', results)))
    chart = {shape.name: shape for shape in deck.slides[3].shapes}
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
    italic = [(page, shape.name, run.font.name, run.font.bold)
              for page, slide in enumerate(deck.slides, start=1) for shape in slide.shapes if shape.has_text_frame
              for paragraph in shape.text_frame.paragraphs for run in paragraph.runs if run.font.italic]
    assert italic == [(1, 'latest_date', 'Georgia', False), (2, 'latest_date', 'Georgia', False),
                      (3, 'prev_date', 'Georgia', False), (3, 'curr_date', 'Georgia', False)]
    for page, name in [(0, 'goal_label'), (3, 'rate_comparison')]:
        shape = next(shape for shape in deck.slides[page].shapes if shape.name == name)
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
        faces = [_pdf_face('Recorded plates', 'Georgia', False), _pdf_face('Previous lunch', 'Georgia', True),
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
