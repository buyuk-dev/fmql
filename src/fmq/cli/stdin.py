from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Optional, TextIO


@dataclass
class StdinResult:
    mode: str  # "paths" | "jsonl" | "empty"
    raw_paths: list[str]       # verbatim strings (unresolved) when mode="paths"
    pids: list[str]            # when mode="jsonl"


def read_stdin_targets(*, stream: Optional[TextIO] = None) -> StdinResult:
    if stream is None:
        stream = sys.stdin
    text = stream.read()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return StdinResult(mode="empty", raw_paths=[], pids=[])
    first = lines[0].lstrip()
    if first.startswith("{"):
        pids: list[str] = []
        for ln in lines:
            try:
                obj = json.loads(ln)
            except json.JSONDecodeError as e:
                raise ValueError(f"invalid JSONL line: {ln!r}: {e}") from e
            if not isinstance(obj, dict) or "id" not in obj:
                raise ValueError(f"JSONL line missing 'id' field: {ln!r}")
            pids.append(str(obj["id"]))
        return StdinResult(mode="jsonl", raw_paths=[], pids=pids)
    if first.startswith("["):
        raise ValueError("JSON array input not supported; use JSONL")
    return StdinResult(mode="paths", raw_paths=lines, pids=[])


def confirm_prompt(msg: str = "Apply these changes? [y/N] ") -> bool:
    try:
        with open("/dev/tty", "r") as tty:
            sys.stderr.write(msg)
            sys.stderr.flush()
            ans = tty.readline().strip().lower()
            return ans in ("y", "yes")
    except OSError:
        sys.stderr.write("error: no terminal for confirmation; use --yes\n")
        return False
