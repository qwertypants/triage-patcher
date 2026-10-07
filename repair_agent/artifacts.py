from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_result(output: Path, status: str, observations: list[str], hypotheses: list[str], attempts: list[dict[str, Any]], **extra: Any) -> None:
    output.mkdir(parents=True, exist_ok=True)
    result = {"version": 1, "status": status, "observations": observations, "hypotheses": hypotheses, "attempts": attempts, **extra}
    (output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_diagnosis(output: Path, reason: str, observations: list[str], hypotheses: list[str], next_check: str) -> None:
    lines = ["# Repair diagnosis", "", f"## What happened\n{reason}", "", "## Observations"]
    lines.extend(f"- {item}" for item in observations or ["No command output was available."])
    lines.extend(["", "## Hypotheses and limits"])
    lines.extend(f"- {item}" for item in hypotheses or ["No safe conclusion beyond the observed evidence."])
    lines.extend(["", f"## Smallest next check\n{next_check}", ""])
    (output / "diagnosis.md").write_text("\n".join(lines), encoding="utf-8")
