"""Reading and writing records, and turning source records into the contract.

Readers yield raw dicts. Adapters turn them into contract records
(``webmeta.schema``). Optional dependencies (zstandard, pandas, datasets) are
imported only when the format that needs them is used.
"""

import io as _io
import json
from pathlib import Path


# ------------------------------------------------------------------ readers

def read_jsonl(path):
    """Yield dicts from a .jsonl, .jsonl.gz or .jsonl.zst file."""
    path = str(path)
    if path.endswith(".zst"):
        import zstandard
        fh = open(path, "rb")
        stream = _io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(fh), encoding="utf-8")
    elif path.endswith(".gz"):
        import gzip
        stream = gzip.open(path, "rt", encoding="utf-8")
    else:
        stream = open(path, encoding="utf-8")
    with stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def read_table(path):
    """Yield dicts from a CSV, TSV or Parquet file (needs pandas)."""
    import pandas as pd
    path = str(path)
    if path.endswith(".parquet"):
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path, sep="\t" if path.endswith(".tsv") else ",")
    # Empty cells arrive as NaN; the contract treats them as missing.
    df = df.astype(object).where(df.notna(), None)
    for row in df.to_dict(orient="records"):
        yield row


def read_hf(repo_id, split="train", config=None, streaming=True):
    """Yield dicts from a Hugging Face dataset (needs datasets)."""
    from datasets import load_dataset
    yield from load_dataset(repo_id, config, split=split, streaming=streaming)


def read(source):
    """Pick a reader by file extension; anything else is taken as a Hugging Face repo id."""
    s = str(source)
    if s.endswith((".jsonl", ".jsonl.gz", ".jsonl.zst", ".json")):
        return read_jsonl(s)
    if s.endswith((".csv", ".tsv", ".parquet")):
        return read_table(s)
    if Path(s).exists():
        raise ValueError(f"unknown file type: {s}")
    return read_hf(s)


# ----------------------------------------------------------------- adapters

def _top_label(value):
    """The top language from a language-ID field, whatever its shape.

    HPLT 4's exact field shapes are an ASSUMPTION until checked against real
    records on LUMI: a plain code, {"lang": ...}, or a ranked list of
    [code, prob] pairs / codes are all accepted.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for k in ("lang", "label", "language", "code"):
            if k in value:
                return _top_label(value[k])
        return None
    if isinstance(value, (list, tuple)) and value:
        return _top_label(value[0])
    return None


def _seg_langs(value):
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [l for l in (_top_label(v) for v in value) if l]


HPLT4_LANG_FIELDS = ("openlid_v3", "openlid_v2", "glotlid_v3")


def from_hplt4(raw):
    """HPLT 4 record -> contract record. Field names per the HPLT 4 release on LUMI.

    The source fields are kept alongside (e.g. ``doc_scores``), so settings can
    derive values from them.
    """
    lang = next((l for l in (_top_label(raw.get(f)) for f in HPLT4_LANG_FIELDS) if l), None)
    return {
        **raw,
        "id": raw.get("id"),
        "text": raw.get("text"),
        "url": raw.get("u"),
        "lang": lang,
        "seg_langs": _seg_langs(raw.get("seg_langs_openlid_v3")),
        "register": raw.get("web-register"),
        "ts": raw.get("ts"),
    }



def from_mapping(raw, mapping):
    """User record -> contract record, renaming fields per ``mapping``.

    mapping: {contract field: source field}, e.g. {"text": "body", "url": "link"}.
    Contract fields left out of the mapping are looked up under their own name.
    Register probabilities may be given as a dict field, or as one column per
    label (e.g. columns "NA", "nb", ...), which are gathered automatically.
    """
    from .register import LABELS
    rec = dict(raw)
    for field, src in (mapping or {}).items():
        if src and src in raw:
            rec[field] = raw[src]
    reg = rec.get("register")
    if isinstance(reg, str):
        reg = json.loads(reg)
    if reg is None:
        cols = {l: raw[l] for l in LABELS if l in raw}
        reg = {k: float(v) for k, v in cols.items()} or None
    rec["register"] = reg
    if isinstance(rec.get("seg_langs"), str):
        rec["seg_langs"] = [s for s in rec["seg_langs"].replace(",", " ").split() if s]
    return rec


ADAPTERS = {"hplt4": from_hplt4, "contract": lambda r: r}


# ------------------------------------------------------------------ writers

def write_jsonl(records, path):
    """Write records to JSONL; returns the number written."""
    n = 0
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def write(records, path):
    """Write by extension: .jsonl, or .parquet / .csv (needs pandas)."""
    path = str(path)
    if path.endswith(".jsonl"):
        return write_jsonl(records, path)
    import pandas as pd
    df = pd.DataFrame(list(records))
    if path.endswith(".parquet"):
        df.to_parquet(path)
    else:
        df.to_csv(path, index=False)
    return len(df)
