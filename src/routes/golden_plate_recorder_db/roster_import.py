"""Read roster documents and map source columns to canonical roster fields."""

import csv
import io
import json
import re
from pathlib import Path, PurePath
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from flask import jsonify, request

from . import recorder_bp
from .security import require_admin

MAX_BYTES = 8 * 1024 * 1024
MAX_ROWS = 20000
MAX_COLUMNS = 128
MAX_CELLS = 500000
MAX_TABLES = 50

NAME_FIELDS = {
    'Preferred': ('preferred', 'preferred name', 'preferred first name', 'first', 'first name', 'given name', 'forename'),
    'Last': ('last', 'last name', 'surname', 'family name'),
}
FIELDS = {
    'student': {
        **NAME_FIELDS,
        'Student ID': ('student id', 'student number', 'student identifier', 'student no', 'id'),
        'Grade': ('grade', 'grade level', 'year', 'year group'),
        'Advisor': ('advisor', 'adviser', 'homeroom', 'form tutor'),
        'House': ('house', 'school house'),
        'Clan': ('clan',),
    },
    'teacher': {
        **NAME_FIELDS,
        'Faculty ID': ('faculty id', 'teacher id', 'staff id', 'employee id', 'id'),
    },
}


def _check_size(height, width):
    if height > MAX_ROWS or width > MAX_COLUMNS or height * width > MAX_CELLS:
        raise ValueError('The roster is too large. Use up to 20,000 rows, 128 columns, and 500,000 cells.')


