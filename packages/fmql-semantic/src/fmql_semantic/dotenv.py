from __future__ import annotations

from pathlib import Path

from fmql_semantic.errors import ConfigError


def load_dotenv(path: str | Path) -> dict[str, str]:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"dotenv file not found: {p}")
    out: dict[str, str] = {}
    for lineno, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            raise ConfigError(f"{p}:{lineno}: expected KEY=VALUE, got {raw!r}")
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            raise ConfigError(f"{p}:{lineno}: empty key")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        out[key] = value
    return out
