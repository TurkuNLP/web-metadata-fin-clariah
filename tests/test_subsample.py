import random

import webmeta
from webmeta.subsample import rank


def docs(n=600):
    """Synthetic annotated records: two languages x three levels."""
    rnd = random.Random(0)
    return [{"id": f"d{i}", "text": "w " * rnd.randint(1, 900),
             "meta": {"lang": "fin" if i % 2 else "swe", "level": 5 + i % 3}}
            for i in range(n)]


def test_equal_allocation_and_population():
    s = webmeta.stratify(docs(), strata=("lang", "level"), n=40, seed=1)
    assert len(s.population) == 6 and sum(s.population.values()) == 600
    assert all(len(v) == 40 for v in s.cells.values())
    rows = list(s.table())
    assert rows[0].keys() == {"lang", "level", "population", "taken"}


def test_small_cells_keep_what_they_have():
    s = webmeta.stratify(docs(30), strata=("lang", "level"), n=40, seed=1)
    assert len(s) == 30


def test_selection_ignores_input_order_and_nests():
    a = webmeta.stratify(docs(), strata=("lang",), n=50, seed=7)
    shuffled = docs()
    random.Random(3).shuffle(shuffled)
    b = webmeta.stratify(shuffled, strata=("lang",), n=50, seed=7)
    assert [r["id"] for r in a.records()] == [r["id"] for r in b.records()]
    small = webmeta.stratify(docs(), strata=("lang",), n=20, seed=7)
    for c in small.cells:
        assert {r["id"] for r in small.cells[c]} <= {r["id"] for r in a.cells[c]}


def test_seed_changes_selection():
    a = webmeta.stratify(docs(), n=50, seed=1)
    b = webmeta.stratify(docs(), n=50, seed=2)
    assert {r["id"] for r in a.records()} != {r["id"] for r in b.records()}
    assert rank("x", 1) == rank("x", 1) != rank("x", 2)


def test_counts_only():
    s = webmeta.stratify(docs(), strata=("level",), n=0)
    assert len(s) == 0 and sum(s.population.values()) == 600


def test_build_settings_on_hplt4(tmp_path):
    from pathlib import Path
    fx = Path(__file__).parent / "fixtures" / "hplt4_like.jsonl"
    settings = {
        "adapter": "hplt4",
        "fields": {"main": lambda r: (r["meta"]["registers"] or [None])[0]},
        "keep": [lambda r: r["meta"]["main"] is not None],
        "strata": ("lang", "main"), "n": 1, "seed": 0,
    }
    s = webmeta.build(webmeta.read(fx), settings)
    assert len(s) == len(s.cells) > 0
    n = webmeta.export(s, tmp_path / "out", format="txt", name="{id}_{main}",
                       columns=("id", "lang", "main", "register"))
    assert n == len(s)
    header = (tmp_path / "out" / "documents.tsv").read_text().splitlines()[0].split("\t")
    assert "register.NA" in header and header[-1] == "file"
    assert (tmp_path / "out" / "cells.tsv").exists()
    assert len(list((tmp_path / "out").glob("*.txt"))) == n


def test_cli_build(tmp_path):
    from pathlib import Path
    from webmeta.cli import main
    fx = Path(__file__).parent / "fixtures" / "hplt4_like.jsonl"
    st = tmp_path / "study.py"
    st.write_text('SETTINGS = {"adapter": "hplt4", "strata": ("lang",), "n": 1}\n'
                  'EXPORT = {"format": "txt", "name": "{id}_{lang}", "columns": ("id", "lang")}\n')
    assert main(["build", str(fx), "--settings", str(st), "-o", str(tmp_path / "o")]) == 0
    assert main(["build", str(fx), "--settings", str(st), "-o", str(tmp_path / "c"),
                 "--counts-only"]) == 0
    lines = (tmp_path / "c" / "cells.tsv").read_text().splitlines()
    assert lines[0] == "lang\tpopulation\ttaken" and len(lines) > 1


def test_export_into_subdirectories(tmp_path):
    s = webmeta.stratify(docs(60), strata=("lang", "level"), n=2, seed=0)
    n = webmeta.export(s, tmp_path / "o", format="txt", name="{id}", dirs="{level}/{lang}",
                       columns=("id", "lang", "level"))
    files = sorted(p.relative_to(tmp_path / "o").as_posix() for p in (tmp_path / "o").rglob("*.txt"))
    assert len(files) == n == 12 and all(f.count("/") == 2 for f in files)
    rows = (tmp_path / "o" / "documents.tsv").read_text().splitlines()[1:]
    assert sorted(r.split("\t")[-1] for r in rows) == files


def test_export_jsonl_is_the_default_and_keeps_meta(tmp_path):
    import json
    s = webmeta.stratify(docs(60), strata=("lang",), n=5, seed=0)
    n = webmeta.export(s, tmp_path / "o")
    lines = (tmp_path / "o" / "documents.jsonl").read_text().splitlines()
    assert n == len(lines) == 10
    rec = json.loads(lines[0])
    assert rec["meta"]["lang"] in ("fin", "swe") and "text" in rec
    assert (tmp_path / "o" / "cells.tsv").exists() and not (tmp_path / "o" / "documents.tsv").exists()
    webmeta.export(s, tmp_path / "f", fields=("id",))
    assert set(json.loads((tmp_path / "f" / "documents.jsonl").read_text().splitlines()[0])) == {"id", "meta"}


def test_export_jsonl_one_file_per_folder(tmp_path):
    s = webmeta.stratify(docs(60), strata=("lang", "level"), n=2, seed=0)
    webmeta.export(s, tmp_path / "o", dirs="{lang}")
    files = sorted(p.relative_to(tmp_path / "o").as_posix() for p in (tmp_path / "o").rglob("*.jsonl"))
    assert files == ["fin/documents.jsonl", "swe/documents.jsonl"]


def test_export_csv_and_parquet(tmp_path):
    import csv
    import pytest
    s = webmeta.stratify(docs(60), strata=("lang",), n=3, seed=0)
    webmeta.export(s, tmp_path / "c", format="csv", columns=("id", "lang"))
    rows = list(csv.DictReader(open(tmp_path / "c" / "documents.csv")))
    assert len(rows) == 6 and list(rows[0]) == ["id", "lang", "text"]
    pd = pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    webmeta.export(s, tmp_path / "p", format="parquet", columns=("id", "lang"))
    assert len(pd.read_parquet(tmp_path / "p" / "documents.parquet")) == 6


def test_export_rejects_unknown_format(tmp_path):
    import pytest
    s = webmeta.stratify(docs(10), n=1)
    with pytest.raises(ValueError):
        webmeta.export(s, tmp_path / "o", format="docx")


def test_example_settings_run(tmp_path):
    from pathlib import Path
    from webmeta.cli import main
    root = Path(__file__).parent.parent
    assert main(["build", str(root / "tests" / "fixtures" / "hplt4_like.jsonl"),
                 "--settings", str(root / "examples" / "news_and_blogs.py"),
                 "-o", str(tmp_path / "o")]) == 0
    assert (tmp_path / "o" / "cells.tsv").exists()
