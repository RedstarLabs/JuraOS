
# JuraOS – Dokumentensortierer starten

JuraOS ist eine lokale Erweiterung für den Obsidian-Vault. Der
Dokumentensortierer analysiert Dateien aus dem Inbox-Ordner,
erstellt Sortiervorschläge und ermöglicht die kontrollierte
Übernahme in die vorgesehenen Quellenordner.

Die Anwendung ist für Fedora KDE und Windows vorbereitet.
Die Windows-Ausführung wurde bislang nicht auf einem echten
Windows-System getestet.

## 1. Voraussetzungen

### Fedora KDE

- Python 3.10 oder neuer
- Eine funktionsfähige Python-Installation mit Unterstützung
  für virtuelle Umgebungen
- Internetverbindung für die erstmalige Installation der
  Python-Abhängigkeiten

Unter Fedora können die benötigten Pakete beispielsweise so
installiert werden:

```bash
sudo dnf install python3 python3-pip
```

Falls die Erstellung einer virtuellen Umgebung fehlschlägt,
prüfe die Fedora-Paketquellen und installiere das passende
Paket für virtuelle Python-Umgebungen.

### Windows

- Windows 10 oder neuer
- Python 3.10 oder neuer
- Internetverbindung für die erstmalige Installation
- Ausreichend Speicherplatz für die virtuelle Umgebung und
  die Python-Abhängigkeiten

Installiere Python über eine vertrauenswürdige Quelle.
Aktiviere beim Installer nach Möglichkeit die Option
„Add Python to PATH“.

## 2. Installation und Start unter Fedora KDE

Wechsle im Terminal in den JuraOS-Projektordner:

```bash
cd /data/Projekte/JuraOS
```

Mache die Startskripte ausführbar und installiere den
KDE-Menüeintrag:

```bash
chmod +x start-juraos.sh scripts/install_desktop_entry.sh
./scripts/install_desktop_entry.sh
```

Danach findest du die Anwendung im KDE-Anwendungsmenü unter:

**JuraOS Dokumentensortierer**

Alternativ kannst du die Anwendung direkt starten:

```bash
./start-juraos.sh
```

Beim ersten Start erstellt das Startskript eine lokale
virtuelle Python-Umgebung unter `.venv`, sofern diese noch
nicht vorhanden ist.

Anschließend werden die benötigten Abhängigkeiten aus
`requirements.txt` installiert. Dafür ist beim ersten Start
eine Internetverbindung erforderlich.

Bei weiteren Starts werden die installierten Abhängigkeiten
wiederverwendet.

## 3. Installation und Start unter Windows

Kopiere den vollständigen JuraOS-Projektordner auf den
Windows-Rechner. Du kannst dafür beispielsweise ein
geeignetes lokales Laufwerk oder einen privaten
Synchronisationsordner verwenden.

Achte darauf, dass die benötigten Programmdateien und
Ordner erhalten bleiben, insbesondere:

- `start-juraos.bat`
- `requirements.txt`
- `scripts/`
- `vault/`

Starte anschließend `start-juraos.bat` per Doppelklick.

Das Skript versucht, eine lokale virtuelle Python-Umgebung
unter `.venv` anzulegen und die erforderlichen Abhängigkeiten
zu installieren. Danach startet es die grafische Oberfläche.

Für die erstmalige Installation wird eine Internetverbindung
benötigt.

**Hinweis:** Die Windows-Startdatei ist vorbereitet, aber
noch nicht auf einem echten Windows-System getestet.
Eine erfolgreiche Ausführung unter Windows kann deshalb
noch nicht garantiert werden.

## 4. Arbeitsablauf

1. Lege eine zu sortierende Datei im Ordner `vault/01 Inbox/` ab.
2. Starte den JuraOS-Dokumentensortierer.
3. Lass die Datei analysieren und prüfe den vorgeschlagenen
   Dokumenttyp sowie den Zielordner.
4. Kontrolliere den Vorschlag, bevor du ihn übernimmst.
5. Bestätige die Übernahme ausdrücklich.
6. Kontrolliere anschließend die Datei im Zielordner und
   verknüpfe sie bei Bedarf mit der passenden Lehrveranstaltung
   oder Wissensnotiz.

Nicht eindeutig zuordenbare Dateien sollten manuell geprüft
werden, statt einen unsicheren Sortiervorschlag zu übernehmen.

## 5. Sicherheitsverhalten

Der Sortierer ist darauf ausgelegt, die Kontrolle über den
Vault beim Nutzer zu belassen.

