import json
import tempfile
import unittest
from pathlib import Path
from repair_agent.cli import CANCELLED, DIAGNOSIS_PRODUCED, PATCH_PRODUCED, REJECTED_REQUEST, run
from tests.test_contract import manifest

PATCH = "--- a/src/value.py\n+++ b/src/value.py\n@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n"


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name) / "source"; (self.root / "src").mkdir(parents=True)
        (self.root / "src/value.py").write_text("VALUE = 1\n")
        (self.root / "check.py").write_text("from src.value import VALUE\nraise SystemExit(VALUE != 2)\n")
        (self.root / "static.py").write_text("from src.value import VALUE\nraise SystemExit(not isinstance(VALUE, int))\n")
        self.output = Path(self.temp.name) / "out"
    def tearDown(self): self.temp.cleanup()
    def _request(self, data):
        request = Path(self.temp.name) / "request.json"; request.write_text(json.dumps(data)); return request
    def test_produces_patch_after_reproduction_and_validation(self):
        self.assertEqual(run(self._request(manifest(candidate_patches=[PATCH])), self.root, self.output), PATCH_PRODUCED)
        self.assertEqual((self.output / "fix.patch").read_text(), PATCH)
        self.assertEqual(json.loads((self.output / "result.json").read_text())["status"], "patch")
        self.assertEqual((self.root / "src/value.py").read_text(), "VALUE = 1\n")
    def test_nonreproduction_produces_flake_diagnosis(self):
        (self.root / "src/value.py").write_text("VALUE = 2\n")
        self.assertEqual(run(self._request(manifest()), self.root, self.output), DIAGNOSIS_PRODUCED)
        self.assertIn("did not reproduce", (self.output / "diagnosis.md").read_text())
    def test_invalid_request_is_rejected(self):
        self.assertEqual(run(self._request({"version": 0}), self.root, self.output), REJECTED_REQUEST)
        self.assertEqual(json.loads((self.output / "result.json").read_text())["status"], "rejected")
    def test_cancellation_emits_diagnosis_artifacts(self):
        self.assertEqual(run(self._request(manifest()), self.root, self.output, cancel=lambda: True), CANCELLED)
        self.assertEqual(json.loads((self.output / "result.json").read_text())["status"], "cancelled")
        self.assertTrue((self.output / "diagnosis.md").exists())
