from __future__ import annotations

from abc import ABC, abstractmethod

from stream_tui.models import StreamLink


class Player(ABC):
    id: str

    @abstractmethod
    def play(self, stream: StreamLink, title: str, resume_seconds: float = 0.0) -> int:
        """Block until playback ends; return the process exit code."""

    @abstractmethod
    def is_available(self) -> bool:
        """Whether the player binary is installed/on PATH."""
