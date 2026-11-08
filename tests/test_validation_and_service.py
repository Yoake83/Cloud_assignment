import json

import app as service_app
import pytest
import validation
from fastapi.testclient import TestClient


def test_validate_accepts_good_output_and_orders_keys():
    obj = validation.validate_output('{"place": "london", "time": null, "date": null, "intent": "weather_query"}')
    assert list(obj) == ["intent", "date", "time", "place"]


@pytest.mark.parametrize("bad", [
    "not json", "[]", '{"intent": "weather_query"}',
    '{"intent": "dance", "date": null, "time": null, "place": null}',
    '{"intent": "alarm_set", "date": 5, "time": null, "place": null}',
    '{"intent": "alarm_set", "date": null, "time": null, "place": null, "extra": 1}',
    '{"intent": "alarm_set", "date": null, "time": null, "place": null} trailing',
])
def test_validate_rejects_bad_output(bad):
    assert validation.validate_output(bad) is None


class StubModel:
    def generate(self, text, max_new_tokens):
        return json.dumps({"intent": "weather_query", "date": None, "time": None, "place": "london"})


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("MODEL_VERSION", "v-test")
    monkeypatch.setenv("POD_NAME", "pod-abc")
    monkeypatch.setattr(service_app, "load_model", lambda: StubModel())
    monkeypatch.setattr(service_app.state, "ready", False)
    monkeypatch.setattr(service_app.state, "model", None)
    with TestClient(service_app.app) as c:
        yield c


def wait_ready(client):
    import time
    for _ in range(100):
        if client.get("/readyz").status_code == 200:
            return
        time.sleep(0.05)
    raise AssertionError("never became ready")


def test_health_and_ready(client):
    assert client.get("/healthz").status_code == 200
    wait_ready(client)


def test_parse_success_body_and_headers(client):
    wait_ready(client)
    r = client.post("/parse", json={"text": "what is the weather in london"})
    assert r.status_code == 200
    assert r.json() == {"intent": "weather_query", "date": None, "time": None, "place": "london"}
    assert r.headers["X-Model-Version"] == "v-test" and r.headers["X-Served-By"] == "pod-abc"


def test_fault_injection_returns_500_with_exact_body(client, monkeypatch):
    wait_ready(client)
    monkeypatch.setenv("FAULT_INJECT", "1")
    r = client.post("/parse", json={"text": "anything"})
    assert r.status_code == 500 and r.json() == {"error": "invalid_model_output"}


def test_not_ready_gives_503(monkeypatch):
    monkeypatch.setattr(service_app.state, "ready", False)
    monkeypatch.setattr(service_app, "_load_in_background", lambda: None)
    with TestClient(service_app.app) as c:
        assert c.get("/readyz").status_code == 503
        assert c.get("/healthz").status_code == 200
