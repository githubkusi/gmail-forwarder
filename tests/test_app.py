import pytest
from fastapi.testclient import TestClient

from gmail_forwarder_web.config import Settings, normalize_forwarder
from gmail_forwarder_web.gam_client import GamOperationError
from gmail_forwarder_web.web import create_app


class FakeGam:
    def __init__(self):
        self.created = []
        self.groups = "billing@titlis.org\nreports@lsass.ch\nbilling-archive@lsass.ch"
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
    settings = Settings("admin@titlis.org", "admin@lsass.ch")
    return create_app(settings=settings, gateway=gateway or FakeGam())


def test_normalize_local_and_full_address():
    assert normalize_forwarder("invoices", "titlis.org") == "invoices@titlis.org"
    assert normalize_forwarder("Ops.Team@LSASS.CH", "lsass.ch") == "Ops.Team@lsass.ch"


def test_rejects_mismatched_domain_and_invalid_local_part():
    with pytest.raises(ValueError, match="selected domain"):
        normalize_forwarder("team@lsass.ch", "titlis.org")
    with pytest.raises(ValueError):
        normalize_forwarder("bad..name", "titlis.org")


def test_settings_require_valid_domain_mailboxes():
    with pytest.raises(ValueError, match="must use the titlis.org domain"):
        Settings("admin@example.com", "admin@lsass.ch").validate()


def test_create_uses_owner_for_selected_domain():
    gateway = FakeGam()
    with TestClient(configured_app(gateway)) as client:
        response = client.post("/create", data={"name": "billing", "domain": "lsass.ch"})
    assert response.status_code == 200
    assert "billing@lsass.ch" in response.text
    assert gateway.created == [("billing@lsass.ch", "admin@lsass.ch")]


def test_create_rejects_full_address_from_other_domain():
    with TestClient(configured_app()) as client:
        response = client.post("/create", data={"name": "team@lsass.ch", "domain": "titlis.org"})
    assert "must use the selected domain" in response.text


def test_search_matches_all_domains_and_deduplicates():
    gateway = FakeGam()
    gateway.groups += "\nBILLING@TITLIS.ORG"
    with TestClient(configured_app(gateway)) as client:
        response = client.post("/search", data={"query": "billing"})
    assert response.status_code == 200
    assert "billing@titlis.org" in response.text
    assert "billing-archive@lsass.ch" in response.text
    assert response.text.count("data-copy=") == 2


def test_search_empty_state():
    with TestClient(configured_app()) as client:
        response = client.post("/search", data={"query": "no-such-name"})
    assert "No matching forwarders found." in response.text


def test_gam_errors_are_reported():
    gateway = FakeGam()
    gateway.failure = GamOperationError("create", "GAM create failed")
    with TestClient(configured_app(gateway)) as client:
        response = client.post("/create", data={"name": "new", "domain": "titlis.org"})
    assert response.status_code == 502
    assert "GAM create failed" in response.text


def test_partial_gam_failure_explains_created_group():
    gateway = FakeGam()
    gateway.failure = GamOperationError(
        "assign_owner", "The group exists, but owner assignment failed", partial=True
    )
    with TestClient(configured_app(gateway)) as client:
        response = client.post("/create", data={"name": "new", "domain": "titlis.org"})
    assert response.status_code == 502
    assert "group exists" in response.text


def test_health_endpoint_does_not_require_google_call():
    with TestClient(configured_app()) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    assert response.text == "ok"