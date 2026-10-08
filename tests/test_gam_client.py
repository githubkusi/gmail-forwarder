import sys
from pathlib import Path
import pytest

from gmail_forwarder_web.gam_client import GamClient, GamOperationError


class FakeGamModule:
    def __init__(self, *, fail_on_call=None):
        self.commands = []
        self.fail_on_call = fail_on_call

    def CallGAMCommand(self, args):
        self.commands.append(args)
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