from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class Command:
    id: str
    argv: tuple[str, ...]
    kind: str


@dataclass(frozen=True)
class Budgets:
    total_seconds: int
    command_seconds: int
    attempts: int
    max_files: int
    max_lines: int
    max_output_bytes: int


@dataclass(frozen=True)
class Manifest:
    checkout_ref: str
    evidence: str
    targets: tuple[str, ...]
    commands: tuple[Command, ...]
    focused_command_id: str
    static_check_ids: tuple[str, ...]
    runtime_profile: str
    budgets: Budgets
    candidate_patches: tuple[str, ...]

    def command(self, command_id: str) -> Command:
        for command in self.commands:
            if command.id == command_id:
                return command
        raise ManifestError(f"unknown approved command id: {command_id}")


def _path(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ManifestError(f"{field} must be a non-empty repository-relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path == PurePosixPath("."):
        raise ManifestError(f"{field} is not a safe repository-relative path")
    return value


def _positive(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ManifestError(f"budgets.{key} must be a positive integer")
    return value


def parse_manifest(data: Any) -> Manifest:
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ManifestError("version must be 1")
    checkout_ref = data.get("checkout_ref")
    if not isinstance(checkout_ref, str) or not checkout_ref.strip():
        raise ManifestError("checkout_ref is required")
    failure = data.get("failing_test")
    if not isinstance(failure, dict) or not isinstance(failure.get("evidence"), str) or not failure["evidence"].strip():
        raise ManifestError("failing_test.evidence is required")
    focused_id = failure.get("command_id")
    if not isinstance(focused_id, str):
        raise ManifestError("failing_test.command_id is required")
    targets_raw = data.get("target_paths")
    if not isinstance(targets_raw, list) or not targets_raw:
        raise ManifestError("target_paths must be a non-empty list")
    targets = tuple(_path(path, "target_paths") for path in targets_raw)
    if len(set(targets)) != len(targets):
        raise ManifestError("target_paths must not contain duplicates")
    commands_raw = data.get("commands")
    if not isinstance(commands_raw, list) or not commands_raw:
        raise ManifestError("commands must be a non-empty list")
    commands = []
    for item in commands_raw:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            raise ManifestError("each command needs an id")
        argv = item.get("argv")
        if not isinstance(argv, list) or not argv or any(not isinstance(arg, str) or not arg or any(c in arg for c in ";&|`$\n") for arg in argv):
            raise ManifestError(f"command {item['id']} has unsafe argv")
        kind = item.get("kind")
        if kind not in {"focused_test", "static_check"}:
            raise ManifestError(f"command {item['id']} has invalid kind")
        commands.append(Command(item["id"], tuple(argv), kind))
    if len({command.id for command in commands}) != len(commands):
        raise ManifestError("command ids must be unique")
    command_map = {command.id: command for command in commands}
    if focused_id not in command_map or command_map[focused_id].kind != "focused_test":
        raise ManifestError("failing_test.command_id must select a focused_test command")
    static_ids_raw = data.get("static_check_ids", [])
    if not isinstance(static_ids_raw, list) or any(not isinstance(item, str) for item in static_ids_raw):
        raise ManifestError("static_check_ids must be a list")
    if any(item not in command_map or command_map[item].kind != "static_check" for item in static_ids_raw):
        raise ManifestError("static_check_ids must select static_check commands")
    profile = data.get("runtime_profile")
    if not isinstance(profile, str) or not profile.strip():
        raise ManifestError("runtime_profile is required")
    raw_budgets = data.get("budgets")
    if not isinstance(raw_budgets, dict):
        raise ManifestError("budgets is required")
    budgets = Budgets(*(_positive(raw_budgets, name) for name in ("total_seconds", "command_seconds", "attempts", "max_files", "max_lines", "max_output_bytes")))
    proposals = data.get("candidate_patches", [])
    if not isinstance(proposals, list) or any(not isinstance(patch, str) for patch in proposals):
        raise ManifestError("candidate_patches must be a list of unified diff strings")
    return Manifest(checkout_ref, failure["evidence"], targets, tuple(commands), focused_id, tuple(static_ids_raw), profile, budgets, tuple(proposals))
