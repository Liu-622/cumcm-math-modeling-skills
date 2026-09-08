#!/usr/bin/env bash
# Compatibility entry point; Windows PowerShell should call writing_check.py.
set -eu
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
for python_bin in python3 python; do
  if command -v "$python_bin" >/dev/null 2>&1 && "$python_bin" -c 'import sys; raise SystemExit(sys.version_info.major != 3)' >/dev/null 2>&1; then
    exec "$python_bin" "$script_dir/writing_check.py" "$@"
  fi
done
echo "ERROR: Python 3 is unavailable; run writing_check.py with a verified interpreter." >&2
exit 2
