"""Identifier helpers.

Deterministic IDs (``stable_id``) are used for things that have a natural key
(a video on a platform, a URL, a frame at a timestamp) so re-ingesting is
idempotent. Random IDs (``new_id``) are used for human/model-authored records
(observations, trades, annotations) that have no natural key.
"""

from __future__ import annotations

import hashlib
import uuid


def stable_id(prefix: str, *parts: object) -> str:
    key = "\x1f".join("" if p is None else str(p) for p in parts)
    return f"{prefix}_{hashlib.sha256(key.encode()).hexdigest()[:16]}"


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"
