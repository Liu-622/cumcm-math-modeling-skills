#!/usr/bin/env python3
from __future__ import annotations

import importlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys

COMMANDS = ["typst", "xelatex", "latexmk", "drawio", "draw.io", "pdftoppm", "mutool", "magick"]
PACKAGES = {
    "numpy": "numpy",
    "scipy": "scipy",
    "pandas": "pandas",
    "matplotlib": "matplotlib",
    "sklearn": "scikit-learn",
    "openpyxl": "openpyxl",
}


def command_record(name: str) -> dict[str, object]:
    path = shutil.which(name)
    record: dict[str, object] = {"name": name, "status": "MISS", "path": path, "version": None}
    if not path:
        return record
    record["status"] = "FOUND"
    for flag in ("--version", "-version", "-v"):
        try:
            result = subprocess.run(
                [path, flag], text=True, encoding="utf-8", errors="replace",
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        output = (result.stdout or "").strip().splitlines()
        if result.returncode == 0 and output:
            record["status"] = "OK"
            record["version"] = output[0][:300]
            break
    return record


def package_record(module_name: str, distribution: str) -> dict[str, object]:
    try:
        importlib.import_module(module_name)
        try:
            version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            version = None
        return {"name": distribution, "module": module_name, "status": "OK", "version": version}
    except Exception as exc:
        return {"name": distribution, "module": module_name, "status": "MISS", "error": type(exc).__name__}


def main() -> int:
    payload = {
        "platform": platform.platform(),
        "python": {"status": "OK", "executable": sys.executable, "version": platform.python_version()},
        "commands": [command_record(name) for name in COMMANDS],
        "python_packages": [package_record(module, dist) for module, dist in PACKAGES.items()],
        "note": "FOUND means the command exists but its version probe was not confirmed; evaluate required tools for the selected workflow.",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
