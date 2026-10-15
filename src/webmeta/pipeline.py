"""The pipeline: annotate each record with language, country and register, then select.

    >>> import webmeta
    >>> docs = webmeta.read("sample.jsonl.zst")
    >>> out = webmeta.run(docs, adapter="hplt4", lang="swe", country="FI", register="NA")

Annotations are added under the ``meta`` key, so source fields are never
overwritten.
"""

from . import country as _country
from . import language as _language
from . import register as _register
from . import schema
from .io import ADAPTERS


def annotate(record, threshold=None):
    """Return a copy of ``record`` with a ``meta`` dict of everything webmeta derived.

    A step whose input field is missing is skipped and its values are None,
    so a corpus without URLs can still be filtered by language and register.
    threshold None = the register model's per-language value.
    """
    gone = schema.missing_fields(record)
    meta = {}
    meta.update(_language.annotate(record) if "language" not in gone
                else {"lang": None, "languages": [], "multilingual": False})
    meta.update(_country.annotate(record) if "country" not in gone
                else {"tld": None, "country": None})
    meta.update(_register.annotate(record, threshold) if "register" not in gone
                else {"registers": [], "hybrid": False, "threshold": None})
    return {**record, "meta": meta}


def select(meta, lang=None, multilingual=None, any_segment=False,
           country=None, register=None, hybrid=None, exclude=()):
    """True if an annotated record's ``meta`` passes every filter given."""
    return (_language.matches(meta, lang, multilingual, any_segment)
            and _country.matches(meta, country)
            and _register.matches(meta, register, hybrid, exclude))


def run(records, adapter="contract", threshold=None,
        limit=None, strict=False, **filters):
    """Adapt, annotate and filter a stream of records; yields matching records.

    adapter   "hplt4", "contract", or a function raw dict -> contract record
    limit     stop after this many matches
    strict    raise ContractError when a record lacks a field a requested
              filter needs, instead of letting it fail the filter
    filters   keyword arguments of ``select``
    """
    adapt = ADAPTERS[adapter] if isinstance(adapter, str) else adapter
    steps = [s for s, keys in (("language", ("lang", "multilingual")),
                               ("country", ("country",)),
                               ("register", ("register", "hybrid")))
             if any(filters.get(k) is not None for k in keys)]
    n = 0
    for raw in records:
        rec = adapt(raw)
        if strict:
            schema.check(rec, steps)
        rec = annotate(rec, threshold)
        if select(rec["meta"], **filters):
            yield rec
            n += 1
            if limit is not None and n >= limit:
                return


def summary(records, by=("lang", "country")):
    """Count annotated records by meta fields, e.g. ("lang", "country").

    "registers" is counted once per label. Fields not in ``meta`` are read from
    the record itself.
    """
    from collections import Counter
    c = Counter()
    for r in records:
        m = r["meta"]
        key = tuple(m[k] if k in m else r.get(k) for k in by if k != "registers")
        if "registers" in by:
            for lab in m["registers"] or [None]:
                c[key + (lab,)] += 1
        else:
            c[key] += 1
    return c
