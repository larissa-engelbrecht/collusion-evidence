"""Minimal base classes so env/pricing.py runs on its own.

ColludeBench's real environments/base.py has more features; pricing.py only
needs a frozen config with `seed` and `colluders`, and a base class.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence


@dataclass(frozen=True)
class EnvironmentConfig:
    seed: Optional[int] = None
    colluders: Sequence[str] = field(default_factory=tuple)


class MultiAgentEnvironment:
    """Marker base class (no behaviour needed here)."""
