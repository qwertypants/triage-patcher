import tempfile
import unittest
from pathlib import Path

from repair_agent.contract import Command
from repair_agent.executor import run_command


class ExecutorTests(unittest.TestCase):
    def test_enforces_output_budget_while_command_runs(self):
        with tempfile.TemporaryDirectory() as temp:
            command = Command("loud", ("python3", "-c", "print('x' * 1000000)"), "static_check")
            result = run_command(command, Path(temp), timeout=2, max_output_bytes=64)
        self.assertTrue(result.output_limited)
        self.assertLessEqual(len(result.output), 110)

    def test_cancels_entire_command_group(self):
        with tempfile.TemporaryDirectory() as temp:
            command = Command("wait", ("python3", "-c", "import time; time.sleep(10)"), "static_check")
            result = run_command(command, Path(temp), timeout=2, max_output_bytes=64, cancel=lambda: True)
        self.assertTrue(result.cancelled)
