import tempfile
import unittest
from pathlib import Path
from repair_agent.contract import parse_manifest
from repair_agent.policy import PolicyError, apply_patch, parse_and_validate_patch
from tests.test_contract import manifest


class PatchPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name); (self.root / "src").mkdir(); (self.root / "src/value.py").write_text("VALUE = 1\n"); self.request = parse_manifest(manifest())
    def tearDown(self): self.temp.cleanup()
    def test_allows_bounded_production_change(self):
        patch = "--- a/src/value.py\n+++ b/src/value.py\n@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n"
        files = parse_and_validate_patch(patch, self.request, self.root); apply_patch(files, self.root)
        self.assertEqual((self.root / "src/value.py").read_text(), "VALUE = 2\n")
    def test_rejects_test_and_out_of_scope_files(self):
        patch = "--- a/tests/test_value.py\n+++ b/tests/test_value.py\n@@ -1 +1 @@\n-a\n+b\n"
        with self.assertRaises(PolicyError): parse_and_validate_patch(patch, self.request, self.root)
    def test_rejects_assert_removal(self):
        (self.root / "src/value.py").write_text("assert VALUE == 1\n")
        patch = "--- a/src/value.py\n+++ b/src/value.py\n@@ -1 +1 @@\n-assert VALUE == 1\n+VALUE = 1\n"
        with self.assertRaises(PolicyError): parse_and_validate_patch(patch, self.request, self.root)
