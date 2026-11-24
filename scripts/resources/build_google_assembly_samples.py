"""Build both Google import examples using the connected-deck export settings."""
import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.services.presentation_exports import generate_deck


SAMPLE = {
    'school_name': 'Sample school results', 'school_code': 'SAMPLE', 'milestone': 200,
    'generated_at': '2026-11-20T17:00:00+00:00', 'reporting_timezone': 'America/New_York',
    'seed_google_session_slides': True,
    'totals': {'clean': 135, 'total': 160, 'clean_percentage': 84.4, 'session_count': 2},
    'latest': {'name': 'Friday Session', 'date': '2026-11-20', 'student_clean': 85, 'faculty_clean': 5,
               'clean': 90, 'dirty': 8, 'very_dirty': 2, 'total': 100, 'clean_percentage': 90},
    'previous': {'name': 'Monday Session', 'date': '2026-11-16', 'student_clean': 43, 'faculty_clean': 2,
                 'clean': 45, 'dirty': 12, 'very_dirty': 3, 'total': 60, 'clean_percentage': 75},
    'change': {'clean': 45, 'total': 40, 'clean_percentage_points': 15.0},
    'winner_names': {'student': 'Riley Chen', 'faculty': 'Morgan Ellis'},
    'winner_details': {
        'student': {'tickets': 8, 'next_ticket_gain': 2, 'probability': 12.5, 'pool_size': 18,
                    'grade': '10', 'house': 'Maple', 'method': 'random'},
        'faculty': {'tickets': 3, 'next_ticket_gain': 1, 'probability': 10, 'pool_size': 12, 'method': 'random'},
    },
}


def build(destination):
    destination.mkdir(parents=True, exist_ok=True)
    files = {theme: destination / f'Golden Plate - {theme.title()} (Google Slides import).pptx'
             for theme in ('dark', 'light')}
    for path in files.values():
        if path.with_name('~$' + path.name).exists():
            raise SystemExit(f'Close {path.name} in PowerPoint before rebuilding.')
    with TemporaryDirectory(dir=destination) as temporary:
        staging = Path(temporary)
        for theme, path in files.items():
            (staging / path.name).write_bytes(generate_deck('assembly', theme, SAMPLE, 'google-slides'))
        for path in files.values():
            (staging / path.name).replace(path)
            print(path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output_directory', type=Path, nargs='?',
                        default=ROOT / 'output' / 'school-assembly' / 'Website style')
    build(parser.parse_args().output_directory)
