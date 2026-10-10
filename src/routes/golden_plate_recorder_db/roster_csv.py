import csv
import io


def roster_csv_reader(content, columns=(
    'Student ID', 'Last', 'Preferred', 'First', 'Grade', 'Advisor', 'House', 'Clan',
)):
    """Match roster column names without regard to order, case, or outer spaces."""
    reader = csv.DictReader(io.StringIO(content))
    canonical = {name.casefold(): name for name in columns}
    if reader.fieldnames:
        fields = [canonical.get(name.strip().casefold(), name.strip()) for name in reader.fieldnames]
        seen = set()
        for name in fields:
            if name in canonical.values() and name in seen:
                raise ValueError(f'CSV contains multiple {name} columns')
            seen.add(name)
        reader.fieldnames = fields
    return reader
