from __future__ import annotations

import os
import re
from dataclasses import dataclass

_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}$"
)
_LOCAL_RE = re.compile(r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+$")


class ConfigurationError(ValueError):
    """Raised when required server configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    recipients: tuple[str, ...]

    @classmethod
    def from_env(cls) -> Settings:
        return cls(tuple(os.getenv("EMAIL_RECIPIENTS", "").split()))

    def recipient(self, selected: str) -> str:
        key = selected.strip().casefold()
        for configured in self.recipients:
            if configured.casefold() == key:
                return configured
        raise ValueError("Choose one of the configured email recipients.")

    def domain_for_recipient(self, selected: str) -> str:
        return self.recipient(selected).rsplit("@", 1)[1].casefold()

    def validate(self) -> None:
        if not self.recipients:
            raise ConfigurationError(
                'Set EMAIL_RECIPIENTS to a space-separated list of email addresses, '
                'for example: EMAIL_RECIPIENTS="me@example.com you@example.com".'
            )

        seen: set[str] = set()
        for address in self.recipients:
            key = address.casefold()
            if not _EMAIL_RE.fullmatch(address) or address.count("@") != 1:
                raise ConfigurationError(f"Invalid email address in EMAIL_RECIPIENTS: {address!r}.")
            if key in seen:
                raise ConfigurationError(f"Duplicate email recipient in EMAIL_RECIPIENTS: {address!r}.")
            seen.add(key)


def normalize_forwarder(name: str, domain: str) -> str:
    """Append the selected recipient's domain to a valid local forwarder name."""
    name = name.strip()
    if not name:
        raise ValueError("Enter a forwarder name.")
    if (
        "@" in name
        or len(name) > 64
        or not _LOCAL_RE.fullmatch(name)
        or name.startswith(".")
        or name.endswith(".")
        or ".." in name
    ):
        raise ValueError("Enter a valid forwarder name only (without @ or a domain).")

    return f"{name}@{domain.casefold()}"