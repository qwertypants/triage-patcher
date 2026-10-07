from __future__ import annotations

import argparse
import json
import signal
import shutil
import sys
import time
from pathlib import Path

from .artifacts import write_diagnosis, write_result
from .contract import ManifestError, parse_manifest
from .executor import disposable_copy, run_command
from .policy import PolicyError, apply_patch, parse_and_validate_patch

PATCH_PRODUCED, DIAGNOSIS_PRODUCED, REJECTED_REQUEST, CANCELLED = 0, 10, 20, 30


def _attempt(execution):
    return {"command_id": execution.command_id, "exit_code": execution.exit_code, "timed_out": execution.timed_out, "cancelled": execution.cancelled, "output_limited": execution.output_limited, "output": execution.output}


def run(request: Path, source: Path, output: Path, cancel: callable | None = None) -> int:
    try:
        manifest = parse_manifest(json.loads(request.read_text(encoding="utf-8")))
        if not source.is_dir():
            raise ManifestError("source must be an existing checkout directory")
    except (OSError, json.JSONDecodeError, ManifestError) as error:
        write_result(output, "rejected", [str(error)], [], [])
        write_diagnosis(output, "The request was rejected before running code.", [str(error)], [], "Provide a valid version-1 manifest with CI-approved commands and targets.")
        return REJECTED_REQUEST
    temp, work = disposable_copy(source)
    attempts = []
    observations = [f"Checkout reference: {manifest.checkout_ref}.", f"Runtime profile: {manifest.runtime_profile}."]
    try:
        baseline = run_command(manifest.command(manifest.focused_command_id), work, manifest.budgets.command_seconds, manifest.budgets.max_output_bytes, cancel)
        attempts.append(_attempt(baseline))
        if baseline.cancelled:
            write_result(output, "cancelled", observations + ["Focused test was cancelled."], [], attempts)
            write_diagnosis(output, "The run was cancelled; no patch was returned.", observations, ["Only evidence gathered before cancellation is included."], "Retry with a fresh CI job if cancellation was unintended.")
            return CANCELLED
        if baseline.timed_out or baseline.output_limited:
            write_result(output, "diagnosis", observations + ["Focused test exceeded its command budget."], [], attempts)
            reason = "The supplied focused test exceeded its output budget before reproduction completed." if baseline.output_limited else "The supplied focused test timed out before reproduction completed."
            write_diagnosis(output, reason, observations, ["The failure could not be safely reproduced within the declared budget."], "Increase the approved focused-test budget or reduce the focused command.")
            return DIAGNOSIS_PRODUCED
        if baseline.exit_code == 0:
            write_result(output, "diagnosis", observations + ["The supplied focused command passed in the disposable work area."], ["This may be a flaky or environment-specific failure."], attempts)
            write_diagnosis(output, "No patch was attempted because the reported failure did not reproduce.", observations, ["Possible flake or missing CI-specific condition."], "Run the exact focused command again in the originating CI environment.")
            return DIAGNOSIS_PRODUCED
        observations.append("The supplied focused command reproduced a failure.")
        started = time.monotonic()
        for number, proposal in enumerate(manifest.candidate_patches[:manifest.budgets.attempts], start=1):
            if time.monotonic() - started >= manifest.budgets.total_seconds:
                break
            candidate = Path(temp.name) / f"candidate-{number}"
            # Commands can create language runtime caches. They are execution
            # residue, not source; carrying them into a same-second candidate
            # can make an interpreter validate stale code instead of the patch.
            shutil.copytree(work, candidate, symlinks=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            try:
                files = parse_and_validate_patch(proposal, manifest, candidate)
                apply_patch(files, candidate)
            except PolicyError as error:
                observations.append(f"Candidate {number} rejected by patch policy: {error}")
                continue
            focus = run_command(manifest.command(manifest.focused_command_id), candidate, manifest.budgets.command_seconds, manifest.budgets.max_output_bytes, cancel)
            attempts.append(_attempt(focus))
            if focus.cancelled:
                write_result(output, "cancelled", observations + ["Candidate validation was cancelled."], [], attempts)
                write_diagnosis(output, "The run was cancelled; no patch was returned.", observations, ["Only evidence gathered before cancellation is included."], "Retry with a fresh CI job if cancellation was unintended.")
                return CANCELLED
            if focus.exit_code != 0 or focus.timed_out or focus.cancelled:
                observations.append(f"Candidate {number} did not pass the focused validation.")
                continue
            checks = [run_command(manifest.command(item), candidate, manifest.budgets.command_seconds, manifest.budgets.max_output_bytes, cancel) for item in manifest.static_check_ids]
            attempts.extend(_attempt(check) for check in checks)
            if any(check.cancelled for check in checks):
                write_result(output, "cancelled", observations + ["Static validation was cancelled."], [], attempts)
                write_diagnosis(output, "The run was cancelled; no patch was returned.", observations, ["Only evidence gathered before cancellation is included."], "Retry with a fresh CI job if cancellation was unintended.")
                return CANCELLED
            if all(check.exit_code == 0 and not check.timed_out and not check.cancelled for check in checks):
                (output / "fix.patch").parent.mkdir(parents=True, exist_ok=True)
                (output / "fix.patch").write_text(proposal, encoding="utf-8")
                write_result(output, "patch", observations + [f"Candidate {number} passed focused and declared static checks."], [], attempts, changed_paths=[item.path for item in files], validation_scope="focused command plus declared static checks only")
                return PATCH_PRODUCED
            observations.append(f"Candidate {number} failed a declared static check.")
        write_result(output, "diagnosis", observations, ["No candidate satisfied all enforced barriers within the approved budget."], attempts)
        write_diagnosis(output, "No safe validated patch was returned.", observations, ["Candidates were rejected, failed validation, or exhausted the configured budget."], "Inspect the focused failure output and propose a smaller production-only change.")
        return DIAGNOSIS_PRODUCED
    finally:
        temp.cleanup()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repair-agent")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--request", type=Path, required=True)
    run_parser.add_argument("--source", type=Path, default=Path.cwd())
    run_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    cancelled = False

    def cancel(_signum, _frame):
        nonlocal cancelled
        cancelled = True

    previous_int = signal.signal(signal.SIGINT, cancel)
    previous_term = signal.signal(signal.SIGTERM, cancel)
    try:
        return run(args.request, args.source.resolve(), args.output.resolve(), lambda: cancelled)
    finally:
        signal.signal(signal.SIGINT, previous_int)
        signal.signal(signal.SIGTERM, previous_term)


if __name__ == "__main__":
    sys.exit(main())
