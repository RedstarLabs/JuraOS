
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.sort_inbox import (
    analyze_file,
    apply_proposal,
    score_rules,
    SOURCE_RULES,
)


class InboxSorterTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.vault = self.root / "vault"
        self.inbox = self.vault / "01 Inbox"
        self.courses = self.vault / "02 Studium" / "Lehrveranstaltungen"
        self.areas = self.vault / "03 Rechtsgebiete"
        self.sources = self.vault / "08 Quellen"

        for directory in (
            self.inbox,
            self.courses,
            self.areas,
            self.sources,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        for folder in (
            "Urteile",
            "Aufsätze",
            "Skripte",
            "Vorlesungsunterlagen",
            "Literatur",
        ):
            (self.sources / folder).mkdir()

        (self.courses / "Staatsrecht I.md").write_text(
            "# Staatsrecht I\n", encoding="utf-8"
        )
        (self.areas / "Öffentliches Recht.md").write_text(
            "# Öffentliches Recht\n", encoding="utf-8"
        )

        self.patches = [
            patch("scripts.sort_inbox.ROOT", self.root),
            patch("scripts.sort_inbox.VAULT", self.vault),
            patch("scripts.sort_inbox.INBOX", self.inbox),
            patch("scripts.sort_inbox.COURSE_DIR", self.courses),
            patch("scripts.sort_inbox.AREA_DIR", self.areas),
            patch("scripts.sort_inbox.SOURCE_DIR", self.sources),
        ]
        for mocked in self.patches:
            mocked.start()
            self.addCleanup(mocked.stop)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_markdown(self, filename, content):
        path = self.inbox / filename
        path.write_text(content, encoding="utf-8")
        return path

    # Analysefälle
    def test_definition_is_not_moved_to_sources(self):
        note = self.write_markdown(
            "Test - Definition.md",
            "---\ntype: definition\nstatus: draft\n---\n# Test - Definition\n",
        )
        result = analyze_file(note)
        self.assertEqual(result["kind"], "Wissensnotiz")
        self.assertIsNone(result["destination"])
        self.assertIn("Wissensnotiz", result["action"])

    def test_pdf_with_clear_clues_gets_source_proposal(self):
        pdf = self.inbox / "Vorlesung Staatsrecht.pdf"
        pdf.write_bytes(b"Test-PDF")
        with patch(
            "scripts.sort_inbox.read_pdf_text",
            return_value=(
                "Vorlesung Folien Staatsrecht I Grundrechte Verfassungsrecht",
                None,
            ),
        ):
            result = analyze_file(pdf)
        self.assertEqual(
            result["destination"], "vault/08 Quellen/Vorlesungsunterlagen/"
        )
        self.assertIn("Staatsrecht I", result["courses"])
        self.assertIn("Öffentliches Recht", result["areas"])

    def test_unknown_pdf_has_no_guessed_destination(self):
        pdf = self.inbox / "Unbekannt.pdf"
        pdf.write_bytes(b"Test-PDF")
        with patch(
            "scripts.sort_inbox.read_pdf_text",
            return_value=("Inhalt ohne erkennbare Fachbegriffe", None),
        ):
            result = analyze_file(pdf)
        self.assertIsNone(result["destination"])
        self.assertEqual(result["confidence"], "niedrig")
        self.assertTrue(result["warnings"])

    def test_missing_course_note_is_not_linked(self):
        note = self.write_markdown(
            "Staatsrecht.md", "# Staatsrecht I\nGrundrechte und Verfassungsrecht\n"
        )
        (self.courses / "Staatsrecht I.md").unlink()
        result = analyze_file(note)
        self.assertNotIn("Staatsrecht I", result["courses"])

    def test_explicit_source_type_aufsatz_is_recognized(self):
        note = self.write_markdown(
            "TEST_Aufsatz.md",
            "---\ntype: source\nsource_type: Aufsatz\nstatus: unread\n---\n"
            "# Testaufsatz zum Völkerrecht\n"
            "Dieser Text behandelt Völkerrecht und Menschenrechte.\n",
        )
        result = analyze_file(note)
        self.assertEqual(result["source_type"], "Aufsätze")
        self.assertEqual(result["destination"], "vault/08 Quellen/Aufsätze/")

    def test_explicit_source_type_urteil_is_recognized(self):
        note = self.write_markdown(
            "TEST_Urteil.md",
            "---\ntype: source\nsource_type: Urteil\nstatus: unread\n---\n"
            "# Testentscheidung des Bundesverfassungsgerichts\n"
            "Fiktiver Testtext zu Grundrechten.\n",
        )
        result = analyze_file(note)
        self.assertEqual(result["source_type"], "Urteile")
        self.assertEqual(result["destination"], "vault/08 Quellen/Urteile/")

    def test_explicit_source_type_vorlesungsunterlage_is_recognized(self):
        note = self.write_markdown(
            "TEST_Vorlesung.md",
            "---\ntype: source\nsource_type: Vorlesungsunterlage\nstatus: unread\n---\n"
            "# Testunterlage\nGrundrechte und Verfassungsrecht.\n",
        )
        result = analyze_file(note)
        self.assertEqual(result["source_type"], "Vorlesungsunterlagen")
        self.assertEqual(
            result["destination"], "vault/08 Quellen/Vorlesungsunterlagen/"
        )

    def test_ambiguous_source_without_metadata_gets_no_destination(self):
        note = self.write_markdown(
            "TEST_Mehrdeutig.md",
            "---\ntype: source\nstatus: unread\n---\n"
            "# Mehrdeutiges Testdokument\n"
            "Dies bezeichnet sich als Vorlesung und Urteil. "
            "Es enthält auch Hinweise auf einen Aufsatz und eine Zeitschrift.\n",
        )
        result = analyze_file(note)
        self.assertIsNone(result["destination"])
        self.assertIsNone(result["source_type"])
        self.assertEqual(result["confidence"], "niedrig")
        self.assertTrue(result["warnings"])

    def test_unknown_source_metadata_alone_is_not_enough(self):
        note = self.write_markdown(
            "TEST_Unbekannt.md",
            "---\ntype: source\nstatus: unread\n---\n"
            "# Testdokument\nKünstlicher Platzhaltertext ohne fachliche Hinweise.\n",
        )
        result = analyze_file(note)
        self.assertIsNone(result["destination"])
        self.assertIsNone(result["source_type"])
        self.assertEqual(result["confidence"], "niedrig")

    def test_definition_can_link_to_existing_topics(self):
        note = self.write_markdown(
            "TEST_Grundrechte.md",
            "---\ntype: definition\nstatus: draft\n---\n"
            "# Grundrechte\nDie Verhältnismäßigkeit ist ein Maßstab des Verfassungsrechts.\n",
        )
        result = analyze_file(note)
        self.assertIsNone(result["destination"])
        self.assertIn("Staatsrecht I", result["courses"])
        self.assertIn("Öffentliches Recht", result["areas"])

    def test_source_type_metadata_does_not_override_knowledge_note(self):
        note = self.write_markdown(
            "TEST_Definition_Mit_Quelle.md",
            "---\ntype: definition\nsource_type: Aufsatz\nstatus: draft\n---\n"
            "# Definition\nEine kurze künstliche Wissensnotiz.\n",
        )
        result = analyze_file(note)
        self.assertIsNone(result["destination"])
        self.assertIn("Wissensnotiz", result["action"])

    def test_source_keywords_do_not_match_inside_unrelated_words(self):
        self.assertEqual(
            score_rules(
                "Ein künstlicher Platzhaltertext ohne fachliche Hinweise.",
                SOURCE_RULES,
            ),
            [],
        )

    def test_real_source_keywords_are_still_recognized(self):
        matches = score_rules(
            "Vorlesung und Folien zur Veranstaltung", SOURCE_RULES
        )
        self.assertTrue(matches)
        self.assertEqual(matches[0][0], "Vorlesungsunterlagen")

    # Sicherheitsfälle für die bestätigte Dateiübernahme
    def test_apply_proposal_moves_file(self):
        source = self.inbox / "Test.pdf"
        source.write_bytes(b"pdf test")
        result = {
            "kind": "PDF",
            "source_type": "Aufsätze",
            "destination": "vault/08 Quellen/Aufsätze/",
        }

        target = apply_proposal(source, result)

        self.assertFalse(source.exists())
        self.assertEqual(target.read_bytes(), b"pdf test")

    def test_existing_target_is_never_overwritten(self):
        source = self.inbox / "Collision.pdf"
        source.write_bytes(b"source")
        target = self.sources / "Urteile" / source.name
        target.write_bytes(b"existing")
        result = {
            "kind": "PDF",
            "source_type": "Urteile",
            "destination": "vault/08 Quellen/Urteile/",
        }

        with self.assertRaises(FileExistsError):
            apply_proposal(source, result)

        self.assertEqual(source.read_bytes(), b"source")
        self.assertEqual(target.read_bytes(), b"existing")

    def test_rejects_destination_outside_allowed_folders(self):
        source = self.inbox / "Unsafe.pdf"
        source.write_bytes(b"source")
        result = {
            "kind": "PDF",
            "source_type": "Urteile",
            "destination": "vault/02 Studium/",
        }

        with self.assertRaises(ValueError):
            apply_proposal(source, result)

        self.assertTrue(source.exists())
        self.assertEqual(source.read_bytes(), b"source")

    def test_rejects_file_outside_inbox(self):
        source = self.vault / "outside.pdf"
        source.write_bytes(b"source")
        result = {
            "kind": "PDF",
            "source_type": "Urteile",
            "destination": "vault/08 Quellen/Urteile/",
        }

        with self.assertRaises(ValueError):
            apply_proposal(source, result)

        self.assertTrue(source.exists())
        self.assertEqual(source.read_bytes(), b"source")

    def test_rejects_knowledge_note(self):
        source = self.write_markdown(
            "Definition.md", "---\ntype: definition\n---\n# Note\n"
        )
        result = {
            "kind": "Wissensnotiz",
            "destination": "vault/08 Quellen/Literatur/",
        }

        with self.assertRaises(ValueError):
            apply_proposal(source, result)

        self.assertTrue(source.exists())

    def test_rejects_path_traversal_destination(self):
        source = self.inbox / "Traversal.pdf"
        source.write_bytes(b"source")
        result = {
            "kind": "PDF",
            "source_type": "Literatur",
            "destination": "vault/08 Quellen/../../02 Studium/",
        }

        with self.assertRaises(ValueError):
            apply_proposal(source, result)

        self.assertTrue(source.exists())
        self.assertEqual(source.read_bytes(), b"source")

    def test_rejects_symlink_as_source(self):
        outside = self.vault / "outside.pdf"
        outside.write_bytes(b"private data")
        link = self.inbox / "linked.pdf"

        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Symlinks werden hier nicht unterstützt: {exc}")

        result = {
            "kind": "PDF",
            "source_type": "Urteile",
            "destination": "vault/08 Quellen/Urteile/",
        }

        with self.assertRaises(ValueError):
            apply_proposal(link, result)

        self.assertTrue(outside.exists())
        self.assertEqual(outside.read_bytes(), b"private data")
        self.assertTrue(link.is_symlink())

    def test_rejects_symlink_as_destination_directory(self):
        outside = self.root / "outside-destination"
        outside.mkdir()
        link = self.sources / "Literatur"
        link.rmdir()

        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Symlinks werden hier nicht unterstützt: {exc}")

        source = self.inbox / "TargetLink.pdf"
        source.write_bytes(b"source")
        result = {
            "kind": "PDF",
            "source_type": "Literatur",
            "destination": "vault/08 Quellen/Literatur/",
        }

        with self.assertRaises(ValueError):
            apply_proposal(source, result)

        self.assertTrue(source.exists())
        self.assertFalse((outside / source.name).exists())

    def test_missing_destination_does_not_remove_source(self):
        source = self.inbox / "MissingDestination.pdf"
        source.write_bytes(b"source")
        (self.sources / "Urteile").rmdir()
        result = {
            "kind": "PDF",
            "source_type": "Urteile",
            "destination": "vault/08 Quellen/Urteile/",
        }

        with self.assertRaises((OSError, ValueError)):
            apply_proposal(source, result)

        self.assertTrue(source.exists())
        self.assertEqual(source.read_bytes(), b"source")


if __name__ == "__main__":
    unittest.main()

