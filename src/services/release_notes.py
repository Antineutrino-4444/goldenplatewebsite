"""Read published release entries in the format shared by the portal and email."""

import re
from pathlib import Path

RELEASE_NOTES_PATH = Path(__file__).resolve().parents[2] / 'RELEASE_NOTES.md'
VERSION = r'(?:0|[1-9][0-9]{0,8})(?:\.(?:0|[1-9][0-9]{0,8})){3}'
RELEASE_HEADING = re.compile(rf'^## ({VERSION})[ \t]*$', re.MULTILINE)


def version_key(version):
    # Fixed-width numeric components let SQL compare versions atomically.
    return ''.join(part.zfill(9) for part in version.split('.'))


def read_release_notes():
    sections = RELEASE_HEADING.split(RELEASE_NOTES_PATH.read_text(encoding='utf-8'))
    return {
        version: body.strip()
        for version, body in zip(sections[1::2], sections[2::2])
        if body.strip()
    }
