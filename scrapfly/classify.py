"""Classify API response model.

Mirrors the `/classify` endpoint response. See
https://scrapfly.io/docs/scrape-api/classify for the full contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ClassifyResult:
    blocked: bool
    antibot: Optional[str]
    cost: int

    @classmethod
    def from_dict(cls, data: dict) -> "ClassifyResult":
        return cls(
            blocked=bool(data.get("blocked", False)),
            antibot=data.get("antibot"),
            cost=int(data.get("cost", 0)),
        )
