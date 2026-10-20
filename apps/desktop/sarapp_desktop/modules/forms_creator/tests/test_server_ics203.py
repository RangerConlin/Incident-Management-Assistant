from pathlib import Path

import httpx
import pytest

from modules.forms_creator.exporting.models import PreparedExport
from modules.forms_creator.exporting.registry import ExportRegistry
from modules.forms_creator.exporting.service import ExportService
from modules.forms_creator.exporting.server import download_ics203
from utils.api_client import APIError, _APIClient, api_client


@pytest.mark.parametrize("status,media,content", [
    (200, "text/html", b"<html>Login</html>"),
    (200, "application/pdf", b"broken"),
    (503, "application/json", b'{"detail":"PDF unavailable"}'),
])
def test_pdf_download_rejects_errors_and_non_pdf(monkeypatch, status, media, content):
    client = _APIClient.__new__(_APIClient)
    client._base_url = "https://example.invalid/r/CONNECT"
    monkeypatch.setattr(client, "_request_with_retry", lambda *a, **k: httpx.Response(
        status, headers={"content-type": media}, content=content
    ))
    with pytest.raises(APIError):
        client.post_pdf("/api/incidents/TEST/form-exports", json={})


def test_download_uses_active_tunnel_path_and_saves_pdf(monkeypatch, tmp_path):
    calls = []
    client = _APIClient.__new__(_APIClient)
    client._base_url = "https://example.invalid/r/CONNECT"
    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF-test")
    monkeypatch.setattr(client, "_request_with_retry", request)
    monkeypatch.setattr(api_client, "post_pdf", client.post_pdf)
    output = tmp_path / "203.pdf"
    assert download_ics203("TEST 203", 7, output) == output
    assert output.read_bytes() == b"%PDF-test"
    assert calls[0][1] == "https://example.invalid/r/CONNECT/api/incidents/TEST%20203/form-exports"
    assert calls[0][2]["json"]["operational_period_id"] == 7


def test_failure_preserves_existing_file(monkeypatch, tmp_path):
    output = tmp_path / "203.pdf"
    output.write_bytes(b"existing")
    def fail(*args, **kwargs): raise APIError("Server unavailable")
    monkeypatch.setattr(api_client, "post_pdf", fail)
    with pytest.raises(APIError):
        download_ics203("TEST", 7, output)
    assert output.read_bytes() == b"existing"


def test_central_service_uses_server_and_rejects_unsupported_set(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr("modules.forms_creator.exporting.server.download_ics203",
                        lambda *a, **k: calls.append((a, k)))
    service = ExportService(ExportRegistry(), generator=lambda *a, **k: pytest.fail("Local renderer called"))
    prepared = PreparedExport("ics_203", tmp_path / "203.pdf", "TEST", "fema",
                              metadata={"operational_period_id": 7})
    service._generate(prepared)
    assert calls[0][0][:2] == ("TEST", 7)
    with pytest.raises(ValueError, match="Unsupported"):
        service._generate(PreparedExport("ics_203", Path("203.pdf"), "TEST", "unknown"))
    with pytest.raises(ValueError, match="operational period"):
        service._generate(PreparedExport("ics_203", Path("203.pdf"), "TEST"))