def _text(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _delimited_rows(content, extension):
    if content.startswith((b'\xff\xfe', b'\xfe\xff')):
        decoded = content.decode('utf-16')
    else:
        try:
            decoded = content.decode('utf-8-sig')
        except UnicodeDecodeError:
            decoded = content.decode('cp1252')
    if '\x00' in decoded:
        raise ValueError('Save the text roster as UTF-8 or UTF-16 and try again.')
    delimiter = '\t' if extension == '.tsv' else ','
    if extension != '.tsv':
        try:
            delimiter = csv.Sniffer().sniff(decoded[:8192], delimiters=',;\t').delimiter
        except csv.Error:
            pass
    return csv.reader(io.StringIO(decoded, newline=''), delimiter=delimiter, strict=True)


def _source_tables(content, extension):
    if extension in ('.csv', '.tsv', '.txt'):
        yield 'Roster', _delimited_rows(content, extension)
        return

    if extension in ('.xlsx', '.numbers'):
        with ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > 10000 or sum(entry.file_size for entry in entries) > 64 * 1024 * 1024:
                raise ValueError('The spreadsheet expands to more data than the roster importer can accept.')

    if extension == '.numbers':
        from numbers_parser import Document

        with TemporaryDirectory(prefix='roster-') as directory:
            path = Path(directory) / 'roster.numbers'
            path.write_bytes(content)
            document = Document(path)
            for sheet in document.sheets:
                for table in sheet.tables:
                    _check_size(table.num_rows, table.num_cols)
                    yield f'{sheet.name} / {table.name}', table.iter_rows(values_only=True)
    else:
        from python_calamine import CalamineWorkbook, SheetTypeEnum, SheetVisibleEnum

        with CalamineWorkbook.from_filelike(io.BytesIO(content)) as workbook:
            for metadata in workbook.sheets_metadata:
                if metadata.typ != SheetTypeEnum.WorkSheet or metadata.visible != SheetVisibleEnum.Visible:
                    continue
                sheet = workbook.get_sheet_by_name(metadata.name)
                _check_size(sheet.total_height, sheet.total_width)
                yield sheet.name, sheet.to_python(skip_empty_area=False)


def _suggest_mapping(row, fields):
    labels = [re.sub(r'[^a-z0-9]+', '', value.casefold()) for value in row]
    mapping = {}
    for field, aliases in fields.items():
        for alias in aliases:
            label = alias.replace(' ', '')
            if label in labels:
                mapping[field] = labels.index(label)
                break
    return mapping


def read_roster(file, kind):
    if not file or not file.filename:
        raise ValueError('Choose a roster file.')
    extension = PurePath(file.filename).suffix.lower()
    if extension not in ('.csv', '.tsv', '.xlsx', '.xls', '.numbers', '.txt'):
        raise ValueError('Choose a CSV, TSV, Excel, Numbers, or delimited TXT file.')
    content = file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ValueError('Choose a roster file of 8 MB or less.')

    tables = []
    cells = 0
    try:
        for table_index, (name, source) in enumerate(_source_tables(content, extension)):
            if table_index >= MAX_TABLES:
                raise ValueError('Use a workbook with at most 50 sheets or tables.')
            rows = []
            width = 0
            for row in source:
                width = max(width, len(row))
                _check_size(len(rows) + 1, width)
                rows.append([_text(value) for value in row])
            while rows and not any(rows[-1]):
                rows.pop()
            if not rows:
                continue
            cells += len(rows) * width
            if cells > MAX_CELLS:
                raise ValueError('Use a workbook with at most 500,000 cells.')
            mapping = _suggest_mapping(rows[0], FIELDS[kind])
            tables.append({
                'name': name, 'rows': rows, 'width': width, 'mapping': mapping,
                'skip_first': bool(mapping),
            })
    except ValueError:
        raise
    except ImportError:
        raise ValueError('The server is missing the reader for this spreadsheet format.') from None
    except Exception:
        raise ValueError('Could not read the roster. Check that the file opens and is not password protected.') from None

    if not tables:
        raise ValueError('The roster file contains no data.')
    return tables


@recorder_bp.route('/rosters/<kind>/review', methods=['POST'])
def review_roster(kind):
    if not require_admin():
        return jsonify({'error': 'Admin or super admin access required'}), 403
    if kind not in FIELDS:
        return jsonify({'error': 'Unknown roster type'}), 404
    try:
        tables = read_roster(request.files.get('file'), kind)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify({'tables': tables}), 200, {'Cache-Control': 'no-store'}


def mapped_roster(file, kind):
    settings = json.loads(request.form['mapping'])
    if not isinstance(settings, dict):
        raise ValueError('Invalid roster mapping.')
    tables = read_roster(file, kind)
    table_index = settings.get('table')
    if type(table_index) is not int or not 0 <= table_index < len(tables):
        raise ValueError('Choose a sheet or table to import.')
    table = tables[table_index]
    columns = settings.get('columns')
    if (not isinstance(columns, dict)
            or any(field not in FIELDS[kind] or type(index) is not int or not 0 <= index < table['width']
                   for field, index in columns.items())
            or len(set(columns.values())) != len(columns)):
        raise ValueError('Assign a different source column to each roster field.')

    skip_first = settings.get('skip_first', False)
    generate_ids = settings.get('generate_ids', False)
    if type(skip_first) is not bool or type(generate_ids) is not bool or (generate_ids and kind != 'student'):
        raise ValueError('Invalid roster import options.')
    required = ['Preferred', 'Last']
    if kind == 'student' and not generate_ids:
        required.append('Student ID')
    if kind == 'teacher' and 'Faculty ID' in columns:
        required.append('Faculty ID')
    if not all(field in columns for field in required):
        raise ValueError('Assign columns for ' + ', '.join(required) + '.')

    rows = []
    identifiers = set()
    start = int(skip_first)
    id_field = 'Student ID' if kind == 'student' else 'Faculty ID'
    for row_number, source in enumerate(table['rows'][start:], start + 1):
        if not any(source):
            continue
        row = {field: source[index] if index < len(source) else '' for field, index in columns.items()}
        missing = [field for field in required if not row[field]]
        if missing:
            raise ValueError(f'Row {row_number} is missing {", ".join(missing)}.')
        if generate_ids:
            row[id_field] = str(len(rows) + 1)
        if id_field in row:
            identifier = row[id_field].casefold()
            if identifier in identifiers:
                raise ValueError(f'Row {row_number} repeats a {id_field}.')
            identifiers.add(identifier)
        rows.append(row)
    if not rows:
        raise ValueError('The selected sheet or table has no roster rows to import.')
    return rows, list(rows[0]), generate_ids
