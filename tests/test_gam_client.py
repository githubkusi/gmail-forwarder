import os
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

from gmail_forwarder_web.gam_client import (
    GAM_PROJECT_APIS,
    GamClient,
    GamOperationError,
    OAUTH_SCOPES,
)


class FakeGamModule:
    def __init__(self, *, fail_on_call=None, failure_code=1):
        self.commands = []
        self.fail_on_call = fail_on_call
        self.failure_code = failure_code
        self.API = SimpleNamespace(PROJECT_APIS=["all GAM APIs"])
        self.project_apis_seen = []
        self.ACTION_FAILED_RC = 50

    def initializeLogging(self):
        pass

    def CallGAMCommand(self, args):
        self.commands.append(args)
        if len(args) > 3 and args[1:3] == ["redirect", "stdout"]:
            output_path = Path(args[3])
            output_path.write_text("GAM output\n", encoding="utf-8")
        result = self.failure_code if len(self.commands) == self.fail_on_call else 0
        if args[1:] == ["create", "project"]:
            self.project_apis_seen.append(self.API.PROJECT_APIS.copy())
            Path(os.environ["CLIENTSECRETS"]).write_text("{}", encoding="utf-8")
        return result


def test_add_forwarder_uses_expected_gam_sequence(monkeypatch):
    fake = FakeGamModule()
    monkeypatch.setitem(sys.modules, "gam", fake)

    output = GamClient().add_forwarder("team@example.org", "admin@example.org")

    assert output == "GAM output\nGAM output"
    assert fake.commands[0][4:] == [
        "create",
        "group",
        "team@example.org",
        "whoCanPostMessage",
        "ANYONE_CAN_POST",
    ]
    assert fake.commands[1][4:] == [
        "update",
        "group",
        "team@example.org",
        "add",
        "owner",
        "user",
        "admin@example.org",
    ]


def test_owner_assignment_error_is_reported_as_partial(monkeypatch):
    fake = FakeGamModule(fail_on_call=2)
    monkeypatch.setitem(sys.modules, "gam", fake)

    with pytest.raises(GamOperationError, match="group team@example.org was created") as error:
        GamClient().add_forwarder("team@example.org", "admin@example.org")

    assert error.value.partial is True


def test_initial_setup_uses_readonly_client_secret_and_persistent_oauth_file(monkeypatch, tmp_path):
    fake = FakeGamModule()
    monkeypatch.setitem(sys.modules, "gam", fake)
    monkeypatch.setenv("GAMCFGDIR", str(tmp_path / "gam-config"))
    client_file = tmp_path / "mounted-client" / "client_secrets.json"
    client_file.parent.mkdir()
    client_file.write_text("{}", encoding="utf-8")
    user_config_dir = tmp_path / "gam-auth-volume"
    monkeypatch.setenv("GAMUSERCONFIGDIR", str(user_config_dir))
    monkeypatch.setenv("CLIENTSECRETS", str(client_file))
    monkeypatch.setenv("GAM_WORK_DIR", str(tmp_path / "work"))

    from gmail_forwarder_web.gam_client import initialize_gam

    initialize_gam()

    config_command = fake.commands[0][1:]
    assert config_command[config_command.index("config_dir") + 1] == str(user_config_dir)
    assert config_command[config_command.index("client_secrets_json") + 1] == str(client_file)
    assert config_command[config_command.index("oauth2_txt") + 1] == str(user_config_dir / "oauth2.txt")
    assert fake.commands[1][1:] == ["oauth", "create", "scopes", ",".join(OAUTH_SCOPES)]
    assert ["print", "groups", "showitemcountonly"] in [
        call[4:] for call in fake.commands if call[1:3] == ["redirect", "stdout"]
    ]


def test_initial_setup_creates_client_secret_with_gam_when_missing(monkeypatch, tmp_path):
    fake = FakeGamModule()
    monkeypatch.setitem(sys.modules, "gam", fake)
    monkeypatch.setenv("GAMCFGDIR", str(tmp_path / "gam-config"))
    monkeypatch.setenv("GAMUSERCONFIGDIR", str(tmp_path / "gam-auth-volume"))
    client_file = tmp_path / "mounted-client" / "client_secrets.json"
    client_file.parent.mkdir()
    monkeypatch.setenv("CLIENTSECRETS", str(client_file))
    monkeypatch.setenv("GAM_WORK_DIR", str(tmp_path / "work"))

    from gmail_forwarder_web.gam_client import initialize_gam

    initialize_gam()

    assert client_file.read_text(encoding="utf-8") == "{}"
    assert client_file.stat().st_mode & 0o777 == 0o600
    assert fake.commands[0][1:] == ["create", "project"]
    assert fake.project_apis_seen == [list(GAM_PROJECT_APIS)]
    assert fake.API.PROJECT_APIS == ["all GAM APIs"]
    assert fake.commands[1][1:2] == ["config"]
    assert fake.commands[2][1:] == ["oauth", "create", "scopes", ",".join(OAUTH_SCOPES)]


