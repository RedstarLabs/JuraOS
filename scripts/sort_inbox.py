#!/usr/bin/env python3
"""Analysiert JuraOS-Inbox-Dateien und bietet sichere Ablagevorschläge an.

Die Analyse verändert keine Dateien. Dateiübernahmen erfolgen ausschließlich
über apply_proposal() nach expliziter Freigabe in der GUI.
"""
from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from pypdf import PdfReader
except ImportError:  # Verständliche Meldung, wenn Abhängigkeiten fehlen
    PdfReader = None  # type: ignore[assignment,misc]

ROOT = Path(__file__).resolve().parent.parent
VAULT = ROOT / "vault"
INBOX = VAULT / "01 Inbox"
COURSE_DIR = VAULT / "02 Studium" / "Lehrveranstaltungen"
AREA_DIR = VAULT / "03 Rechtsgebiete"
SOURCE_DIR = VAULT / "08 Quellen"
ALLOWED_SOURCE_FOLDERS = {"Urteile", "Aufsätze", "Skripte", "Vorlesungsunterlagen", "Literatur"}

FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
KNOWLEDGE_TYPES = {"definition", "fall", "karteikarte", "pruefungsschema", "prüfungsschema"}
SOURCE_ALIASES = {
    "urteil": "Urteile", "urteile": "Urteile", "beschluss": "Urteile",
    "beschluesse": "Urteile", "beschlüsse": "Urteile",
    "aufsatz": "Aufsätze", "aufsätze": "Aufsätze", "aufsatze": "Aufsätze",
    "skript": "Skripte", "skripte": "Skripte",
    "vorlesung": "Vorlesungsunterlagen", "vorlesungsunterlage": "Vorlesungsunterlagen",
    "vorlesungsunterlagen": "Vorlesungsunterlagen", "literatur": "Literatur",
}
COURSE_RULES = {
    "Staatsrecht I": ["staatsrecht", "grundrecht", "staatsorganisationsrecht", "bundestag", "bundesrat", "verfassungsrecht", "gesetzgebung", "verhältnismäßigkeit"],
    "Strafrecht I": ["strafrecht", "stgb", "tatbestand", "rechtswidrigkeit", "schuld", "vorsatz", "fahrlässigkeit"],
    "Zivilrecht I": ["zivilrecht", "bgb", "willenserklärung", "anspruch", "vertrag", "schuldrecht", "sachenrecht"],
    "Deutsche Rechtsgeschichte": ["rechtsgeschichte", "historische rechtsschule", "rezeption des römischen rechts"],
    "Einführung in die deutsche Rechtssprache": ["rechtssprache", "juristische fachsprach"],
    "Einführung in die Rechtswissenschaft": ["rechtswissenschaft", "rechtsquellen", "rechtsnorm", "juristische methodik"],
    "Römisches Recht": ["römisches recht", "roemisches recht", "digesten", "justinian", "corpus iuris civilis"],
    "Latein für Juristen I": ["latein für juristen", "lateinische rechtsbegriffe"],
}
AREA_RULES = {
    "Öffentliches Recht": ["öffentliches recht", "oeffentliches recht", "verfassungsrecht", "verfassungsrechts", "verwaltungsrecht", "grundrecht", "staatsorganisationsrecht"],
    "Strafrecht": ["strafrecht", "stgb", "tatbestand", "rechtswidrigkeit", "vorsatz", "fahrlässigkeit"],
    "Zivilrecht": ["zivilrecht", "bgb", "willenserklärung", "schuldrecht", "sachenrecht", "vertrag"],
    "Völkerrecht": ["völkerrecht", "voelkerrecht", "menschenrecht", "vereinte nationen", "humanitäres völkerrecht", "humanitaeres voelkerrecht", "asylrecht", "internationales recht"],
    "Rechtsphilosophie": ["rechtsphilosophie", "naturrecht", "rechtspositivismus", "gerechtigkeit", "rechtsphilosoph", "rechtsstaatlichkeit"],
}
SOURCE_RULES = {
    "Urteile": ["urteil", "beschluss", "entscheidungsgründe", "entscheidungsgruende", "bundesverfassungsgericht", "bundesgerichtshof", "aktenzeichen"],
    "Aufsätze": ["aufsatz", "journal", "zeitschrift", "abstract", "doi:"],
    "Skripte": ["skript", "script", "zusammenfassung", "lernunterlage"],
    "Vorlesungsunterlagen": ["vorlesung", "vorlesungsunterlage", "folien", "veranstaltung", "erstsemester"],
    "Literatur": ["lehrbuch", "kommentar", "isbn", "verlag", "auflage"],
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def normalize_source_type(value: str) -> str | None:
    key = normalize(value).replace("_", " ").replace("-", " ")
    key = re.sub(r"\s+", " ", key).strip()
    return SOURCE_ALIASES.get(key)


def read_frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER.match(text)
    if not match:
        return {}
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split(":", 1)
        metadata[key.strip().casefold()] = value.strip().strip("\"'")
    return metadata


def score_rules(text: str, rules: dict[str, list[str]]) -> list[tuple[str, int, list[str]]]:
    """Zählt Treffer als ganze Begriffe/Phrasen, nicht als beliebige Teilstrings."""
    normalized = normalize(text)
    matches: list[tuple[str, int, list[str]]] = []
    for name, keywords in rules.items():
        hits: list[str] = []
        for keyword in keywords:
            needle = normalize(keyword)
            pattern = r"(?<!\w)" + re.escape(needle) + r"(?!\w)"
            if re.search(pattern, normalized):
                hits.append(keyword)
        if hits:
            matches.append((name, len(hits), hits))
    return sorted(matches, key=lambda item: (-item[1], item[0].casefold()))


def existing_note(directory: Path, name: str) -> bool:
    return (directory / f"{name}.md").is_file()


def read_pdf_text(path: Path) -> tuple[str, str | None]:
    """Liest PDF-Text plattformübergreifend mit pypdf."""
    if PdfReader is None:
        return "", "Die PDF-Bibliothek pypdf fehlt. Bitte JuraOS-Abhängigkeiten installieren."
    try:
        reader = PdfReader(str(path))
        parts: list[str] = []
        for page in reader.pages[:80]:
            parts.append(page.extract_text() or "")
        text = "\n".join(parts)
        if not text.strip():
            return "", "Kein auslesbarer Text gefunden (möglicherweise ein Scan)."
        return text, None
    except Exception as exc:
        return "", f"PDF konnte nicht gelesen werden: {type(exc).__name__}: {exc}"


def analyze_file(path: Path) -> dict[str, Any]:
    path = Path(path)
    suffix = path.suffix.casefold()
    result: dict[str, Any] = {
        "file": str(path.relative_to(VAULT)) if path.is_relative_to(VAULT) else path.name,
        "kind": "PDF" if suffix == ".pdf" else "Markdown-Quelle" if suffix == ".md" else "Unbekannter Dateityp",
        "destination": None, "courses": [], "areas": [], "source_type": None,
        "confidence": "niedrig", "reason": [], "warnings": [], "action": "Manuelle Prüfung erforderlich.",
    }
    if suffix not in {".pdf", ".md"}:
        result["warnings"].append("Nur PDF- und Markdown-Dateien werden unterstützt.")
        return result

    if suffix == ".md":
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            result["warnings"].append(f"Markdown-Datei konnte nicht gelesen werden: {exc}")
            return result
        metadata = read_frontmatter(text)
    else:
        text, error = read_pdf_text(path)
        metadata = {}
        if error:
            result["warnings"].append(error)

    course_matches = score_rules(text, COURSE_RULES)
    area_matches = score_rules(text, AREA_RULES)
    source_matches = score_rules(text, SOURCE_RULES)
    courses = [name for name, score, _ in course_matches if score >= 1 and existing_note(COURSE_DIR, name)]
    areas = [name for name, score, _ in area_matches if score >= 1 and existing_note(AREA_DIR, name)]
    result["courses"] = courses
    result["areas"] = areas
    if course_matches:
        name, _, hits = course_matches[0]
        result["reason"].append(f"Lehrveranstaltungshinweise für {name}: {', '.join(hits[:4])}")
    if area_matches:
        name, _, hits = area_matches[0]
        result["reason"].append(f"Rechtsgebietshinweise für {name}: {', '.join(hits[:4])}")

    note_type = metadata.get("type", "").casefold()
    if suffix == ".md" and note_type in KNOWLEDGE_TYPES:
        result["kind"] = "Wissensnotiz"
        result["action"] = "Wissensnotiz erkannt; sie wird nicht in Quellen verschoben."
        if not courses and not areas:
            result["warnings"].append("Keine passende Lehrveranstaltung oder kein Rechtsgebiet erkannt.")
        return result

    if suffix == ".md":
        declared_type = metadata.get("source_type", "").strip()
        source_type = normalize_source_type(declared_type) if declared_type else None
        if declared_type and source_type is None:
            result["warnings"].append(f"Unbekannte Quellenart in source_type: {declared_type!r}.")
        elif source_type:
            result["source_type"] = source_type
            result["destination"] = f"vault/08 Quellen/{source_type}/"
            result["confidence"] = "mittel"
            result["reason"].append(f"Quellenart aus Frontmatter übernommen: {source_type}")
            result["action"] = "Explizite Quellenmetadaten erkannt; Ziel vor Übernahme prüfen."
        else:
            result["warnings"].append("Keine explizite Quellenart in source_type angegeben.")
            if len(source_matches) > 1:
                result["warnings"].append("Mehrere Quellenarten passen zum Text; source_type im Frontmatter ergänzen.")
            result["action"] = "Quellenart nicht ausreichend belegt; manuelle Prüfung erforderlich."
    else:
        if error:
            result["action"] = "PDF-Text konnte nicht vollständig ausgewertet werden; manuelle Prüfung erforderlich."
        elif not source_matches:
            result["warnings"].append("Keine eindeutige Quellenart erkannt.")
            result["action"] = "Quellenart unklar; manuelle Prüfung erforderlich."
        else:
            source_type, score, hits = source_matches[0]
            tied = len(source_matches) > 1 and source_matches[1][1] == score
            if tied:
                result["warnings"].append("Mehrere Quellenarten haben gleich viele Treffer; kein Ziel vorgeschlagen.")
                result["action"] = "Quellenart mehrdeutig; manuelle Prüfung erforderlich."
            elif score < 2:
                result["warnings"].append("Zu wenige Hinweise für eine belastbare Quellenart.")
                result["action"] = "Quellenart unklar; manuelle Prüfung erforderlich."
            else:
                result["source_type"] = source_type
                result["destination"] = f"vault/08 Quellen/{source_type}/"
                result["confidence"] = "mittel"
                result["reason"].append(f"Quellenart-Hinweise für {source_type}: {', '.join(hits[:4])}")
                result["action"] = "Quellenablage vorgeschlagen; Ziel und Hinweise prüfen."
                if not courses and not areas:
                    result["confidence"] = "niedrig"
                    result["warnings"].append("Keine thematische Zuordnung erkannt.")
    if not courses and not areas and not any("Keine passende Lehrveranstaltung" in w for w in result["warnings"]):
        result["warnings"].append("Keine passende Lehrveranstaltung oder kein Rechtsgebiet erkannt.")
    return result


def _safe_source(path: Path) -> Path:
    inbox_root = INBOX.resolve(strict=True)
    if path.is_symlink():
        raise ValueError("Symbolische Links dürfen nicht verschoben werden.")
    source = path.resolve(strict=True)
    source.relative_to(inbox_root)
    if not source.is_file() or source.suffix.casefold() not in {".pdf", ".md"}:
        raise ValueError("Quelle muss eine reguläre PDF- oder Markdown-Datei in der Inbox sein.")
    if source.name == "README.md":
        raise ValueError("Die Inbox-README darf nicht verschoben werden.")
    if source != path.absolute() and path.is_symlink():
        raise ValueError("Symbolische Links sind nicht zulässig.")
    return source


def apply_proposal(source_path: Path, result: dict[str, Any], destination_override: str | None = None) -> Path:
    """Verschiebt nach expliziter Freigabe, ohne existierende Dateien zu überschreiben."""
    source = _safe_source(Path(source_path))
    if result.get("kind") == "Wissensnotiz" or result.get("kind") not in {"PDF", "Markdown-Quelle"}:
        raise ValueError("Dieser Dateityp darf nicht über die Quellenablage verschoben werden.")
    relative_destination = destination_override or result.get("destination")
    if not isinstance(relative_destination, str) or not relative_destination:
        raise ValueError("Es liegt kein gültiges Ablageziel vor.")
    relative = Path(relative_destination)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Das Ablageziel ist ungültig.")
    expected_prefix = Path("vault") / "08 Quellen"
    if relative.parts[:2] != expected_prefix.parts or len(relative.parts) != 3:
        raise ValueError("Zulässig sind ausschließlich die vorgesehenen JuraOS-Quellenordner.")
    folder_name = relative.parts[2].rstrip("/")
    if folder_name not in ALLOWED_SOURCE_FOLDERS:
        raise ValueError("Dieser Quellenordner ist nicht freigegeben.")
    vault_root = VAULT.resolve(strict=True)
    target_candidate = ROOT / relative
    if target_candidate.is_symlink():
        raise ValueError("Symbolische Links als Zielordner sind nicht zulässig.")
    target_dir = target_candidate.resolve(strict=True)
    target_dir.relative_to(vault_root)
    if not target_dir.is_dir():
        raise ValueError("Der Zielordner existiert nicht oder ist nicht sicher.")
    if source == target_dir or target_dir in source.parents:
        raise ValueError("Quelle und Ziel sind nicht zulässig.")
    target = target_dir / source.name
    if target.exists():
        raise FileExistsError(f"Im Zielordner existiert bereits eine Datei namens {target.name!r}; nichts wurde verändert.")

    # Hardlink ist ein exklusiver, kollisionssicherer Eintrag. Falls nicht möglich,
    # wird mit exklusiver Dateierstellung kopiert und erst danach die Quelle entfernt.
    try:
        os.link(source, target)
    except FileExistsError:
        raise FileExistsError(f"Im Zielordner existiert bereits eine Datei namens {target.name!r}; nichts wurde verändert.")
    except OSError:
        created = False
        try:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IMODE(source.stat().st_mode))
            created = True
            with os.fdopen(fd, "wb") as output, source.open("rb") as input_file:
                shutil.copyfileobj(input_file, output)
                output.flush()
                os.fsync(output.fileno())
            shutil.copystat(source, target)
        except Exception:
            if created:
                try:
                    target.unlink()
                except OSError:
                    pass
            raise
    try:
        source.unlink()
    except Exception:
        try:
            target.unlink()
        except OSError:
            pass
        raise
    return target


