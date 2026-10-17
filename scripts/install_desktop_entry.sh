#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${HOME}/.local/share/applications"
mkdir -p "$APP_DIR"
cat > "${APP_DIR}/juraos-sorter.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=JuraOS Dokumentensortierer
Comment=Juristische Dokumente prüfen und sicher ablegen
Exec="${ROOT}/start-juraos.sh"
Path=${ROOT}
Terminal=false
Categories=Office;Education;
EOF
chmod +x "${APP_DIR}/juraos-sorter.desktop"
echo "Desktop-Eintrag erstellt: ${APP_DIR}/juraos-sorter.desktop"
echo "Du findest JuraOS jetzt im KDE-Anwendungsmenü."