- Die Analyse allein verschiebt keine Dateien.
- Die Übernahme eines Vorschlags erfordert eine Bestätigung.
- Eine manuelle Zielauswahl ist auf die vorgesehenen
  Quellenordner beschränkt.
- Bereits vorhandene Zieldateien werden nicht überschrieben.
- Wissensnotizen werden nicht als externe Quellen verschoben.
- Unsichere oder unzulässige Pfade werden abgelehnt.
- Lehrveranstaltungs- und Rechtsgebietszuordnungen werden
  angezeigt, aber nicht automatisch in Markdown-Dateien
  geschrieben.

Prüfe nach einer Übernahme, ob die Datei am erwarteten Ort
liegt und der Inhalt erhalten geblieben ist.

## 6. Datenschutz und Git

Der JuraOS-Vault kann persönliche Studiennotizen,
Vorlesungsunterlagen und urheberrechtlich geschützte
Dokumente enthalten.

Beachte daher folgende Regeln:

- Private PDFs und persönliche Quellennotizen bleiben lokal,
  sofern ihre Veröffentlichung nicht ausdrücklich gewollt
  und rechtlich zulässig ist.
- Die allgemeine Vorlage und Dokumentation dürfen Teil des
  öffentlichen Repositories sein.
- Verlasse dich nicht ausschließlich auf `.gitignore`:
  Bereits versionierte Dateien werden dadurch nicht
  automatisch aus Git entfernt.
- Prüfe vor jedem Commit den Git-Status und die Änderungen.
- Kontrolliere insbesondere neue Dateien unter `vault/`.
- Lade keine privaten Dokumente versehentlich in ein
  öffentliches Repository hoch.

Für eine gezielte Datenschutzprüfung kannst du beispielsweise
folgende Befehle verwenden:

```bash
git status --short
git diff --stat
git check-ignore -v "PFAD/ZUR/PRIVATEN_DATEI.pdf"
```

Ersetze den Beispielpfad durch den tatsächlichen Dateipfad.

## 7. Tests und Qualitätsprüfung

Führe die folgenden Befehle im Projektordner aus.

Automatisierte Tests:

```bash
python -m unittest discover -s tests -v
```

Vault-Prüfung:

```bash
python scripts/check_vault.py
```

Syntaxprüfung der Python-Dateien:

```bash
python -m py_compile \
  scripts/juraos_sorter_gui.py \
  scripts/sort_inbox.py \
  scripts/check_vault.py
```

Syntaxprüfung des Fedora-Startskripts:

```bash
bash -n start-juraos.sh
```

Die Prüfungen kontrollieren unterschiedliche Aspekte des
Projekts. Ein erfolgreicher Testlauf ersetzt weder eine
manuelle Funktionsprüfung noch einen tatsächlichen Test
unter Windows.

## 8. Fehlerbehebung

### Fedora: Die virtuelle Umgebung kann nicht erstellt werden

Prüfe, ob Python 3 installiert ist:

```bash
python3 --version
```

Prüfe außerdem, ob die Installation virtueller Umgebungen
auf deinem System funktioniert.

### Python-Abhängigkeiten können nicht installiert werden

- Prüfe die Internetverbindung.
- Prüfe, ob Python korrekt installiert ist.
- Kontrolliere die Fehlermeldung des Startskripts.
- Wiederhole die Installation nicht blind, wenn ein
  konkreter Paket- oder Berechtigungsfehler angezeigt wird.

### Die grafische Oberfläche startet nicht

Starte die Anwendung direkt im Terminal, damit Fehlermeldungen
sichtbar bleiben:

```bash
./start-juraos.sh
```

Kopiere die vollständige Fehlermeldung, bevor du Änderungen
an der virtuellen Umgebung oder den Projektdateien vornimmst.

### Windows: Die Anwendung startet nicht

Prüfe zuerst, ob Python installiert und über den Launcher
`py` oder den Befehl `python` erreichbar ist.

Öffne bei Bedarf eine Eingabeaufforderung im Projektordner
und starte:

```bat
start-juraos.bat
```

Notiere die vollständige Fehlermeldung. Die Windows-Version
muss auf einem echten Windows-System getestet werden, bevor
sie als zuverlässig unterstützt gelten kann.

## 9. Projektversion

Aktuelle Projektversion: **0.1.0**

Die Versionsnummer bezeichnet den Entwicklungsstand der
lokalen JuraOS-Werkzeuge. Vor einer Veröffentlichung sollten
die Tests, die Datenschutzregeln, die Dokumentation und
die Startabläufe geprüft werden.

Ein erfolgreicher lokaler Testlauf bedeutet nicht automatisch,
dass die Anwendung auf jedem Betriebssystem getestet wurde.