def main() -> int:
    if not INBOX.is_dir():
        print(f"FEHLER: Inbox nicht gefunden: {INBOX}", file=sys.stderr)
        return 2
    files = sorted(path for path in INBOX.rglob("*") if path.is_file() and path.name != "README.md" and not path.is_symlink())
    print("JuraOS – Inbox-Sortierer")
    print("Modus: VORSCHLÄGE; Dateien bleiben unverändert, bis du sie ausdrücklich übernimmst.")
    print(f"Untersuchte Dateien: {len(files)}")
    for path in files:
        result = analyze_file(path)
        print(f"\n{'=' * 64}\nDatei: {result['file']}\nTyp: {result['kind']}\nAktion: {result['action']}\nKonfidenz: {result['confidence']}")
        if result["destination"]:
            print(f"Vorgeschlagener Zielordner: {result['destination']}")
        for field, label in (("courses", "Lehrveranstaltungen"), ("areas", "Rechtsgebiete")):
            if result[field]:
                print(f"{label}: " + ", ".join(f"[[{item}]]" for item in result[field]))
        if result["source_type"]:
            print(f"Quellenart: {result['source_type']}")
        for reason in result["reason"]:
            print(f"Begründung: {reason}")
        for warning in result["warnings"]:
            print(f"HINWEIS: {warning}")
    print("\nAnalyse abgeschlossen. Es wurden keine Dateien verändert.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
