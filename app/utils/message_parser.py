"""
Message normalization helpers for Notiflow.
"""

from __future__ import annotations

import re


class MessageParser:
    """Normalize incoming business messages before they reach the agents."""

    _whitespace_pattern = re.compile(r"\s+")

    def parse(self, message: str) -> str:
        """Normalize a message for downstream LLM processing."""
        if message is None:
            return ""
        normalized = str(message).strip().lower()
        normalized = self._whitespace_pattern.sub(" ", normalized)
        return normalized


def parse_message(message: str) -> str:
    """Convenience wrapper used by the backend entry point."""
    return MessageParser().parse(message)
