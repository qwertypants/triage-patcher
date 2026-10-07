from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .contract import Manifest


class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class FilePatch:
    path: str
    hunks: tuple[tuple[int, int, tuple[str, ...]], ...]
    changed_lines: int


_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_FORBIDDEN_PATH = re.compile(r"(^|/)(test|tests|spec|__tests__|\.github)(/|$)|(^|/)(package-lock\.json|pnpm-lock\.yaml|pyproject\.toml|Dockerfile|.*\.ya?ml)$", re.I)
_EVASION = re.compile(r"\b(skip|xfail|mock|monkeypatch|suppress|ignore_errors?|catch\s*\(.*\)\s*\{?\s*\})\b", re.I)


def parse_and_validate_patch(patch: str, manifest: Manifest, root: Path) -> tuple[FilePatch, ...]:
    if not patch.strip() or "GIT binary patch" in patch or "new file mode" in patch or "deleted file mode" in patch or "120000" in patch:
        raise PolicyError("patch must only modify regular text files")
    lines = patch.splitlines()
    patches: list[FilePatch] = []
    index = 0
    while index < len(lines):
        if not lines[index].startswith("--- "):
            raise PolicyError("patch is not a unified diff")
        if index + 1 >= len(lines) or not lines[index + 1].startswith("+++ "):
            raise PolicyError("patch has an incomplete file header")
        old, new = lines[index][4:].split("\t", 1)[0], lines[index + 1][4:].split("\t", 1)[0]
        if not old.startswith("a/") or not new.startswith("b/") or old[2:] != new[2:]:
            raise PolicyError("patch may not add, delete, or rename files")
        path = new[2:]
        if path not in manifest.targets or _FORBIDDEN_PATH.search(path):
            raise PolicyError(f"patch touches prohibited or out-of-scope path: {path}")
        file_path = root / path
        if not file_path.is_file() or file_path.is_symlink():
            raise PolicyError(f"patch target is not a regular existing file: {path}")
        try:
            file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise PolicyError(f"patch target is not text: {path}") from error
        index += 2
        hunks = []
        changed = 0
        while index < len(lines) and not lines[index].startswith("--- "):
            match = _HEADER.match(lines[index])
            if not match:
                raise PolicyError("invalid hunk header")
            old_start, old_count = int(match.group(1)), int(match.group(2) or 1)
            index += 1
            body = []
            old_seen = 0
            while index < len(lines) and not lines[index].startswith("@@ ") and not lines[index].startswith("--- "):
                line = lines[index]
                if not line or line[0] not in " +-\\":
                    raise PolicyError("invalid hunk body")
                if line.startswith("-"):
                    old_seen += 1
                    if "assert" in line.lower() or _EVASION.search(line[1:]):
                        raise PolicyError("patch appears to weaken test behavior or suppress errors")
                    changed += 1
                elif line.startswith("+"):
                    if _EVASION.search(line[1:]):
                        raise PolicyError("patch contains a prohibited evasion pattern")
                    changed += 1
                elif line.startswith(" "):
                    old_seen += 1
                body.append(line)
                index += 1
            if old_seen != old_count:
                raise PolicyError("hunk old-line count does not match header")
            hunks.append((old_start, old_count, tuple(body)))
        patches.append(FilePatch(path, tuple(hunks), changed))
    if not patches:
        raise PolicyError("patch contains no file changes")
    if len(patches) > manifest.budgets.max_files:
        raise PolicyError("patch exceeds file budget")
    if sum(item.changed_lines for item in patches) > manifest.budgets.max_lines:
        raise PolicyError("patch exceeds line budget")
    return tuple(patches)


def apply_patch(files: tuple[FilePatch, ...], root: Path) -> None:
    for file_patch in files:
        target = root / file_patch.path
        original = target.read_text(encoding="utf-8").splitlines(keepends=True)
        output: list[str] = []
        cursor = 0
        for old_start, _old_count, body in file_patch.hunks:
            start = old_start - 1
            if start < cursor:
                raise PolicyError("overlapping patch hunks")
            output.extend(original[cursor:start])
            cursor = start
            for line in body:
                if line.startswith("\\"):
                    continue
                content = line[1:] + "\n"
                if line.startswith(" "):
                    if cursor >= len(original) or original[cursor].rstrip("\n") != line[1:]:
                        raise PolicyError("patch context does not match source")
                    output.append(original[cursor])
                    cursor += 1
                elif line.startswith("-"):
                    if cursor >= len(original) or original[cursor].rstrip("\n") != line[1:]:
                        raise PolicyError("patch removal does not match source")
                    cursor += 1
                elif line.startswith("+"):
                    output.append(content)
        output.extend(original[cursor:])
        target.write_text("".join(output), encoding="utf-8")
