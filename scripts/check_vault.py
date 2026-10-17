
#!/usr/bin/env python3
"""Prüft grundlegende Qualitätsmerkmale des JuraOS-Obsidian-Vaults."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VAULT = ROOT / "vault"

REQUIRED_TEMPLATES = [
    "Definition.md",
    "Fall.md",
    "Karteikarte.md",
    "Prüfungsschema.md",
    "Quelle.md",
    "Wochenplanung.md",
]

PRIVATE_DIRS = [
    "vault/01 Inbox/",
    "vault/02 Studium/Wochenplanung/",
    "vault/09 Prüfungen/",
    "vault/08 Quellen/Vorlesungsunterlagen/",
]

PRIVATE_EXTENSIONS = {
    ".pdf", ".epub", ".docx", ".xlsx", ".pptx",
    ".pem", ".key", ".p12", ".pfx",
}

WIKILINK = re.compile(r"!?\[\[([^\]]+)\]\]")
FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)


def markdown_files() -> list[Path]:
    return sorted(
        path
        for path in VAULT.rglob("*.md")
        if ".obsidian" not in path.parts
    )


def check_links(files: list[Path]) -> list[str]:
    errors = []

    # Alle lokalen Dateien erfassen, auch ignorierte PDFs.
    all_files = [
        path
        for path in VAULT.rglob("*")
        if path.is_file() and ".obsidian" not in path.parts
    ]

    for source in files:
        text = source.read_text(encoding="utf-8")

        for match in WIKILINK.finditer(text):
            target_text = match.group(1).split("|", 1)[0].strip()
            target_text = target_text.split("#", 1)[0].strip()

            if not target_text:
                continue

            if target_text.startswith(("http://", "https://", "mailto:")):
                continue

            # Offensichtliche Beispiel-Platzhalter nicht als Fehler werten.
            if target_text in {"Dateiname.pdf", "Beispiel.pdf"}:
                continue

            target = Path(target_text)
            candidates = [
                source.parent / target,
                VAULT / target,
            ]

            # Obsidian kann Notizen auch über ihren Namen auflösen.
            if not target.is_absolute():
                if target.suffix:
                    candidates.extend(
                        path for path in all_files
                        if path.name == target.name
                    )
                else:
                    candidates.extend(
                        path for path in all_files
                        if path.stem == target.name
                    )

            if not any(candidate.is_file() for candidate in candidates):
                errors.append(
                    f"{source.relative_to(VAULT)}: "
                    f"Linkziel nicht gefunden: [[{match.group(1)}]]"
                )

    return errors

def check_frontmatter(files: list[Path]) -> list[str]:
    errors = []

    for path in files:
        text = path.read_text(encoding="utf-8")
        if text.startswith("---") and not FRONTMATTER.match(text):
            errors.append(f"{path.relative_to(VAULT)}: Frontmatter nicht korrekt abgeschlossen")

    return errors


def check_templates() -> list[str]:
    template_dir = VAULT / "90 Templates"
    return [
        f"Vorlage fehlt: {name}"
        for name in REQUIRED_TEMPLATES
        if not (template_dir / name).is_file()
    ]


def check_tracked_private_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    tracked = [
        item.decode("utf-8", errors="replace")
        for item in result.stdout.split(b"\0")
        if item
    ]

    errors = []
    for filename in tracked:
        path = Path(filename)

        if path.suffix.lower() in PRIVATE_EXTENSIONS:
            errors.append(f"Privater Dateityp wird von Git verwaltet: {filename}")

        if any(filename.startswith(directory) for directory in PRIVATE_DIRS):
            if path.name != "README.md":
                errors.append(f"Datei in persönlichem Bereich wird von Git verwaltet: {filename}")

    return errors


def main() -> int:
    if not VAULT.is_dir():
        print(f"FEHLER: Vault nicht gefunden: {VAULT}", file=sys.stderr)
        return 2

    files = markdown_files()
    checks = [
        ("Interne Links", check_links(files)),
        ("Frontmatter", check_frontmatter(files)),
        ("Vorlagen", check_templates()),
        ("Git-Datenschutz", check_tracked_private_files()),
    ]

    total_errors = 0
    for name, errors in checks:
        print(f"\n=== {name} ===")
        if errors:
            for error in errors:
                print(f"FEHLER: {error}")
            total_errors += len(errors)
        else:
            print("OK")

    print(f"\nGeprüfte Markdown-Dateien: {len(files)}")
    print(f"Gefundene Probleme: {total_errors}")
    return 1 if total_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
