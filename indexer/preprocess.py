from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List

COMMENT_PATTERN = re.compile(r"(?<!\\)%.*$")
COMMAND_PATTERN = re.compile(r"\\[a-zA-Z@]+")


@dataclass(slots=True)
class PreprocessedFile:
    path: Path
    content: str
    commands: List[str]


def preprocess_file(path: Path) -> PreprocessedFile:
    expanded = _maybe_latexpand(path)
    stripped = _strip_comments(expanded)
    commands = sorted(set(COMMAND_PATTERN.findall(stripped)))
    return PreprocessedFile(path=path, content=stripped, commands=commands)


def _strip_comments(text: str) -> str:
    lines = text.splitlines()
    cleaned = [COMMENT_PATTERN.sub("", line) for line in lines]
    return "\n".join(cleaned)


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
