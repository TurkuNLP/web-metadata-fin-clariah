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
    """Equal allocation: up to ``n`` records per cell, chosen by rank; returns a Sample."""
    strata = tuple(strata)
    population = Counter()
    heaps = {}
    for r in records:
        c = tuple(value(r, f) for f in strata)
        population[c] += 1
        if n == 0:
            continue
        rid = value(r, id_field)
        item = (-rank(rid, seed), str(rid), r)   # max-heap on rank: the worst kept is on top
        h = heaps.setdefault(c, [])
        if n is None or len(h) < n:
            heapq.heappush(h, item)
        elif item[:2] > h[0][:2]:
            heapq.heapreplace(h, item)
    cells = {c: [it[2] for it in sorted(h, key=lambda it: (-it[0], it[1]))]
             for c, h in heaps.items()}
    return Sample(strata, cells, population, n, seed)


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

def export(sample, outdir, name="{id}", text_field="text", columns=("id",),
           texts=True, dirs=None):
    """Write a Sample as one .txt per document plus ``documents.tsv`` and ``cells.tsv``.

    name     filename template, filled from meta and record fields, e.g. "{id}_{category}_{level}"
    dirs     subdirectory template, e.g. "{level}/{category}"; None = all files at the top.
             Large flat directories are slow on shared file systems such as Lustre.
    columns  fields for documents.tsv; a dict-valued field (e.g. ``register``)
             becomes one column per key, ``register.NA`` ...
    texts    False = tables only
    Returns the number of documents written.
    """
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    rows, keys = [], {}
    for r in sample.records():
        row = {}
        for col in columns:
            v = value(r, col)
            if isinstance(v, dict):
                keys.setdefault(col, set()).update(v)
                row.update({f"{col}.{k}": x for k, x in v.items()})
            else:
                row[col] = json.dumps(v, ensure_ascii=False) if isinstance(v, (list, tuple)) else v
        if texts:
            fname = _filename(name, r)
            if dirs:
                sub = Path(*[_safe(p) for p in _fill(dirs, r).split("/") if p])
                (out / sub).mkdir(parents=True, exist_ok=True)
                fname = str(sub / fname)
            row["file"] = fname
            (out / fname).write_text(value(r, text_field) or "", encoding="utf-8")
        rows.append(row)
    header = []
    for col in columns:
        header += [f"{col}.{k}" for k in sorted(keys[col])] if col in keys else [col]
    if texts:
        header.append("file")
    _write_tsv(out / "documents.tsv", header, rows)
    _write_tsv(out / "cells.tsv", [*sample.strata, "population", "taken"], sample.table())
    return len(rows)


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
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header, delimiter="\t", extrasaction="ignore",
                           lineterminator="\n")
        w.writeheader()
        for row in rows:
            w.writerow({k: "" if v is None else v for k, v in row.items()})


def _sort_key(cell):
    return tuple((v is None, str(v)) for v in cell)
