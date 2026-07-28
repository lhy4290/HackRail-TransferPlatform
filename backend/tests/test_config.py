from app.config import load_tdx_credentials


def test_load_tdx_credentials_returns_none_when_missing(monkeypatch):
    monkeypatch.delenv("TDX_CLIENT_ID", raising=False)
    monkeypatch.delenv("TDX_CLIENT_SECRET", raising=False)

    assert load_tdx_credentials() is None


def test_load_tdx_credentials_reads_env_vars(monkeypatch):
    monkeypatch.setenv("TDX_CLIENT_ID", "abc")
    monkeypatch.setenv("TDX_CLIENT_SECRET", "secret")

    credentials = load_tdx_credentials()

    assert credentials is not None
    assert credentials.client_id == "abc"
    assert credentials.client_secret == "secret"
