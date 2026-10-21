"""Subsampling: turn annotated records into a research dataset, by settings.

A study is a set of settings, not code in this package:

    fields  {name: function(record) -> value}: derived values, stored in ``meta``
            in the order given, so a later field can use an earlier one
    keep    functions record -> bool; a record must pass all of them
    strata  meta (or record) fields whose value combinations are the cells,
            e.g. ("category", "level"); () = one cell, a simple random sample
    n       documents per cell (equal allocation); None = every document,
            0 = none (only count the cells)
    seed    selection seed

    >>> s = webmeta.build(webmeta.read("sample.jsonl.zst"), {
    ...     "adapter": "hplt4",
    ...     "fields": {"words": lambda r: len(r["text"].split())},
    ...     "keep": [lambda r: r["meta"]["words"] >= 500],
    ...     "strata": ("lang", "hybrid"), "n": 100, "seed": 1})
    >>> s.population, s.cells

Selection is reproducible and independent of input order: each record gets a
pseudo-random rank from (seed, id), and each cell keeps its n lowest-ranked
records. The same settings give the same dataset however the input is ordered
or split, and a smaller n gives a subset of a larger one.
"""

import csv
import hashlib
import heapq
import json
from collections import Counter
from pathlib import Path

from . import pipeline


def rank(record_id, seed=0):
    """A record's pseudo-random rank: a 64-bit integer from (seed, id)."""
    h = hashlib.blake2b(f"{seed}:{record_id}".encode("utf-8"), digest_size=8)
    return int.from_bytes(h.digest(), "big")


def value(record, field):
    """A field from ``meta`` if derived there, else from the record itself."""
    meta = record.get("meta") or {}
    return meta[field] if field in meta else record.get(field)


def derive(records, fields):
    """Add derived values to each record's ``meta``; source fields are untouched."""
    for r in records:
        meta = dict(r.get("meta") or {})
        out = {**r, "meta": meta}
        for name, fn in (fields or {}).items():
            meta[name] = fn(out)
        yield out


def keep(records, tests):
    """Records that pass every test."""
    tests = list(tests or ())
    for r in records:
        if all(t(r) for t in tests):
            yield r


class Sample:
    """The result of ``stratify``: the chosen records per cell, and every cell's size.

    strata      the fields that define the cells
    cells       {cell: [records]}, each list ordered by rank
    population  {cell: number of documents seen in that cell}
    """

    def __init__(self, strata, cells, population, n, seed):
        self.strata, self.cells, self.population = tuple(strata), cells, population
        self.n, self.seed = n, seed

    def records(self):
        for c in sorted(self.cells, key=_sort_key):
            yield from self.cells[c]

    def table(self):
        """One row per cell: its values, population and how many were taken."""
        for c in sorted(self.population, key=_sort_key):
            row = dict(zip(self.strata, c))
            row.update(population=self.population[c], taken=len(self.cells.get(c, ())))
            yield row

    def __len__(self):
        return sum(len(v) for v in self.cells.values())


def stratify(records, strata=(), n=None, seed=0, id_field="id"):
    """Equal allocation: up to ``n`` records per cell, chosen by rank; returns a Sample.

    A record without an id is ranked by its text instead. A list-valued stratum
    (e.g. ``registers``) is joined into one value, "NA+nb".
    """
    strata = tuple(strata)
    population = Counter()
    heaps = {}
    for seq, r in enumerate(records):
        c = tuple(_cell_value(value(r, f)) for f in strata)
        population[c] += 1
        if n == 0:
            continue
        rid = value(r, id_field)
        key = str(rid) if rid is not None else "text:" + (value(r, "text") or "")
        # max-heap on rank: the worst kept is on top; seq breaks ties between duplicates
        item = (-rank(key, seed), key, -seq, r)
        h = heaps.setdefault(c, [])
        if n is None or len(h) < n:
            heapq.heappush(h, item)
        elif item[:3] > h[0][:3]:
            heapq.heapreplace(h, item)
    cells = {c: [it[3] for it in sorted(h, key=lambda it: (-it[0], it[1], -it[2]))]
             for c, h in heaps.items()}
    return Sample(strata, cells, population, n, seed)


def _cell_value(v):
    return "+".join(map(str, v)) if isinstance(v, (list, tuple)) else v


def build(records, settings):
    """Adapt, annotate, derive, keep and stratify: a stream of records -> Sample.

    settings: adapter, threshold, filters (keyword arguments of ``webmeta.select``),
    fields, keep, strata, n, seed (see the module docstring).
    """
    s = settings or {}
    out = pipeline.run(records, adapter=s.get("adapter", "contract"),
                       threshold=s.get("threshold"), **(s.get("filters") or {}))
    out = derive(out, s.get("fields"))
    out = keep(out, s.get("keep"))
    return stratify(out, s.get("strata", ()), s.get("n"), s.get("seed", 0))


