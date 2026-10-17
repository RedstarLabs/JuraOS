
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.check_vault import (
    check_frontmatter,
    check_links,
    check_templates,
    check_tracked_private_files,
)


class VaultCheckerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_note(self, relative_path, content):
        path = self.vault / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_existing_wikilink_is_valid(self):
        note = self.write_note("Quelle.md", "[[Staatsrecht I]]")
        self.write_note("02 Studium/Staatsrecht I.md", "# Staatsrecht")

        with patch("scripts.check_vault.VAULT", self.vault):
            errors = check_links([note])

        self.assertEqual(errors, [])

    def test_missing_wikilink_is_reported(self):
        note = self.write_note(
            "Quelle.md",
            "[[Nicht vorhandene Notiz]]",
        )

        with patch("scripts.check_vault.VAULT", self.vault):
            errors = check_links([note])

        self.assertEqual(len(errors), 1)
        self.assertIn("Nicht vorhandene Notiz", errors[0])

    def test_valid_frontmatter(self):
        note = self.write_note(
            "Quelle.md",
            "---\ntitel: Testquelle\ntyp: skript\n---\n\nInhalt",
        )

        with patch("scripts.check_vault.VAULT", self.vault):
            errors = check_frontmatter([note])

        self.assertEqual(errors, [])

    def test_unclosed_frontmatter_is_reported(self):
        note = self.write_note(
            "Quelle.md",
            "---\ntitel: Testquelle\n\nInhalt",
        )

        with patch("scripts.check_vault.VAULT", self.vault):
            errors = check_frontmatter([note])

        self.assertEqual(len(errors), 1)
        self.assertIn("Frontmatter", errors[0])

    def test_missing_template_is_reported(self):
        (self.vault / "90 Templates").mkdir()

        with patch("scripts.check_vault.VAULT", self.vault):
            errors = check_templates()

        self.assertEqual(len(errors), 6)

    def test_tracked_private_pdf_is_reported(self):
        tracked_files = (
            b"vault/08 Quellen/Vorlesungsunterlagen/privat.pdf\0"
        )

        with patch("scripts.check_vault.subprocess.run") as mocked_run:
            mocked_run.return_value.stdout = tracked_files
            mocked_run.return_value.returncode = 0

            errors = check_tracked_private_files()

        self.assertTrue(
            any("privat.pdf" in error for error in errors)
        )


if __name__ == "__main__":
    unittest.main()
