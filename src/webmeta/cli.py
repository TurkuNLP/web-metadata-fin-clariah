"""Command line: ``webmeta run`` filters, ``webmeta count`` tabulates, ``webmeta build`` makes a dataset from a settings file, ``webmeta check`` reports what a corpus supports, ``webmeta geo`` shows the country table."""

import argparse
import itertools
import json
import sys

from . import io, pipeline, schema, subsample


def _list(value):
    return [v for v in value.split(",") if v] if value else None


def main(argv=None):
    p = argparse.ArgumentParser(prog="webmeta", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="annotate and filter records")
    r.add_argument("inputs", nargs="+", help=".jsonl[.zst|.gz], .csv, .tsv, .parquet or a HF dataset id")
    r.add_argument("-o", "--out", required=True, help="output .jsonl, .parquet or .csv")
    r.add_argument("--adapter", default="hplt4", choices=sorted(io.ADAPTERS))
    r.add_argument("--lang", type=_list, help="comma-separated language codes")
    r.add_argument("--any-segment", action="store_true", help="match --lang against segment languages too")
    r.add_argument("--multilingual", choices=["yes", "no"])
    r.add_argument("--country", type=_list, help="comma-separated ISO country codes")
    r.add_argument("--region", type=_list, help="comma-separated UN regions, e.g. Europe,Asia")
    r.add_argument("--subregion", type=_list, help='comma-separated UN subregions, e.g. "Northern Europe"')
    r.add_argument("--register", type=_list, help="comma-separated register labels")
    r.add_argument("--hybrid", choices=["yes", "no"])
    r.add_argument("--exclude", type=_list, help="comma-separated register labels that disqualify a document, e.g. MT")
    r.add_argument("--threshold", type=float, help="register threshold; default: the model's per-language value")
    r.add_argument("--limit", type=int)
    r.add_argument("--strict", action="store_true")

    k = sub.add_parser("count", help="count kept documents by meta fields, as TSV")
    k.add_argument("inputs", nargs="+")
    k.add_argument("--adapter", default="hplt4", choices=sorted(io.ADAPTERS))
    k.add_argument("--by", type=_list, default=["lang", "country"],
                   help="comma-separated meta fields, e.g. lang,country,registers (default: lang,country)")
    k.add_argument("--threshold", type=float)
    k.add_argument("--exclude", type=_list)
    k.add_argument("-o", "--out", help="TSV file (default: stdout)")

    b = sub.add_parser("build", help="build a dataset from a study's settings file")
    b.add_argument("inputs", nargs="+")
    b.add_argument("--settings", required=True,
                   help="Python file defining SETTINGS (see webmeta.subsample) and optionally EXPORT")
    b.add_argument("-o", "--out", required=True, help="output directory")
    b.add_argument("--counts-only", action="store_true",
                   help="only count the cells (n = 0): writes cells.tsv")

    g = sub.add_parser("geo", help="show the country table in use, or rebuild it")
    g.add_argument("--refresh", action="store_true", help="rebuild from the sources now (needs the geo extra)")
    g.add_argument("--country", help="show one country's row, e.g. FI")

    c = sub.add_parser("check", help="count how many records can run each step")
    c.add_argument("input")
    c.add_argument("--adapter", default="hplt4", choices=sorted(io.ADAPTERS))
    c.add_argument("--n", type=int, default=1000, help="records to inspect")

    a = p.parse_args(argv)
    yn = {"yes": True, "no": False, None: None}

    if a.cmd == "geo":
        from . import geo
        geo.table(refresh="force" if a.refresh else "auto")
        info = geo.table_info()
        if a.country:
            json.dump(geo.lookup(a.country), sys.stdout, indent=2, ensure_ascii=False)
        else:
            info["countries"] = len(geo.table()["countries"])
            json.dump(info, sys.stdout, indent=2, ensure_ascii=False)
        print()
        return 0

    if a.cmd == "check":
        adapt = io.ADAPTERS[a.adapter]
        recs = (adapt(x) for x in itertools.islice(io.read(a.input), a.n))
        json.dump(schema.coverage(recs), sys.stdout, indent=2)
        print()
        return 0

    raw = itertools.chain.from_iterable(io.read(i) for i in a.inputs)

    if a.cmd == "build":
        study = _load(a.settings)
        settings = dict(study.SETTINGS)
        if a.counts_only:
            settings["n"] = 0
        sample = subsample.build(raw, settings)
        if a.counts_only:
            from pathlib import Path
            Path(a.out).mkdir(parents=True, exist_ok=True)
            subsample.write_counts(sample, f"{a.out}/cells.tsv")
            print(f"counted {sum(sample.population.values())} documents in "
                  f"{len(sample.population)} cells -> {a.out}/cells.tsv", file=sys.stderr)
        else:
            record = {"settings_file": a.settings, "inputs": list(a.inputs), **settings}
            n = subsample.export(sample, a.out, settings=record, **getattr(study, "EXPORT", {}))
            print(f"wrote {n} documents to {a.out}", file=sys.stderr)
        return 0

    if a.cmd == "count":
        kept = pipeline.run(raw, adapter=a.adapter, threshold=a.threshold,
                            exclude=a.exclude or ())
        counts = pipeline.summary(kept, by=tuple(a.by))
        fh = open(a.out, "w") if a.out else sys.stdout
        fh.write("\t".join([*a.by, "n"]) + "\n")
        for key, n in sorted(counts.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
            fh.write("\t".join([*("" if x is None else str(x) for x in key), str(n)]) + "\n")
        if a.out:
            fh.close()
        return 0

    out = pipeline.run(raw, adapter=a.adapter, threshold=a.threshold, limit=a.limit,
                       strict=a.strict, lang=a.lang, any_segment=a.any_segment,
                       multilingual=yn[a.multilingual], country=a.country,
                       region=a.region, subregion=a.subregion, register=a.register, hybrid=yn[a.hybrid], exclude=a.exclude or ())
    n = io.write(out, a.out)
    print(f"wrote {n} records to {a.out}", file=sys.stderr)
    return 0


def _load(path):
    """Import a settings file as a module."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("webmeta_settings", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


if __name__ == "__main__":
    sys.exit(main())
