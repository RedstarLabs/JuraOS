#!/usr/bin/env python3
"""Grafische Oberfläche für den sicheren JuraOS-Dokumentensortierer."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QHeaderView, QHBoxLayout,
    QInputDialog, QLabel, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from sort_inbox import ALLOWED_SOURCE_FOLDERS, INBOX, ROOT, VAULT, analyze_file, apply_proposal


class JuraOSSorterWindow(QMainWindow):
    COLUMNS = ["Datei", "Typ", "Quellenart", "Zielordner", "Konfidenz", "Status"]
    FILTERS = ["Alle Dateien", "Vorschlag vorhanden", "Manuelle Prüfung", "Noch nicht analysiert", "Wissensnotiz"]

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("JuraOS – Dokumentensortierer")
        self.resize(1350, 820)
        self.setMinimumSize(900, 600)
        self.file_paths: list[Path] = []
        self.results: dict[str, dict] = {}
        self.rejected: set[str] = set()

        heading = QLabel("JuraOS – Dokumentensortierer")
        heading.setStyleSheet("font-size: 22px; font-weight: bold;")
        subtitle = QLabel("Dokumente analysieren, Ablagevorschläge prüfen und freigegebene Dateien sicher verschieben.")
        subtitle.setWordWrap(True)
        self.workspace_label = QLabel(f"Vault: {VAULT}\nInbox: {INBOX}")
        self.workspace_label.setWordWrap(True)
        self.workspace_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.safety_label = QLabel("SICHERHEIT: Dateien werden erst nach deiner Bestätigung verschoben. Bestehende Dateien werden niemals überschrieben.")
        self.safety_label.setWordWrap(True)
        self.safety_label.setStyleSheet("font-weight: bold;")

        self.refresh_button = QPushButton("Inbox aktualisieren")
        self.refresh_button.clicked.connect(self.refresh_files)
        self.analyze_selected_button = QPushButton("Ausgewählte Datei analysieren")
        self.analyze_selected_button.clicked.connect(self.analyze_selected)
        self.analyze_all_button = QPushButton("Alle Dateien analysieren")
        self.analyze_all_button.clicked.connect(self.analyze_all)
        self.accept_button = QPushButton("Vorschlag akzeptieren…")
        self.accept_button.clicked.connect(self.accept_proposal)
        self.manual_button = QPushButton("Ziel manuell wählen…")
        self.manual_button.clicked.connect(self.choose_destination)
        self.reject_button = QPushButton("Vorschlag ablehnen")
        self.reject_button.clicked.connect(self.reject_proposal)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(self.FILTERS)
        self.filter_combo.currentTextChanged.connect(self.populate_table)

        toolbar = QHBoxLayout()
        for button in (self.refresh_button, self.analyze_selected_button, self.analyze_all_button):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        toolbar.addWidget(QLabel("Filter:"))
        toolbar.addWidget(self.filter_combo)
        actions = QHBoxLayout()
        for button in (self.accept_button, self.manual_button, self.reject_button):
            actions.addWidget(button)
        actions.addStretch(1)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.cellDoubleClicked.connect(self.analyze_row)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Wähle eine Datei aus, um Analyse und Begründung zu sehen.")
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        table_panel = QWidget()
        table_layout = QVBoxLayout(table_panel)
        table_layout.addWidget(QLabel("Inbox-Dateien"))
        table_layout.addWidget(self.table, 1)
        detail_panel = QWidget()
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.addWidget(QLabel("Details und Begründung"))
        detail_layout.addWidget(self.details, 1)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(table_panel)
        splitter.addWidget(detail_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        central = QWidget()
        layout = QVBoxLayout(central)
        for widget in (heading, subtitle, self.workspace_label, self.safety_label):
            layout.addWidget(widget)
        layout.addLayout(toolbar)
        layout.addLayout(actions)
        layout.addWidget(splitter, 1)
        layout.addWidget(self.status_label)
        self.setCentralWidget(central)
        self.refresh_files()

    def inbox_files(self) -> list[Path]:
        root = INBOX.resolve()
        files: list[Path] = []
        if not root.is_dir():
            return files
        for candidate in root.rglob("*"):
            if candidate.name == "README.md" or candidate.is_symlink():
                continue
            try:
                resolved = candidate.resolve(strict=True)
                resolved.relative_to(root)
            except (OSError, ValueError):
                continue
            if resolved.is_file():
                files.append(resolved)
        return sorted(set(files), key=lambda p: str(p).casefold())

    def refresh_files(self) -> None:
        self.file_paths = self.inbox_files()
        current = {str(path) for path in self.file_paths}
        self.results = {key: value for key, value in self.results.items() if key in current}
        self.rejected.intersection_update(current)
        self.populate_table()
        self.status_label.setText(f"{len(self.file_paths)} Datei(en) in der Inbox. Dateien werden nur nach Bestätigung verschoben.")
        if not self.file_paths:
            self.details.setPlainText("Die Inbox ist leer.")

    def result_status(self, result: dict | None, key: str | None = None) -> str:
        if key and key in self.rejected:
            return "Abgelehnt (Sitzung)"
        if result is None:
            return "Noch nicht analysiert"
        if result.get("kind") == "Wissensnotiz":
            return "Wissensnotiz"
        if result.get("destination") and result.get("source_type"):
            return "Vorschlag vorhanden"
        return "Manuelle Prüfung"

    def populate_table(self) -> None:
        selected = self.selected_path()
        filter_value = self.filter_combo.currentText()
        self.table.setRowCount(0)
        for path in self.file_paths:
            key = str(path)
            result = self.results.get(key)
            status = self.result_status(result, key)
            if filter_value == "Vorschlag vorhanden" and status != filter_value:
                continue
            if filter_value == "Manuelle Prüfung" and status != filter_value:
                continue
            if filter_value == "Noch nicht analysiert" and result is not None:
                continue
            if filter_value == "Wissensnotiz" and status != filter_value:
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            try:
                name = str(path.relative_to(INBOX.resolve()))
            except ValueError:
                name = path.name
            values = [name, str(result.get("kind", "—")) if result else "—",
                      str(result.get("source_type") or "—") if result else "—",
                      str(result.get("destination") or "—") if result else "—",
                      str(result.get("confidence", "—")) if result else "—", status]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, key)
                item.setToolTip(value)
                self.table.setItem(row, column, item)
        if selected:
            self.select_path(selected)
        self.update_action_buttons()

    def selected_path(self) -> Path | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        key = item.data(Qt.ItemDataRole.UserRole) if item else None
        return Path(key) if key else None

    def select_path(self, path: Path) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == str(path):
                self.table.selectRow(row)
                return

    def update_action_buttons(self) -> None:
        path = self.selected_path()
        result = self.results.get(str(path)) if path else None
        eligible = bool(result and result.get("destination") and result.get("source_type") and result.get("kind") in {"PDF", "Markdown-Quelle"})
        self.accept_button.setEnabled(eligible and str(path) not in self.rejected if path else False)
        self.manual_button.setEnabled(bool(path and path.suffix.casefold() in {".pdf", ".md"} and (not result or result.get("kind") != "Wissensnotiz")))
        self.reject_button.setEnabled(bool(eligible and path and str(path) not in self.rejected))

    def on_selection_changed(self) -> None:
        path = self.selected_path()
        if not path:
            self.update_action_buttons()
            return
        result = self.results.get(str(path))
        if result is None:
            self.details.setPlainText(f"Datei: {path.name}\n\nNoch nicht analysiert. Doppelklick oder Analyse-Button startet die Analyse.")
        else:
            self.details.setPlainText(self.format_result(path, result))
        self.update_action_buttons()

    def format_result(self, path: Path, result: dict) -> str:
        lines = [f"Datei: {result.get('file', path.name)}", f"Typ: {result.get('kind', 'unbekannt')}",
                 f"Status: {self.result_status(result, str(path))}", f"Aktion: {result.get('action', 'Manuell prüfen')}",
                 f"Konfidenz: {result.get('confidence', 'niedrig')}", ""]
        if result.get("destination"):
            lines += ["Vorgeschlagener Zielordner:", str(result["destination"]), ""]
        for field, label in (("courses", "Lehrveranstaltungen"), ("areas", "Rechtsgebiete")):
            if result.get(field):
                lines += [label + ":", *[f"  - [[{name}]]" for name in result[field]], ""]
        if result.get("source_type"):
            lines += ["Quellenart:", str(result["source_type"]), ""]
        if result.get("reason"):
            lines += ["Begründung:", *[f"  - {item}" for item in result["reason"]], ""]
        if result.get("warnings"):
            lines += ["Hinweise:", *[f"  - {item}" for item in result["warnings"]], ""]
        lines += ["Sicherheit:", "Es wurde bisher nichts verändert. Die Datei wird erst nach Bestätigung verschoben."]
        return "\n".join(lines)

    def analyze_path(self, path: Path) -> dict | None:
        try:
            root = INBOX.resolve(strict=True)
            if path.is_symlink():
                raise ValueError("Symbolische Links sind nicht zulässig.")
            resolved = path.resolve(strict=True)
            resolved.relative_to(root)
            if not resolved.is_file():
                raise ValueError("Keine reguläre Datei.")
            result = analyze_file(resolved)
        except Exception as exc:
            QMessageBox.warning(self, "Analyse fehlgeschlagen", f"Datei konnte nicht analysiert werden.\n\n{type(exc).__name__}: {exc}")
            return None
        self.results[str(resolved)] = result
        self.rejected.discard(str(resolved))
        return result

    def analyze_selected(self) -> None:
        path = self.selected_path()
        if path is None:
            QMessageBox.information(self, "Keine Auswahl", "Bitte wähle zuerst eine Datei aus.")
            return
        result = self.analyze_path(path)
        if result is not None:
            self.populate_table()
            self.select_path(path)
            self.details.setPlainText(self.format_result(path, result))

    def analyze_row(self, row: int, column: int) -> None:
        item = self.table.item(row, 0)
        if item is None:
            return
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        result = self.analyze_path(path)
        if result is not None:
            self.populate_table()
            self.select_path(path)
            self.details.setPlainText(self.format_result(path, result))

    def analyze_all(self) -> None:
        files = self.inbox_files()
        count = 0
        for path in files:
            if self.analyze_path(path) is not None:
                count += 1
        self.populate_table()
        self.status_label.setText(f"{count} von {len(files)} Datei(en) analysiert. Es wurde nichts verschoben.")

    def confirm_and_move(self, path: Path, result: dict, destination: str) -> None:
        folder = destination.rstrip("/").split("/")[-1]
        target = VAULT / "08 Quellen" / folder / path.name
        warnings = result.get("warnings", [])
        warning_text = "\n\nHinweise:\n- " + "\n- ".join(warnings) if warnings else ""
        answer = QMessageBox.question(
            self, "Datei wirklich verschieben?",
            f"Quelle:\n{path}\n\nZiel:\n{target}\n{warning_text}\n\nDie Datei wird verschoben, nicht kopiert. Bestehende Dateien werden nicht überschrieben. Fortfahren?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            moved_to = apply_proposal(path, result, destination_override=destination)
        except Exception as exc:
            QMessageBox.critical(self, "Verschieben fehlgeschlagen", f"Die Datei wurde nicht erfolgreich übernommen.\n\n{type(exc).__name__}: {exc}")
            return
        self.results.pop(str(path), None)
        self.rejected.discard(str(path))
        self.refresh_files()
        QMessageBox.information(self, "Datei verschoben", f"Die Datei wurde verschoben nach:\n{moved_to}")
        self.status_label.setText(f"Verschoben: {moved_to.name}")

    def accept_proposal(self) -> None:
        path = self.selected_path()
        result = self.results.get(str(path)) if path else None
        if not path or not result or not result.get("destination") or not result.get("source_type"):
            QMessageBox.information(self, "Kein eindeutiger Vorschlag", "Analysiere die Datei zuerst. Bei unklaren Fällen wähle ein Ziel manuell.")
            return
        self.confirm_and_move(path, result, result["destination"])

    def choose_destination(self) -> None:
        path = self.selected_path()
        if path is None:
            return
        result = self.results.get(str(path))
        if result is None:
            result = self.analyze_path(path)
            if result is None:
                return
        if result.get("kind") == "Wissensnotiz":
            QMessageBox.information(self, "Wissensnotiz", "Wissensnotizen werden nicht in die Quellenordner verschoben.")
            return
        current = result.get("source_type") or ""
        options = sorted(ALLOWED_SOURCE_FOLDERS)
        default = current if current in options else options[0]
        selected, ok = QInputDialog.getItem(self, "Ablageziel wählen", "Quellenordner:", options, options.index(default), False)
        if not ok or not selected:
            return
        destination = f"vault/08 Quellen/{selected}/"
        self.confirm_and_move(path, result, destination)

    def reject_proposal(self) -> None:
        path = self.selected_path()
        if path is None:
            return
        answer = QMessageBox.question(self, "Vorschlag ablehnen", f"Den Vorschlag für {path.name} in dieser Sitzung ausblenden? Die Datei bleibt unverändert.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.rejected.add(str(path))
            self.populate_table()
            self.details.setPlainText(f"Vorschlag für {path.name} in dieser Sitzung abgelehnt. Die Datei wurde nicht verändert.")


def main() -> int:
    if not VAULT.is_dir() or not INBOX.is_dir():
        print("FEHLER: JuraOS-Vault oder Inbox wurde nicht gefunden.", file=sys.stderr)
        return 2
    app = QApplication(sys.argv)
    app.setApplicationName("JuraOS Dokumentensortierer")
    window = JuraOSSorterWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
