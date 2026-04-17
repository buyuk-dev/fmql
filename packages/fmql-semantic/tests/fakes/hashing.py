from __future__ import annotations

import hashlib
import math


def deterministic_vector(text: str, dim: int = 8) -> list[float]:
    """SHA256-derived, L2-normalised vector. Stable across runs and platforms."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    vals: list[float] = []
    i = 0
    while len(vals) < dim:
        if i >= len(digest):
            digest = hashlib.sha256(digest).digest()
            i = 0
        byte = digest[i]
        vals.append(byte / 255.0 - 0.5)
        i += 1
    norm = math.sqrt(sum(v * v for v in vals))
    if norm == 0:
        return vals
    return [v / norm for v in vals]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
