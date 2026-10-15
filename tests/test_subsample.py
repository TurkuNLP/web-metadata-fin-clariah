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
    n = webmeta.export(s, tmp_path / "out", name="{id}_{main}",
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
                  'EXPORT = {"name": "{id}_{lang}", "columns": ("id", "lang")}\n')
    assert main(["build", str(fx), "--settings", str(st), "-o", str(tmp_path / "o")]) == 0
    assert main(["build", str(fx), "--settings", str(st), "-o", str(tmp_path / "c"),
                 "--counts-only"]) == 0
    lines = (tmp_path / "c" / "cells.tsv").read_text().splitlines()
    assert lines[0] == "lang\tpopulation\ttaken" and len(lines) > 1
