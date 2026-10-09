import sys
from pathlib import Path
import pytest

from gmail_forwarder_web.gam_client import GamClient, GamOperationError


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
        return int(len(self.commands) == self.fail_on_call)


def test_add_forwarder_uses_expected_gam_sequence(monkeypatch):
    fake = FakeGamModule()
    monkeypatch.setitem(sys.modules, "gam", fake)

    output = GamClient().add_forwarder("team@titlis.org", "admin@titlis.org")

    assert output == "GAM output\nGAM output"
    assert fake.commands[0][4:] == [
        "create",
        "group",
        "team@titlis.org",
        "whoCanPostMessage",
        "ANYONE_CAN_POST",
    ]
    assert fake.commands[1][4:] == [
        "update",
        "group",
        "team@titlis.org",
        "add",
        "owner",
        "user",
        "admin@titlis.org",
    ]


def test_owner_assignment_error_is_reported_as_partial(monkeypatch):
    fake = FakeGamModule(fail_on_call=2)
    monkeypatch.setitem(sys.modules, "gam", fake)

    with pytest.raises(GamOperationError, match="group team@titlis.org was created") as error:
        GamClient().add_forwarder("team@titlis.org", "admin@titlis.org")

    assert error.value.partial is True


def test_reuse_existing_credentials_skips_project_and_oauth(monkeypatch, tmp_path):
    fake = FakeGamModule()
    monkeypatch.setitem(sys.modules, "gam", fake)
    monkeypatch.setenv("GAMCFGDIR", str(tmp_path))
    credentials_dir = tmp_path / "credentials"
    credentials_dir.mkdir()
    monkeypatch.setenv("GAMUSERCONFIGDIR", str(credentials_dir))
    monkeypatch.setenv("GAM_WORK_DIR", str(tmp_path / "work"))
    (credentials_dir / "client_secrets.json").write_text("{}", encoding="utf-8")
    (credentials_dir / "oauth2.txt").write_text("{}", encoding="utf-8")

    from gmail_forwarder_web.gam_client import initialize_gam

    initialize_gam(reuse_existing_credentials=True)

    commands = [call[1:] for call in fake.commands]
    assert ["create", "project"] not in commands
    assert ["oauth", "create"] not in commands
    setup_config = fake.commands[0]
    assert setup_config[setup_config.index("config_dir") + 1] == str(credentials_dir)
    assert setup_config[setup_config.index("client_secrets_json") + 1] == str(
        credentials_dir / "client_secrets.json"
    )
    assert ["print", "groups", "showitemcountonly"] in [call[4:] for call in fake.commands if call[1:3] == ["redirect", "stdout"]]


def test_reuse_existing_credentials_requires_both_files(monkeypatch, tmp_path):
    fake = FakeGamModule()
    monkeypatch.setitem(sys.modules, "gam", fake)
    monkeypatch.setenv("GAMCFGDIR", str(tmp_path))
    credentials_dir = tmp_path / "credentials"
    credentials_dir.mkdir()
    monkeypatch.setenv("GAMUSERCONFIGDIR", str(credentials_dir))
    monkeypatch.setenv("GAM_WORK_DIR", str(tmp_path / "work"))

    from gmail_forwarder_web.gam_client import initialize_gam

    with pytest.raises(RuntimeError, match="Cannot reuse GAM credentials"):
        initialize_gam(reuse_existing_credentials=True)


def test_reuse_existing_credentials_reports_failed_group_check(monkeypatch, tmp_path):
    fake = FakeGamModule(fail_on_call=2)
    monkeypatch.setitem(sys.modules, "gam", fake)
    monkeypatch.setenv("GAMCFGDIR", str(tmp_path))
    credentials_dir = tmp_path / "credentials"
    credentials_dir.mkdir()
    monkeypatch.setenv("GAMUSERCONFIGDIR", str(credentials_dir))
    monkeypatch.setenv("GAM_WORK_DIR", str(tmp_path / "work"))
    (credentials_dir / "client_secrets.json").write_text("{}", encoding="utf-8")
    (credentials_dir / "oauth2.txt").write_text("{}", encoding="utf-8")

    from gmail_forwarder_web.gam_client import initialize_gam

    with pytest.raises(RuntimeError, match="could not list Workspace groups"):
        initialize_gam(reuse_existing_credentials=True)