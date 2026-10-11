import sys
import os
from pathlib import Path
import pytest

from gmail_forwarder_web.gam_client import GamClient, GamOperationError, OAUTH_SCOPES


class FakeGamModule:
    def __init__(self, *, fail_on_call=None):
        self.commands = []
        self.fail_on_call = fail_on_call

    def initializeLogging(self):
        pass

    def CallGAMCommand(self, args):
        self.commands.append(args)
        if len(args) > 3 and args[1:3] == ["redirect", "stdout"]:
            output_path = Path(args[3])
            output_path.write_text("GAM output\n", encoding="utf-8")
        result = int(len(self.commands) == self.fail_on_call)
        if not result and args[1:] == ["create", "project"]:
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
    assert fake.commands[0][1:] == ["create", "project"]
    assert fake.commands[1][1:2] == ["config"]
    assert fake.commands[2][1:] == ["oauth", "create", "scopes", ",".join(OAUTH_SCOPES)]


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