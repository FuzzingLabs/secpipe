#!/usr/bin/env bash
# Extract the version from a pyproject.toml file.
# Usage: pyproject-version.sh <path/to/pyproject.toml> [default]
# Prints the version string, or the default (0.0.1) if not found.

PYPROJECT="${1:?Usage: pyproject-version.sh <pyproject.toml> [default]}"
DEFAULT="${2:-0.0.1}"

version=$(grep -m1 '^version\s*=' "${PYPROJECT}" 2>/dev/null \
    | sed 's/^version\s*=\s*//;s/"//g;s/\s*$//')

echo "${version:-${DEFAULT}}"
