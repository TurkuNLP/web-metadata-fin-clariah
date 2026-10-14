"""Language step: document language and multilingual documents.

First version. Language codes are compared after
normalisation, so "fi", "fin" and "fin_Latn" all select Finnish.
"""

# ISO 639-1 -> 639-3 for the languages most likely to be asked for by
# two-letter code. Three-letter and HPLT-style "xxx_Scrp" codes need no table.
_ISO1_TO_3 = {
    "en": "eng", "fi": "fin", "sv": "swe", "et": "est", "no": "nor", "nb": "nob",
    "nn": "nno", "da": "dan", "is": "isl", "de": "deu", "fr": "fra", "es": "spa",
    "it": "ita", "pt": "por", "nl": "nld", "pl": "pol", "ru": "rus", "uk": "ukr",
    "tr": "tur", "ar": "arb", "fa": "pes", "hi": "hin", "ur": "urd", "zh": "zho",
    "ja": "jpn", "ko": "kor", "se": "sme",
}


def base(code):
    """Normalise a language code to a lowercase ISO 639-3 code ('fin_Latn' -> 'fin')."""
    if not code:
        return None
    c = str(code).strip().split("_")[0].split("-")[0].lower()
    return _ISO1_TO_3.get(c, c)


def languages(record):
    """Distinct base languages of a record: its document language plus segment languages."""
    found = []
    for c in [record.get("lang"), *(record.get("seg_langs") or [])]:
        b = base(c)
        if b and b not in found:
            found.append(b)
    return found


def is_multilingual(record):
    """True when the segments carry two or more distinct languages."""
    return len({base(c) for c in (record.get("seg_langs") or []) if c}) >= 2


def annotate(record):
    return {
        "lang": base(record.get("lang")),
        "languages": languages(record),
        "multilingual": is_multilingual(record),
    }


def matches(meta, lang=None, multilingual=None, any_segment=False):
    """Does an annotated record pass the language filter?

    lang          a code or a list of codes; None = any language
    multilingual  True = only multilingual documents, False = only monolingual
    any_segment   match ``lang`` against any segment language, not only the
                  document language (targets documents that *contain* a language)
    """
    if multilingual is not None and meta["multilingual"] != multilingual:
        return False
    if lang is None:
        return True
    wanted = {base(l) for l in ([lang] if isinstance(lang, str) else lang)}
    pool = set(meta["languages"]) if any_segment else {meta["lang"]}
    return bool(wanted & pool)
