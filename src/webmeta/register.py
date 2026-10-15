"""Register step: labels and hybrids from register probabilities.

First version. Works on the 25-class TurkuNLP web
register taxonomy: 9 main registers and 16 subregisters. A label is assigned
when its probability reaches the threshold. A subregister counts only together
with its main register, e.g. ``nb`` (narrative blog) only under ``NA``.

HPLT 4's ``web-register`` probabilities come from the public XLM-R checkpoint
``TurkuNLP/web-register-classification-multilingual`` run at 512 tokens
(identified empirically, 2026-10-15), so the thresholds default to that
model's per-language values from its model card.
"""

MAIN = ("MT", "LY", "SP", "ID", "NA", "HI", "IN", "OP", "IP")

PARENT = {
    "it": "SP",
    "ne": "NA", "sr": "NA", "nb": "NA",
    "re": "HI",
    "en": "IN", "ra": "IN", "dtp": "IN", "fi": "IN", "lt": "IN",
    "rv": "OP", "ob": "OP", "rs": "OP", "av": "OP",
    "ds": "IP", "ed": "IP",
}

LABELS = MAIN + tuple(PARENT)

NAMES = {
    "MT": "Machine translated", "LY": "Lyrical", "SP": "Spoken", "ID": "Interactive discussion",
    "NA": "Narrative", "HI": "How-to or instructions", "IN": "Informational description",
    "OP": "Opinion", "IP": "Informational persuasion",
    "it": "Interview", "ne": "News report", "sr": "Sports report", "nb": "Narrative blog",
    "re": "Recipe", "en": "Encyclopedia article", "ra": "Research article",
    "dtp": "Description of a thing or person", "fi": "FAQ", "lt": "Legal terms and conditions",
    "rv": "Review", "ob": "Opinion blog", "rs": "Religious blog or sermon", "av": "Advice",
    "ds": "Description with intent to sell", "ed": "News and opinion blog or editorial",
}

# Per-language thresholds from the XLM-R model card (ISO 639-3 keys):
# tuned on the five training languages, plus its zero-shot evaluation.
THRESHOLDS = {
    "eng": 0.40, "fin": 0.45, "fra": 0.45, "swe": 0.45, "tur": 0.45,
    "arb": 0.40, "ara": 0.40, "cat": 0.50, "spa": 0.65, "pes": 0.35, "fas": 0.35,
    "hin": 0.40, "ind": 0.30, "jpn": 0.35, "nor": 0.65, "nob": 0.65, "nno": 0.65,
    "por": 0.40, "urd": 0.35, "zho": 0.40, "cmn": 0.40,
}
# Languages the card does not list: its own example value.
DEFAULT_THRESHOLD = 0.5


def threshold_for(lang):
    """The model card's threshold for a language code ('fin_Latn' -> 0.45)."""
    from .language import base
    return THRESHOLDS.get(base(lang), DEFAULT_THRESHOLD)


def labels(probs, threshold=DEFAULT_THRESHOLD):
    """Main and subregister labels at or above the threshold, main labels first."""
    probs = probs or {}
    mains = [m for m in MAIN if probs.get(m, 0.0) >= threshold]
    subs = [s for s, p in PARENT.items() if p in mains and probs.get(s, 0.0) >= threshold]
    return mains + subs


def annotate(record, threshold=None):
    """threshold None = the model card's value for the record's language."""
    t = threshold_for(record.get("lang")) if threshold is None else threshold
    found = labels(record.get("register"), t)
    mains = [l for l in found if l in MAIN]
    return {"registers": found, "hybrid": len(mains) >= 2, "threshold": t}


def matches(meta, register=None, hybrid=None, exclude=()):
    """Does an annotated record pass the register filter?

    register  a label or list of labels; the record passes if it has any of them
    hybrid    True = only hybrids (two or more main registers), False = only non-hybrids
    exclude   labels that disqualify a record, e.g. ("MT",); default none
    """
    have = set(meta["registers"])
    if exclude and have & set(exclude):
        return False
    if hybrid is not None and meta["hybrid"] != hybrid:
        return False
    if register is None:
        return True
    wanted = {register} if isinstance(register, str) else set(register)
    return bool(wanted & have)
