"""The record contract every filter works against.

A record is a plain dict. webmeta never reads source-specific fields
directly: an adapter (``webmeta.io.from_hplt4``) or a field mapping
(``webmeta.io.from_mapping``) first turns each source record into this shape.
That is what lets the same pipeline run on HPLT 4 and on a user's own corpus.

Canonical fields
----------------
text       str                 required
url        str                 needed by the country step
lang       str                 needed by the language step, e.g. "fin_Latn" or "fi"
seg_langs  list[str]           optional; languages found in the document's
                               segments. Two or more distinct values mark the
                               document as multilingual.
register   dict[str, float]    needed by the register step: label -> probability,
                               using the 25 labels in ``webmeta.register.LABELS``
id         str                 optional; carried through unchanged

Any other keys are carried through unchanged.
"""

REQUIRED = ("text",)

NEEDS = {
    "language": ("lang",),
    "country": ("url",),
    "register": ("register",),
}


class ContractError(ValueError):
    """A record lacks a field that a requested step needs."""


def missing_fields(record, steps=NEEDS):
    """Return {step: [missing field, ...]} for the steps this record cannot run."""
    out = {}
    for step, fields in steps.items():
        gone = [f for f in fields if record.get(f) in (None, "")]
        if gone:
            out[step] = gone
    return out


def check(record, steps=()):
    """Raise ContractError if ``record`` cannot run the given steps."""
    for f in REQUIRED:
        if not isinstance(record.get(f), str):
            raise ContractError(f"record has no '{f}' string")
    wanted = {s: NEEDS[s] for s in steps}
    gone = missing_fields(record, wanted)
    if gone:
        detail = "; ".join(f"{s} needs {', '.join(f)}" for s, f in gone.items())
        raise ContractError(f"record {record.get('id', '?')}: {detail}")


def coverage(records):
    """Count, over an iterable of records, how many can run each step.

    Returns {"records": n, "language": k, "country": k, "register": k}.
    Used by the notebook to tell a user what their own data supports.
    """
    counts = {"records": 0, **{s: 0 for s in NEEDS}}
    for r in records:
        counts["records"] += 1
        gone = missing_fields(r)
        for s in NEEDS:
            if s not in gone:
                counts[s] += 1
    return counts
