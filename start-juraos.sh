#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${ROOT}/.venv/bin/python"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 ist nicht installiert. Bitte zuerst Python 3 installieren." >&2
  read -r -p "Enter zum Schließen …" _ || true
  exit 1
fi
if [[ ! -x "$PYTHON" ]]; then
  python3 -m venv "${ROOT}/.venv" || {
    echo "Die Python-Umgebung konnte nicht erstellt werden. Unter Fedora ggf. python3-virtualenv installieren." >&2
    read -r -p "Enter zum Schließen …" _ || true
    exit 1
  }
fi
if ! "$PYTHON" -c 'import PySide6, pypdf' >/dev/null 2>&1; then
  echo "Installiere JuraOS-Abhängigkeiten (nur beim ersten Start oder nach Änderungen)…"
  "$PYTHON" -m pip install --upgrade pip
  "$PYTHON" -m pip install -r "${ROOT}/requirements.txt" || {
    echo "Installation fehlgeschlagen. Internetverbindung und Python-Installation prüfen." >&2
    read -r -p "Enter zum Schließen …" _ || true
    exit 1
  }
fi
cd "$ROOT"
exec "$PYTHON" "${ROOT}/scripts/juraos_sorter_gui.py" "$@"
