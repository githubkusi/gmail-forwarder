from __future__ import annotations

import os
import re
from dataclasses import dataclass

DOMAINS = ("titlis.org", "lsass.ch")
_EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+$")
_LOCAL_RE = re.compile(r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+$")


class ConfigurationError(ValueError):
    """Raised when required server configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    owner_titlis: str
    owner_lsass: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            owner_titlis=os.getenv("TITLIS_ORG_OWNER", "").strip(),
            owner_lsass=os.getenv("LSASS_CH_OWNER", "").strip(),
        )

    def owner_for(self, domain: str) -> str:
        if domain == "titlis.org":
            return self.owner_titlis
        if domain == "lsass.ch":
            return self.owner_lsass
        raise ValueError("Choose one of the configured domains.")

    def validate(self) -> None:
        for domain, owner in (
            ("titlis.org", self.owner_titlis),
            ("lsass.ch", self.owner_lsass),
        ):
            variable = "TITLIS_ORG_OWNER" if domain == "titlis.org" else "LSASS_CH_OWNER"
            if not owner:
                raise ConfigurationError(f"Set {variable} to the owner mailbox at {domain}.")
            if not _EMAIL_RE.fullmatch(owner) or owner.count("@") != 1:
                raise ConfigurationError(f"The configured owner for {domain} is not a valid email address.")
            if owner.rsplit("@", 1)[1].casefold() != domain:
                raise ConfigurationError(f"The configured owner mailbox must use the {domain} domain.")


def normalize_forwarder(name: str, domain: str) -> str:
    """Turn a local part into an address, or validate a supplied full address."""
    if domain not in DOMAINS:
        raise ValueError("Choose one of the configured domains.")

    name = name.strip()
    if not name:
        raise ValueError("Enter a forwarder name.")

    if "@" in name:
        if name.count("@") != 1:
            raise ValueError("Enter a valid forwarder name or email address.")
        local, supplied_domain = name.rsplit("@", 1)
        if supplied_domain.casefold() != domain:
            raise ValueError(f"The address must use the selected domain, {domain}.")
    else:
        local = name

    if (
        not local
        or len(local) > 64
        or not _LOCAL_RE.fullmatch(local)
        or local.startswith(".")
        or local.endswith(".")
        or ".." in local
    ):
        raise ValueError("Use a valid email name (letters, numbers, dots, and email-safe symbols).")

    return f"{local}@{domain}"