def test_initial_setup_continues_after_gam_action_warning_when_secret_exists(monkeypatch, tmp_path):
    fake = FakeGamModule(fail_on_call=1, failure_code=50)
    monkeypatch.setitem(sys.modules, "gam", fake)
    monkeypatch.setenv("GAMCFGDIR", str(tmp_path / "gam-config"))
    monkeypatch.setenv("GAMUSERCONFIGDIR", str(tmp_path / "gam-auth-volume"))
    client_file = tmp_path / "mounted-client" / "client_secrets.json"
    client_file.parent.mkdir()
    monkeypatch.setenv("CLIENTSECRETS", str(client_file))
    monkeypatch.setenv("GAM_WORK_DIR", str(tmp_path / "work"))

    from gmail_forwarder_web.gam_client import initialize_gam

    initialize_gam()

    assert client_file.is_file()
    assert client_file.stat().st_mode & 0o777 == 0o600
    assert fake.commands[1][1:2] == ["config"]
    assert fake.commands[2][1:] == ["oauth", "create", "scopes", ",".join(OAUTH_SCOPES)]


def test_initial_setup_imports_mounted_client_secret_with_restricted_permissions(monkeypatch, tmp_path):
    fake = FakeGamModule()
    monkeypatch.setitem(sys.modules, "gam", fake)
    monkeypatch.setenv("GAMCFGDIR", str(tmp_path / "gam-config"))
    monkeypatch.setenv("GAMUSERCONFIGDIR", str(tmp_path / "gam-auth-volume"))
    client_file = tmp_path / "gam-client-volume" / "client_secrets.json"
    source_file = tmp_path / "import" / "client_secrets.json"
    client_file.parent.mkdir()
    source_file.parent.mkdir()
    source_file.write_text("client secret", encoding="utf-8")
    monkeypatch.setenv("CLIENTSECRETS", str(client_file))
    monkeypatch.setenv("GAM_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setattr("gmail_forwarder_web.gam_client.IMPORTED_CLIENT_SECRETS", source_file)

    from gmail_forwarder_web.gam_client import initialize_gam

    initialize_gam()

    assert client_file.read_text(encoding="utf-8") == "client secret"
    assert client_file.stat().st_mode & 0o777 == 0o600
    assert fake.commands[0][1:2] == ["config"]
    assert fake.commands[1][1:] == ["oauth", "create", "scopes", ",".join(OAUTH_SCOPES)]


def test_initial_setup_does_not_overwrite_existing_client_secret(monkeypatch, tmp_path):
    fake = FakeGamModule()
    monkeypatch.setitem(sys.modules, "gam", fake)
    destination = tmp_path / "gam-client-volume" / "client_secrets.json"
    source = tmp_path / "imported-client_secrets.json"
    destination.parent.mkdir()
    destination.write_text("original", encoding="utf-8")
    source.write_text("replacement", encoding="utf-8")
    monkeypatch.setenv("CLIENTSECRETS", str(destination))
    monkeypatch.setenv("GAMUSERCONFIGDIR", str(tmp_path / "gam-auth-volume"))
    monkeypatch.setenv("GAM_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setattr("gmail_forwarder_web.gam_client.IMPORTED_CLIENT_SECRETS", source)

    from gmail_forwarder_web.gam_client import initialize_gam

    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        initialize_gam()

    assert destination.read_text(encoding="utf-8") == "original"
    assert fake.commands == []


def test_gam_setup_runs_without_client_secrets_argument(monkeypatch):
    from gmail_forwarder_web import gam_setup

    received = []
    monkeypatch.setattr(gam_setup, "initialize_gam", lambda: received.append(True))

    gam_setup.main()

    assert received == [True]


def test_initial_setup_reports_failed_authorization_check(monkeypatch, tmp_path):
    fake = FakeGamModule(fail_on_call=3)
    monkeypatch.setitem(sys.modules, "gam", fake)
    monkeypatch.setenv("GAMCFGDIR", str(tmp_path / "gam-config"))
    client_file = tmp_path / "mounted-client" / "client_secrets.json"
    client_file.parent.mkdir()
    client_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GAMUSERCONFIGDIR", str(tmp_path / "gam-auth-volume"))
    monkeypatch.setenv("CLIENTSECRETS", str(client_file))
    monkeypatch.setenv("GAM_WORK_DIR", str(tmp_path / "work"))

    from gmail_forwarder_web.gam_client import initialize_gam

    with pytest.raises(RuntimeError, match="OAuth authorization completed"):
        initialize_gam()