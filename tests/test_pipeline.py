from pathlib import Path

import pytest

import webmeta

FX = Path(__file__).parent / "fixtures"


def hplt():
    return list(webmeta.read(FX / "hplt4_like.jsonl"))


def ids(recs):
    return [r["id"] for r in recs]


def test_swedish_from_finland():
    assert ids(webmeta.run(hplt(), adapter="hplt4", lang="sv", country="FI")) == ["fx-2"]


def test_register_filter_and_exclusion():
    assert ids(webmeta.run(hplt(), adapter="hplt4", register="NA")) == ["fx-1", "fx-2"]
    assert "fx-6" in ids(webmeta.run(hplt(), adapter="hplt4"))
    assert "fx-6" not in ids(webmeta.run(hplt(), adapter="hplt4", exclude=("MT",)))


def test_multilingual_targeting():
    assert ids(webmeta.run(hplt(), adapter="hplt4", multilingual=True)) == ["fx-4"]
    found = webmeta.run(hplt(), adapter="hplt4", lang="fin", any_segment=True)
    assert ids(found) == ["fx-1", "fx-4"]


def test_meta_is_added_not_overwriting():
    rec = next(webmeta.run(hplt(), adapter="hplt4"))
    assert rec["url"].startswith("https://") and rec["meta"]["country"] == "FI"


def test_own_corpus_via_mapping():
    pytest.importorskip("pandas")
    mapping = {"id": "doc_id", "text": "body", "url": "link", "lang": "language"}
    adapt = lambda r: webmeta.from_mapping(r, mapping)
    recs = [adapt(r) for r in webmeta.read(FX / "own_corpus.csv")]
    cov = webmeta.coverage(recs)
    assert cov == {"records": 3, "language": 3, "country": 2, "register": 3}
    out = webmeta.run(recs, lang="fi", register="OP")
    assert ids(out) == ["own-2"]


def test_strict_mode_reports_missing_fields():
    recs = [{"id": "x", "text": "no url"}]
    with pytest.raises(webmeta.ContractError):
        list(webmeta.run(recs, country="FI", strict=True))
    assert list(webmeta.run(recs, country="FI")) == []


def test_zst_roundtrip(tmp_path):
    zstd = pytest.importorskip("zstandard")
    src = (FX / "hplt4_like.jsonl").read_bytes()
    p = tmp_path / "shard.jsonl.zst"
    p.write_bytes(zstd.ZstdCompressor().compress(src))
    assert len(list(webmeta.read(p))) == 6


def test_parquet_of_hplt4_records(tmp_path):
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq
    path = tmp_path / "hplt.parquet"
    pq.write_table(pa.Table.from_pylist(hplt()), path)
    got = [r["meta"] for r in webmeta.run(webmeta.read(path), adapter="hplt4")]
    assert got == [r["meta"] for r in webmeta.run(hplt(), adapter="hplt4")]


def test_cli(tmp_path):
    from webmeta.cli import main
    out = tmp_path / "out.jsonl"
    main(["run", str(FX / "hplt4_like.jsonl"), "-o", str(out), "--lang", "swe"])
    assert len(out.read_text().splitlines()) == 2


def test_cli_count(tmp_path):
    from webmeta.cli import main
    out = tmp_path / "counts.tsv"
    main(["count", str(FX / "hplt4_like.jsonl"), "--by", "lang,registers", "-o", str(out)])
    rows = out.read_text().splitlines()
    assert rows[0] == "lang\tregisters\tn"
    assert "swe\tre\t1" in rows
