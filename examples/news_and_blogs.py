"""Example study settings: Finnish and Swedish news reports and blogs.

Up to 50 documents per language x register, from documents of at least 200
words. Run it with

    webmeta build sample.jsonl.zst --settings examples/news_and_blogs.py -o out/news_and_blogs

A settings file is plain Python: SETTINGS says which documents qualify and how
to sample them, EXPORT how to write them out. Derived fields and keep rules are
functions, so a study can define anything its design needs (word counts, a
quality level, its own categories) without changes to webmeta.
"""

REGISTERS = ("ne", "nb", "ob")      # news report, narrative blog, opinion blog


def words(r):
    return len((r.get("text") or "").split())


def register(r):
    """The first of REGISTERS the document carries, or None."""
    return next((x for x in r["meta"]["registers"] if x in REGISTERS), None)


SETTINGS = {
    "adapter": "hplt4",                       # HPLT 4 records; "contract" for your own mapped data
    "filters": {"lang": ["fin", "swe"], "exclude": ("MT",)},
    "fields": {"words": words, "register": register},
    "keep": [lambda r: r["meta"]["words"] >= 200,
             lambda r: r["meta"]["register"] is not None],
    "strata": ("lang", "register"),           # the cells
    "n": 50,                                  # per cell; None = all
    "seed": 1,
}

EXPORT = {
    "format": "jsonl",                        # or "txt", "csv", "parquet"
    "dirs": "{lang}",                         # one folder per language
    "columns": ("id", "url", "lang", "country", "register", "words"),
}
