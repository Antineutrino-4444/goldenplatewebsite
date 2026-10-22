#!/bin/sh
# Run from any directory; prefer the project's installed Python environment.
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$script_dir")
if [ -x "$project_dir/venv/bin/python" ]; then
    python_bin="$project_dir/venv/bin/python"
elif [ -x "$project_dir/.venv/bin/python" ]; then
    python_bin="$project_dir/.venv/bin/python"
else
    python_bin=python3
fi
exec "$python_bin" "$script_dir/test_emails.py" "$@"
