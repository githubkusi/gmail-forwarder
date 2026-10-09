from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


class GamOperationError(RuntimeError):
    def __init__(self, stage: str, message: str, *, partial: bool = False) -> None:
        super().__init__(message)
        self.stage = stage
        self.partial = partial


@dataclass
class GamClient:
    """Thin adapter around GAM7's Python API; GAM credentials remain in GAM's config dir."""

    def _gam(self):
        try:
            import gam
        except ImportError as exc:
            raise RuntimeError("GAM7 is not installed in this application image.") from exc
        return gam

    def setup(self) -> None:
        gam = self._gam()
        gam.initializeLogging()

    def _call(self, command: list[str]) -> str:
        gam = self._gam()
        try:
            with tempfile.NamedTemporaryFile() as output:
                return_code = gam.CallGAMCommand(
                    ["gam", "redirect", "stdout", output.name, *command]
                )
                output.seek(0)
                result = output.read().decode("utf-8", errors="replace")
            if return_code:
                detail = result.strip() or f"GAM exited with status {return_code}."
                raise RuntimeError(detail)
            return result
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc

    def add_forwarder(self, address: str, owner: str) -> str:
        try:
            created = self._call(
                ["create", "group", address, "whoCanPostMessage", "ANYONE_CAN_POST"]
            )
        except Exception as exc:
            raise GamOperationError("create", f"GAM could not create {address}: {exc}") from exc

        try:
            assigned = self._call(["update", "group", address, "add", "owner", "user", owner])
        except Exception as exc:
            raise GamOperationError(
                "assign_owner",
                f"The group {address} was created, but adding {owner} as owner failed: {exc}",
                partial=True,
            ) from exc
        return "\n".join(part for part in (created.strip(), assigned.strip()) if part)

    def print_groups(self) -> str:
        return self._call(["print", "groups"])


def initialize_gam() -> None:
    """Initialize GAM settings and create OAuth authorization in persistent storage."""
    client = GamClient()
    client.setup()
    gam = client._gam()
    work_dir = os.getenv("GAM_WORK_DIR", "/var/lib/gam-work")
    config_dir = Path(os.path.expanduser(os.getenv("GAMCFGDIR", "~/.gam")))
    user_config_dir = Path(
        os.path.expanduser(os.getenv("GAMUSERCONFIGDIR", str(config_dir)))
    )
    client_secrets = Path(
        os.path.expanduser(
            os.getenv("CLIENTSECRETS", str(user_config_dir / "client_secrets.json"))
        )
    )
    oauth_token = Path(
        os.path.expanduser(os.getenv("OAUTHFILE", str(user_config_dir / "oauth2.txt")))
    )

    os.makedirs(work_dir, exist_ok=True)
    user_config_dir.mkdir(parents=True, exist_ok=True)
    if not client_secrets.is_file():
        raise RuntimeError(
            f"GAM OAuth client file not found: {client_secrets}. "
            "Set GAM_AUTH_DIR to a directory containing client_secrets.json."
        )

    commands = (
        [
            "config",
            "no_browser",
            "true",
            "config_dir",
            str(user_config_dir),
            "client_secrets_json",
            str(client_secrets),
            "oauth2_txt",
            str(oauth_token),
            "drive_dir",
            work_dir,
            "save",
            "verify",
        ],
        ["oauth", "create"],
    )
    for command in commands:
        result = gam.CallGAMCommand(["gam", *command])
        if result:
            raise RuntimeError(
                f"GAM setup command {' '.join(command)} failed with status {result}."
            )

    try:
        client._call(["print", "groups", "showitemcountonly"])
    except RuntimeError as exc:
        raise RuntimeError(
            "GAM OAuth authorization completed, but the Workspace group check failed. "
            "Check the selected OAuth scopes and administrator access. "
            f"GAM reported: {exc}"
        ) from exc