from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from typing import Protocol

from .config import Settings, normalize_forwarder
from .gam_client import GamOperationError

_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+")


class Gateway(Protocol):
    def setup(self) -> None: ...

    def add_forwarder(self, address: str, owner: str) -> str: ...

    def print_groups(self) -> str: ...


@dataclass
class ForwarderService:
    settings: Settings
    gateway: Gateway

    def __post_init__(self) -> None:
        self._gam_lock = threading.Lock()

    def create(self, name: str, selected_recipient: str) -> tuple[str, str]:
        recipient = self.settings.recipient(selected_recipient)
        domain = recipient.rsplit("@", 1)[1].casefold()
        address = normalize_forwarder(name, domain)
        with self._gam_lock:
            output = self.gateway.add_forwarder(address, recipient)
        return address, output

    def search(self, pattern: str) -> list[str]:
        pattern = pattern.strip()
        if not pattern:
            raise ValueError("Enter a search term.")
        if len(pattern) > 100:
            raise ValueError("Search terms must be 100 characters or fewer.")

        with self._gam_lock:
            output = self.gateway.print_groups()
        matches: list[str] = []
        seen: set[str] = set()
        for address in _EMAIL_PATTERN.findall(output):
            key = address.casefold()
            if pattern.casefold() in key and key not in seen:
                matches.append(address)
                seen.add(key)
        return matches


__all__ = ["ForwarderService", "GamOperationError"]