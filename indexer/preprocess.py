from __future__ import annotations

import difflib
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List


COMMENT_PATTERN = re.compile(r"(?<!\\)%.*$", re.MULTILINE)
COMMAND_PATTERN = re.compile(r"\\[A-Za-z@]+")


@dataclass(slots=True)
class PreprocessedFile:
    path: Path
    content: str
    commands: List[str]
    line_offsets: List[int]


def preprocess_file(path: Path) -> PreprocessedFile:
    original_text = path.read_text(encoding="utf-8")
    original_stripped = _strip_comments(original_text)

    expanded = _maybe_latexpand(path)
    expanded_stripped = _strip_comments(expanded)

    commands = sorted(set(COMMAND_PATTERN.findall(expanded_stripped)))

    line_offsets = _compute_line_offsets(
        original_stripped.splitlines(), expanded_stripped.splitlines()
    )

    return PreprocessedFile(
        path=path,
        content=expanded_stripped,
        commands=commands,
        line_offsets=line_offsets,
    )


def _strip_comments(text: str) -> str:
    return COMMENT_PATTERN.sub("", text)


def _maybe_latexpand(path: Path) -> str:
    latexpand = shutil.which("latexpand")
    if not latexpand:
        return path.read_text(encoding="utf-8")

    with tempfile.NamedTemporaryFile(suffix=".tex", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with tmp_path.open("w", encoding="utf-8") as handle:
            subprocess.run(
                [latexpand, "--empty-comments", str(path)],
                check=True,
                stdout=handle,
            )
        return tmp_path.read_text(encoding="utf-8")
    except (subprocess.CalledProcessError, OSError):
        return path.read_text(encoding="utf-8")
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def _compute_line_offsets(original: List[str], processed: List[str]) -> List[int]:
    if not processed:
        return []

    matcher = difflib.SequenceMatcher(None, original, processed, autojunk=False)
    offsets = [0] * len(processed)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for idx, orig_idx in enumerate(range(i1, i2), start=j1):
                offsets[idx] = orig_idx + 1
        else:
            fallback = min(i1 + 1, len(original)) if original else 1
            if fallback <= 0:
                fallback = 1
            for idx in range(j1, j2):
                offsets[idx] = fallback

    return offsets
