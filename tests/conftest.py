import pytest

import webmeta.geo as geo


@pytest.fixture(autouse=True)
def _country_table(monkeypatch, tmp_path):
    """Tests use the shipped snapshot and never touch the network or the real cache."""
    monkeypatch.setenv("WEBMETA_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("WEBMETA_GEO_TABLE", str(geo.SNAPSHOT))
    monkeypatch.setattr(geo, "_TABLE", None)
