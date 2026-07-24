from modules.intel.weather.services import runway_api


class _FakeResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, response: _FakeResponse):
        self._response = response
        self.last_params = None

    def get(self, url, params=None):
        self.last_params = params
        return self._response


def test_fetch_runways_derives_reciprocal_end_from_single_alignment(monkeypatch):
    payload = [
        {
            "icaoId": "KDEN",
            "runways": [
                {"id": "08/26", "alignment": "080", "dimension": "12000x150"},
            ],
        }
    ]
    fake_client = _FakeClient(_FakeResponse(200, payload))
    monkeypatch.setattr(runway_api, "get_shared_client", lambda: fake_client)

    ends = runway_api.fetch_runways("KDEN")
    assert len(ends) == 2
    by_designator = {e.designator: e for e in ends}
    assert abs(by_designator["08"].heading_true_deg - 80) < 0.01
    assert abs(by_designator["26"].heading_true_deg - 260) < 0.01
    assert by_designator["08"].length_ft == 12000.0


def test_fetch_runways_empty_icao_returns_empty_list_without_a_call(monkeypatch):
    calls = []
    monkeypatch.setattr(runway_api, "get_shared_client", lambda: calls.append("called"))
    assert runway_api.fetch_runways("") == []
    assert calls == []


def test_fetch_runways_http_error_returns_empty_not_a_guess(monkeypatch):
    fake_client = _FakeClient(_FakeResponse(404, {}))
    monkeypatch.setattr(runway_api, "get_shared_client", lambda: fake_client)
    assert runway_api.fetch_runways("KUNKNOWN") == []


def test_fetch_runways_network_exception_returns_empty_not_a_guess(monkeypatch):
    class _RaisingClient:
        def get(self, *args, **kwargs):
            raise ConnectionError("simulated network failure")

    monkeypatch.setattr(runway_api, "get_shared_client", lambda: _RaisingClient())
    assert runway_api.fetch_runways("KDEN") == []


def test_fetch_runways_malformed_runway_entry_is_skipped_not_fatal(monkeypatch):
    payload = [
        {
            "icaoId": "KDEN",
            "runways": [
                {"id": "08/26", "alignment": "not-a-number"},
                {"id": "17/35", "alignment": "170", "dimension": "9000x120"},
            ],
        }
    ]
    fake_client = _FakeClient(_FakeResponse(200, payload))
    monkeypatch.setattr(runway_api, "get_shared_client", lambda: fake_client)

    ends = runway_api.fetch_runways("KDEN")
    designators = {e.designator for e in ends}
    assert designators == {"17", "35"}
