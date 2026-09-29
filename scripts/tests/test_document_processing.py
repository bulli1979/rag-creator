from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "documentApi"))

from app.document_processing import clean_markdown_boilerplate, scrub_sensitive_text, structured_chunks
from app.worker import parse_document


class SafePiiTests(unittest.TestCase):
    def test_contacts_are_redacted(self) -> None:
        text = (
            "Phone: +34 922 405 500\n"
            "Fax: 922 405 501\n"
            "Observer: jane.person@example.org\n"
            "Help: helpdesk@not.iac.es"
        )
        result = scrub_sensitive_text(text)
        self.assertEqual(result.count("[phone removed]"), 2)
        self.assertIn("[email removed]", result)
        self.assertIn("helpdesk@not.iac.es", result)
        self.assertNotIn("jane.person@example.org", result)

    def test_technical_values_are_unchanged(self) -> None:
        technical = (
            "Wavelength 3500 - 9000 Å; H-alpha 6562.8 Å; frequency 10 000 000 Hz.\n"
            "Coordinates RA 12:34:56.7 DEC +28 45 12.3 and +28 45 12 34.\n"
            "Signed calibration interval +3500 - 9000 Å.\n"
            "Run 2026-09-29 at 22:15:30; file NOTCam_20260929_001.fits.\n"
            "Detector 2048 x 2048, gain 0.726 e-/ADU, instrument ALFOSC/FIES."
        )
        self.assertEqual(scrub_sensitive_text(technical), technical)


class StructuredChunkTests(unittest.TestCase):
    FIXTURE = """---
title: \"ALFOSC startup\"
source_url: \"https://www.not.iac.es/instruments/alfosc/startup.html\"
category: \"procedure\"
instrument: \"ALFOSC\"
authority: \"official\"
status: \"active\"
corpus_version: \"phase3-test\"
---

Nordic Optical Telescope

[Back to top](#Top)

# Startup

WARNING: Keep the shutter closed during initialization.

## Procedure

1. Run `alfosc.init`.
2. Verify pressure is 1.2 mbar.
3. Record file ALFOSC_20260929_001.fits.

| Filter | Wavelength |
| --- | ---: |
| B | 440 nm |
| V | 550 nm |

```bash
alfosc.init --mode safe
alfosc.status
```

Last modified: May 31 2023
"""

    def test_structure_and_metadata_survive_chunking(self) -> None:
        chunks = structured_chunks(
            self.FIXTURE,
            target_chars=220,
            base_metadata={"authority": "official", "status": "active", "corpusVersion": "phase3-test"},
        )
        combined = "\n".join(chunk.text for chunk in chunks)
        self.assertNotIn("Back to top", combined)
        self.assertNotIn("Last modified", combined)
        self.assertNotIn("Nordic Optical Telescope", combined)
        self.assertIn("1. Run `alfosc.init`.", combined)
        self.assertIn("3. Record file ALFOSC_20260929_001.fits.", combined)
        self.assertIn("| B | 440 nm |", combined)
        self.assertIn("alfosc.init --mode safe", combined)
        self.assertEqual(len([c for c in chunks if "list" in c.metadata["contentTypes"]]), 1)
        self.assertEqual(len([c for c in chunks if "table" in c.metadata["contentTypes"]]), 1)
        self.assertEqual(len([c for c in chunks if "code" in c.metadata["contentTypes"]]), 1)
        for chunk in chunks:
            self.assertEqual(chunk.metadata["canonicalSource"], "https://www.not.iac.es/instruments/alfosc/startup.html")
            self.assertTrue(chunk.metadata["section"])
            self.assertIn("parentSection", chunk.metadata)
            self.assertIn("previousSection", chunk.metadata)
            self.assertIn("nextSection", chunk.metadata)
            self.assertEqual(chunk.metadata["authority"], "official")
            self.assertEqual(chunk.metadata["status"], "active")
            self.assertEqual(chunk.metadata["corpusVersion"], "phase3-test")

    def test_runtime_parser_uses_structured_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manual.md"
            path.write_text(self.FIXTURE)
            result = parse_document(str(path), 220, 40)
        self.assertTrue(result["ok"])
        self.assertGreater(len(result["chunks"]), 1)
        for index, chunk in enumerate(result["chunks"]):
            self.assertEqual(chunk["chunkIndex"], index)
            self.assertEqual(chunk["metadata"]["instrument"], "ALFOSC")
            self.assertTrue(chunk["metadata"]["section"])
            self.assertIn("sha256", chunk["metadata"])

    def test_navigation_only_document_produces_no_chunks(self) -> None:
        text = "Nordic Optical Telescope\n\n[Back to top](#Top)\n\nLast modified: May 31 2023"
        self.assertEqual(clean_markdown_boilerplate(text), "")
        self.assertEqual(structured_chunks(text), [])


if __name__ == "__main__":
    unittest.main()