# ------------------------------------------------------------------- export

FORMATS = ("jsonl", "txt", "csv", "parquet")


def export(sample, outdir, format="jsonl", dirs=None, columns=("id",), fields=None,
           name="{id}", text_field="text"):
    """Write a Sample to ``outdir`` in the chosen format, plus ``cells.tsv``.

    format   "jsonl"    full records with webmeta's ``meta`` (``fields`` limits which
                        record fields are kept, e.g. ("id", "url", "text"))
             "txt"      one text file per document, named by ``name``, with a
                        ``documents.tsv`` index of ``columns``
             "csv", "parquet"  one table of ``columns`` plus ``text_field``
                        (parquet needs pandas and pyarrow)
    dirs     folder template, e.g. "{level}/{category}": txt files go into these
             folders, other formats write one file per folder. None = top level.
             Large flat directories are slow on shared file systems such as Lustre.
    columns  fields for the tables; a dict-valued field (e.g. ``register``) becomes
             one column per key, ``register.NA`` ...
    name     txt only: filename template, e.g. "{id}_{category}_{level}"
    Returns the number of documents written.
    """
    if format not in FORMATS:
        raise ValueError(f"format must be one of {FORMATS}, not {format!r}")
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    groups = {}                                   # folder -> [records]
    for r in sample.records():
        folder = Path(*[_safe(p) for p in _fill(dirs, r).split("/") if p]) if dirs else Path()
        groups.setdefault(folder, []).append(r)

    n = 0
    index = []                                    # documents.tsv rows (txt)
    for folder, recs in groups.items():
        (out / folder).mkdir(parents=True, exist_ok=True)
        if format == "txt":
            for r in recs:
                fname = str(folder / _filename(name, r)) if dirs else _filename(name, r)
                (out / fname).write_text(value(r, text_field) or "", encoding="utf-8")
                index.append({**_row(r, columns), "file": fname})
        elif format == "jsonl":
            with open(out / folder / "documents.jsonl", "w", encoding="utf-8") as fh:
                for r in recs:
                    keep = r if fields is None else {k: r.get(k) for k in fields}
                    fh.write(json.dumps({**keep, "meta": r.get("meta")}, ensure_ascii=False) + "\n")
        else:
            rows = [{**_row(r, columns), text_field: value(r, text_field)} for r in recs]
            if format == "csv":
                header = _header(rows, columns) + [text_field]
                _write_table(out / folder / "documents.csv", header, rows, delimiter=",")
            else:
                import pandas as pd
                pd.DataFrame(rows).to_parquet(out / folder / "documents.parquet")
        n += len(recs)
    if format == "txt":
        _write_tsv(out / "documents.tsv", _header(index, columns) + ["file"], index)
    write_counts(sample, out / "cells.tsv")
    _write_run_record(out, sample, format)
    return n


def _write_run_record(out, sample, format):
    """webmeta.json: the webmeta version, the selection, and the country table used."""
    from . import __version__, geo
    record = {"webmeta": __version__, "strata": list(sample.strata), "n": sample.n,
              "seed": sample.seed, "format": format, "documents": len(sample),
              "country_table": geo.table_info()}
    (out / "webmeta.json").write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")


def _row(r, columns):
    row = {}
    for col in columns:
        v = value(r, col)
        if isinstance(v, dict):
            row.update({f"{col}.{k}": x for k, x in v.items()})
        else:
            row[col] = json.dumps(v, ensure_ascii=False) if isinstance(v, (list, tuple)) else v
    return row


def _header(rows, columns):
    """Columns in order; a dict-valued column expands to its sorted keys."""
    seen = set().union(*(row.keys() for row in rows)) if rows else set()
    header = []
    for col in columns:
        expanded = sorted(k for k in seen if k.startswith(col + "."))
        header += expanded if expanded and col not in seen else [col]
    return header


def write_counts(sample, path):
    """Write a Sample's cell table (values, population, taken) as TSV."""
    _write_tsv(path, [*sample.strata, "population", "taken"], sample.table())


def _fill(template, record):
    fields = {**{k: v for k, v in record.items() if k != "meta"}, **(record.get("meta") or {})}
    return template.format_map(_Blank(fields))


def _safe(stem):
    return "".join(ch if ch.isalnum() or ch in "-_.+" else "-" for ch in stem) or "-"


def _filename(template, record):
    return _safe(_fill(template, record)) + ".txt"


class _Blank(dict):
    def __missing__(self, key):
        return ""


def _write_tsv(path, header, rows):
    _write_table(path, header, rows, delimiter="\t")


def _write_table(path, header, rows, delimiter):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header, delimiter=delimiter, extrasaction="ignore",
                           lineterminator="\n")
        w.writeheader()
        for row in rows:
            w.writerow({k: "" if v is None else v for k, v in row.items()})


def _sort_key(cell):
    return tuple((v is None, str(v)) for v in cell)
