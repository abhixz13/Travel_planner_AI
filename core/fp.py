"""Fingerprint helper utilities."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List


def _normalize_value(value: Any) -> Any:
    """Normalize individual values for fingerprinting."""
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "" or stripped.lower() == "null":
            return None
        return stripped
    return value


def compute_fp(ex: Dict[str, Any], keys: List[str]) -> str:
    """Compute a deterministic fingerprint for a subset of extracted info."""
    subset = {}
    data = ex or {}
    for key in keys:
        subset[key] = _normalize_value(data.get(key))
    payload = json.dumps(subset, sort_keys=True, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()
