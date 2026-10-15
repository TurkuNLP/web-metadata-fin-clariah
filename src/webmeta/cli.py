"""Command line: ``webmeta run`` filters, ``webmeta count`` tabulates, ``webmeta check`` reports what a corpus supports."""

import argparse
import itertools
import json
import sys

from . import io, pipeline, schema


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

    c = sub.add_parser("check", help="count how many records can run each step")
    c.add_argument("input")
    c.add_argument("--adapter", default="hplt4", choices=sorted(io.ADAPTERS))
    c.add_argument("--n", type=int, default=1000, help="records to inspect")

    a = p.parse_args(argv)
    yn = {"yes": True, "no": False, None: None}

    if a.cmd == "check":
        adapt = io.ADAPTERS[a.adapter]
        recs = (adapt(x) for x in itertools.islice(io.read(a.input), a.n))
        json.dump(schema.coverage(recs), sys.stdout, indent=2)
        print()
        return 0

    raw = itertools.chain.from_iterable(io.read(i) for i in a.inputs)

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
                       register=a.register, hybrid=yn[a.hybrid], exclude=a.exclude or ())
    n = io.write(out, a.out)
    print(f"wrote {n} records to {a.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
