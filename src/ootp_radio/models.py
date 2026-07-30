"""Typed data returned by OOTP Radio parsers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GameRecap:
    """A cleaned recap extracted from an OOTP game box score."""

    game_id: int
    subject: str
    body: str

