import unittest

from repair_agent.contract import ManifestError, parse_manifest


def manifest(**overrides):
    data = {
        "version": 1, "checkout_ref": "abc123",
        "failing_test": {"command_id": "focused", "evidence": "expected 2 got 1"},
        "target_paths": ["src/value.py"],
        "commands": [{"id": "focused", "kind": "focused_test", "argv": ["python3", "check.py"]}, {"id": "static", "kind": "static_check", "argv": ["python3", "static.py"]}],
        "static_check_ids": ["static"], "runtime_profile": "python-3.11",
        "budgets": {"total_seconds": 10, "command_seconds": 2, "attempts": 1, "max_files": 1, "max_lines": 5, "max_output_bytes": 4096},
    }
    data.update(overrides)
    return data


class ManifestTests(unittest.TestCase):
    def test_valid_manifest(self): self.assertEqual(parse_manifest(manifest()).targets, ("src/value.py",))
    def test_rejects_shell_like_arguments(self):
        data = manifest(); data["commands"][0]["argv"] = ["python3", "check.py; rm"]
        with self.assertRaises(ManifestError): parse_manifest(data)
    def test_rejects_unsafe_target(self):
        with self.assertRaises(ManifestError): parse_manifest(manifest(target_paths=["../outside.py"]))
    def test_rejects_unapproved_static_command(self):
        with self.assertRaises(ManifestError): parse_manifest(manifest(static_check_ids=["nope"]))
