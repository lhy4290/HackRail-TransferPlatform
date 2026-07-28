def test_health_check(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_metrics_endpoint_returns_defaults_when_no_logs(client):
    resp = client.get("/api/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_calls_last_7_days"] == 0
    assert body["error_rate"] == 0.0


def test_alerts_endpoint_empty_when_no_adapters(client):
    resp = client.get("/api/alerts")
    assert resp.status_code == 200
    assert resp.json() == []


def test_transfer_info_endpoint(client):
    resp = client.get("/api/transfers/T1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_transfer_time_minutes"] == 15  # walking 5 + buffer 10
    assert body["message"] is None


def test_transfer_info_not_found(client):
    resp = client.get("/api/transfers/UNKNOWN")
    assert resp.status_code == 404


def test_liveboard_endpoint_no_adapter_returns_empty_fallback(client):
    resp = client.get("/api/liveboard/ORIGIN")
    assert resp.status_code == 200
    body = resp.json()
    assert body["entries"] == []
    assert body["is_realtime"] is False


def test_liveboard_endpoint_unknown_station(client):
    resp = client.get("/api/liveboard/NOT_A_STATION")
    assert resp.status_code == 404
