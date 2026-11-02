"""How each country-code domain is used: as a national domain, or worldwide.

Some country codes are sold worldwide as generic domains (.tv, .io, .me), so a
.tv site says little about Tuvalu. Which codes are used that way is measured
from corpus counts, not listed by hand. Each code gets a class:

national  every document on the code gets the country
gated     only documents in one of the country's own languages, other than
          English, get the country (a Montenegrin page on .me is still from
          Montenegro; an English one on .me could be from anywhere)

A code is national when both hold:

1. Most of its documents are in the country's own languages:
   own-language share >= OWN_SHARE. The country's languages are those spoken
   by at least LANGUAGE_SHARE of its population (Unicode CLDR), counting the
   other members of a macrolanguage as the same language (Bosnian and Serbian;
   Standard Malay and Malay).
2. It has no more documents than its population could plausibly write:
   documents per inhabitant <= MAX_PER_INHABITANT. National codes of large
   countries have about 1-10; codes sold worldwide have hundreds or thousands.

A gated code keeps the country only for its local-language documents, and not
even for those if they too exceed MAX_PER_INHABITANT (Malay on .cc, the Cocos
Islands, ~600 inhabitants). A code missing from the counts is national.

The classes ship in ``data/cctld_use.json``; ``build`` recomputes them from a
table of counts per code and language, such as HPLT's.
"""

import csv
import datetime as _dt
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

OWN_SHARE = 0.50
MAX_PER_INHABITANT = 30
LANGUAGE_SHARE = 0.01
NEVER_LOCAL = {"eng"}          # used worldwide, so it never shows where a site is from

USE_NAME = "cctld_use.json"
SHIPPED = Path(__file__).parent / "data" / USE_NAME
MACROLANGUAGES = "https://iso639-3.sil.org/sites/iso639-3/files/downloads/iso-639-3-macrolanguages.tab"

_USE = None


def use():
    """The class table: {"codes": {"TV": {"class": "gated", ...}}, ...}.
    ``WEBMETA_CCTLD_USE`` (a path) pins another table."""
    global _USE
    if _USE is None:
        path = Path(os.environ.get("WEBMETA_CCTLD_USE") or SHIPPED)
        _USE = json.loads(path.read_text(encoding="utf-8"))
        _USE["loaded_from"] = str(path)
    return _USE


def use_info():
    """Where the class table came from and its rule, without the per-code rows."""
    return {k: v for k, v in use().items() if k != "codes"}


def gives_country(code, lang):
    """Does a document in ``lang`` (ISO 639-3) on country code ``code`` get the country?"""
    row = use()["codes"].get(code)
    if row is None or row["class"] == "national":
        return True
    return lang in row["local_languages"]


# ------------------------------------------------------------------ building

def build(counts_csv, source, table=None, population=None, macro=None):
    """Classify every code from a counts table, using the country table's languages.

    counts_csv  CSV with columns tld, language (ISO 639-3) and document_count;
                other columns are ignored, repeated (tld, language) rows are summed
    source      a description of the counts, stored in the result
    population  {ISO code: inhabitants}; default: from CLDR
    macro       {language: set of languages counted as the same}; default: from SIL
    """
    from . import geo
    table = table or geo.table()
    population = population if population is not None else cldr_population()
    macro = macro if macro is not None else macrolanguages()

    counts = defaultdict(Counter)
    with open(counts_csv, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            counts[r["tld"].upper()][r["language"]] += int(r["document_count"])

    codes = {}
    for code, langs in sorted(counts.items()):
        row = table["countries"].get(code)
        if row is None:
            continue
        own = set()
        for lang, share in row.get("languages", {}).items():
            if share >= LANGUAGE_SHARE:
                own |= {lang} | macro.get(lang, set())
        total = sum(langs.values())
        inhabitants = population.get(code) or 0
        own_share = sum(n for lang, n in langs.items() if lang in own) / total
        per_person = total / inhabitants if inhabitants else float("inf")
        national = own_share >= OWN_SHARE and per_person <= MAX_PER_INHABITANT
        entry = {"class": "national" if national else "gated", "documents": total,
                 "own_share": round(own_share, 4), "inhabitants": inhabitants,
                 "per_inhabitant": _round(per_person)}
        if not national:
            local = {lang: n for lang, n in langs.items() if lang in own and lang not in NEVER_LOCAL}
            kept = sum(local.values())
            kept_per_person = kept / inhabitants if inhabitants else float("inf")
            entry["local_documents"] = kept
            entry["local_per_inhabitant"] = _round(kept_per_person)
            entry["local_languages"] = (sorted(local, key=lambda k: -local[k])
                                        if kept and kept_per_person <= MAX_PER_INHABITANT else [])
        codes[code] = entry

    return {
        "built": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "rule": {"own_share": OWN_SHARE, "max_per_inhabitant": MAX_PER_INHABITANT,
                 "language_share": LANGUAGE_SHARE, "never_local": sorted(NEVER_LOCAL)},
        "country_table": {k: table.get(k) for k in ("built", "cldr_version")},
        "codes": codes,
    }


def _round(x):
    return None if x == float("inf") else round(x, 4)


def cldr_population():
    """{ISO code: inhabitants} from Unicode CLDR territory information."""
    from . import geo
    info = json.loads(geo._fetch(geo.SOURCES["cldr_territories"]))["supplemental"]["territoryInfo"]
    return {code: int(float(d.get("_population", 0))) for code, d in info.items()}


def macrolanguages():
    """{language: the other languages of its macrolanguage, and the macrolanguage itself}."""
    from . import geo
    groups = defaultdict(set)
    for i, line in enumerate(geo._fetch(MACROLANGUAGES).decode("utf-8").splitlines()):
        cols = line.split("\t")
        if i and len(cols) >= 2:
            groups[cols[0]].add(cols[1])
    same = defaultdict(set)
    for m, members in groups.items():
        for lang in members | {m}:
            same[lang] |= (members | {m}) - {lang}
    return dict(same)
