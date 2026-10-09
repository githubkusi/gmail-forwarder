import pytest
from fastapi.testclient import TestClient

from gmail_forwarder_web.config import Settings, normalize_forwarder
from gmail_forwarder_web.gam_client import GamOperationError
from gmail_forwarder_web.web import create_app


class FakeGam:
    def __init__(self):
        self.created = []
        self.groups = "billing@example.org\nreports@another.test\nbilling-archive@another.test"
        self.failure = None

    def setup(self):
        pass

    def add_forwarder(self, address, owner):
        if self.failure:
            raise self.failure
        self.created.append((address, owner))
        return "created and owner assigned"

    def print_groups(self):
        return self.groups


def configured_app(gateway=None):
    settings = Settings(("admin@example.org", "reports@another.test"))
    return create_app(settings=settings, gateway=gateway or FakeGam())


def test_normalize_local_name_with_recipient_domain():
    assert normalize_forwarder("invoices", "example.org") == "invoices@example.org"
    assert normalize_forwarder("Ops.Team", "another.test") == "Ops.Team@another.test"


def test_rejects_full_address_and_invalid_local_part():
    with pytest.raises(ValueError, match="without @"):
        normalize_forwarder("team@example.org", "example.org")
    with pytest.raises(ValueError):
        normalize_forwarder("bad..name", "example.org")


def test_settings_parse_and_validate_recipients(monkeypatch):
    monkeypatch.setenv("EMAIL_RECIPIENTS", " first@example.org  second@another.test ")
    settings = Settings.from_env()
    settings.validate()
    assert settings.recipients == ("first@example.org", "second@another.test")
    assert settings.domain_for_recipient("SECOND@ANOTHER.TEST") == "another.test"


@pytest.mark.parametrize(
    "recipients",
    ["", "not-an-email", "one@example.org ONE@example.org", "bad@-example.org"],
)
def test_settings_reject_missing_invalid_or_duplicate_recipients(monkeypatch, recipients):
    monkeypatch.setenv("EMAIL_RECIPIENTS", recipients)
    with pytest.raises(ValueError):
        Settings.from_env().validate()


def test_unknown_recipient_is_rejected():
    with pytest.raises(ValueError, match="configured email recipients"):
        Settings(("admin@example.org",)).domain_for_recipient("intruder@elsewhere.test")


def test_create_derives_domain_and_uses_selected_recipient_as_owner():
    gateway = FakeGam()
    with TestClient(configured_app(gateway)) as client:
        response = client.post(
            "/create", data={"name": "billing", "recipient": "reports@another.test"}
        )
    assert response.status_code == 200
    assert "billing@another.test" in response.text
    assert gateway.created == [("billing@another.test", "reports@another.test")]


def test_create_rejects_full_address_as_forwarder_name():
    with TestClient(configured_app()) as client:
        response = client.post(
            "/create", data={"name": "team@another.test", "recipient": "admin@example.org"}
        )
    assert "without @" in response.text


def test_create_rejects_unconfigured_recipient_and_preserves_valid_selection():
    with TestClient(configured_app()) as client:
        response = client.post(
            "/create", data={"name": "billing", "recipient": "fake@elsewhere.test"}
        )
    assert "Choose one of the configured email recipients" in response.text
    assert 'value="admin@example.org" selected' in response.text


def test_create_page_shows_email_recipient_selector():
    with TestClient(configured_app()) as client:
        response = client.get("/")
    assert "Email recipient" in response.text
    assert "Forwarder domain" not in response.text
    assert "admin@example.org" in response.text
    assert "reports@another.test" in response.text
    assert "@example.org" in response.text


def test_static_assets_use_relative_paths_and_are_served():
    with TestClient(configured_app()) as client:
        response = client.get("/")
        css = client.get("/static/style.css")
        javascript = client.get("/static/app.js")

    assert 'href="static/style.css"' in response.text
    assert 'src="static/app.js"' in response.text
    assert css.status_code == 200
    assert "--canvas" in css.text
    assert javascript.status_code == 200


def test_search_matches_all_domains_and_deduplicates():
    gateway = FakeGam()
    gateway.groups += "\nBILLING@EXAMPLE.ORG"
    with TestClient(configured_app(gateway)) as client:
        response = client.post("/search", data={"query": "billing"})
    assert response.status_code == 200
    assert "billing@example.org" in response.text
    assert "billing-archive@another.test" in response.text
    assert response.text.count("data-copy=") == 2


def test_search_empty_state():
    with TestClient(configured_app()) as client:
        response = client.post("/search", data={"query": "no-such-name"})
    assert "No matching forwarders found." in response.text


def test_gam_errors_are_reported():
    gateway = FakeGam()
    gateway.failure = GamOperationError("create", "GAM create failed")
    with TestClient(configured_app(gateway)) as client:
        response = client.post(
            "/create", data={"name": "new", "recipient": "admin@example.org"}
        )
    assert response.status_code == 502
    assert "GAM create failed" in response.text


def test_partial_gam_failure_explains_created_group():
    gateway = FakeGam()
    gateway.failure = GamOperationError(
        "assign_owner", "The group exists, but owner assignment failed", partial=True
    )
    with TestClient(configured_app(gateway)) as client:
        response = client.post(
            "/create", data={"name": "new", "recipient": "admin@example.org"}
        )
    assert response.status_code == 502
    assert "group exists" in response.text


def test_health_endpoint_does_not_require_google_call():
    with TestClient(configured_app()) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    assert response.text == "ok"