from io import BytesIO

import pytest
from pptx import Presentation

from src.services.presentation_exports import generate_deck


@pytest.mark.parametrize('theme', ['dark', 'light'])
def test_powerpoint_reminders_keep_each_instruction_editable_and_google_retains_its_layout(theme):
    snapshot = {
        'school_name': 'School', 'generated_at': '2026-11-20T17:00:00Z',
        'totals': {'clean': 0, 'total': 0, 'session_count': 0},
        'latest': None, 'previous': None,
    }
    decks = [Presentation(BytesIO(generate_deck('assembly', theme, snapshot, platform)))
             for platform in ('powerpoint', 'google-slides')]
    powerpoint, google = [
        {shape.name: shape for shape in slide.shapes} for slide in (decks[0].slides[-3], decks[1].slides[-2])
    ]
    assert 'Serving line rule' not in powerpoint and 'Serving line rule' in google
    assert powerpoint['title'].text == google['title'].text == 'Quick Reminders'
    assert powerpoint['title'].text_frame.paragraphs[0].runs[0].font.size.pt == 17
    gold = next(shape for shape in decks[0].slides[-2].shapes if shape.name == 'Be Green')
    gold_color = gold.text_frame.paragraphs[0].runs[0].font.color.rgb
    for name, emphasis in [('Portion choice', 'fits your appetite'), ('Plate count', 'Compost Coach')]:
        shape = powerpoint[name]
        assert ' '.join(shape.text.split()) == ' '.join(google[name].text.split())
        assert shape.shape_id == google[name].shape_id
        runs = [run for paragraph in shape.text_frame.paragraphs for run in paragraph.runs]
        assert any(run.font.name == 'Newsreader' and run.font.size.pt == 51 for run in runs)
        assert any(run.font.name == 'Georgia' and run.font.size.pt == 26 for run in runs)
        assert [run.text for run in runs if run.font.color.rgb == gold_color] == [emphasis]
        assert all(run.font.name == 'Georgia' for paragraph in google[name].text_frame.paragraphs
                   for run in paragraph.runs)
