import datetime as dt
import json

import pytest

import webmeta
import webmeta.geo as geo


def test_snapshot_places_countries():
    fi = geo.lookup("fi")
    assert fi["name"] == "Finland" and fi["region"] == "Europe" and fi["subregion"] == "Northern Europe"
    assert fi["languages"]["fin"] > 0.9 and -180 <= fi["lon"] <= 180
    assert geo.lookup("GF")["subregion"] == "South America"      # not folded into France
    assert geo.lookup(None) is None and geo.lookup("XX") is None
    from webmeta.country import ISO_ALPHA2
    assert ISO_ALPHA2 <= set(geo.table()["countries"])


def _table(days_old, name="Finland"):
    built = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_old)
    return {"built": built.isoformat(timespec="seconds"), "sources": {},
            "countries": {"FI": {"name": name, "region": "Europe", "subregion": "Northern Europe",
                                 "lon": 0, "lat": 0, "languages": {}}}}


def _use_cache(monkeypatch, tmp_path, table):
    monkeypatch.delenv("WEBMETA_GEO_TABLE")
    d = tmp_path / "cache"
    d.mkdir(exist_ok=True)
    if table is not None:
        (d / geo.TABLE_NAME).write_text(json.dumps(table))
    return d


def test_fresh_cache_is_used_without_rebuilding(monkeypatch, tmp_path):
    _use_cache(monkeypatch, tmp_path, _table(10, "cached"))
    monkeypatch.setattr(geo, "build", lambda: pytest.fail("should not rebuild"))
    assert geo.lookup("FI")["name"] == "cached" and geo.table_info()["loaded_from"]["how"] == "cache"


def test_old_cache_is_rebuilt(monkeypatch, tmp_path):
    d = _use_cache(monkeypatch, tmp_path, _table(geo.MAX_AGE_DAYS + 1, "old"))
    monkeypatch.setattr(geo, "build", lambda: _table(0, "new"))
    assert geo.lookup("FI")["name"] == "new" and geo.table_info()["loaded_from"]["how"] == "rebuilt"
    assert json.loads((d / geo.TABLE_NAME).read_text())["countries"]["FI"]["name"] == "new"


def test_failed_rebuild_falls_back(monkeypatch, tmp_path):
    _use_cache(monkeypatch, tmp_path, _table(geo.MAX_AGE_DAYS + 1, "old"))
    def fail():
        raise OSError("offline")
    monkeypatch.setattr(geo, "build", fail)
    with pytest.warns(UserWarning):
        assert geo.lookup("FI")["name"] == "old"
    assert geo.table_info()["loaded_from"]["how"] == "stale cache"


def test_no_cache_and_no_rebuild_uses_snapshot(monkeypatch, tmp_path):
    _use_cache(monkeypatch, tmp_path, None)
    monkeypatch.setattr(geo, "build", lambda: (_ for _ in ()).throw(ImportError("no geopandas")))
    with pytest.warns(UserWarning):
        assert geo.lookup("FI")["name"] == "Finland"
    assert geo.table_info()["loaded_from"]["how"] == "snapshot"


def test_region_filters_and_meta():
    recs = [{"id": "1", "text": "a", "url": "https://yle.fi/x"},
            {"id": "2", "text": "b", "url": "https://www.lemonde.fr/y"},
            {"id": "3", "text": "c", "url": "https://example.com/z"}]
    out = list(webmeta.run(recs, region="Europe", subregion="northern europe"))
    assert [r["id"] for r in out] == ["1"]
    m = out[0]["meta"]
    assert (m["country"], m["country_name"], m["region"]) == ("FI", "Finland", "Europe")
    assert [r["id"] for r in webmeta.run(recs, region=["Europe"])] == ["1", "2"]


def test_export_records_the_table(tmp_path):
    s = webmeta.stratify([{"id": "1", "text": "a", "meta": {}}], n=1)
    webmeta.export(s, tmp_path / "o")
    rec = json.loads((tmp_path / "o" / "webmeta.json").read_text())
    assert rec["country_table"]["built"] and rec["country_table"]["loaded_from"]["how"] == "pinned"


def test_cli_geo(capsys):
    from webmeta.cli import main
    assert main(["geo"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["countries"] >= 249 and info["loaded_from"]["how"] == "pinned"
    assert main(["geo", "--country", "se"]) == 0
    assert json.loads(capsys.readouterr().out)["name"] == "Sweden"
