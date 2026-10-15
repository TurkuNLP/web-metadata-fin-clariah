from webmeta import country, language, register


def test_language_codes_normalise():
    assert language.base("fin_Latn") == language.base("fi") == language.base("fin") == "fin"


def test_multilingual_needs_two_segment_languages():
    assert language.is_multilingual({"seg_langs": ["eng_Latn", "fin_Latn"]})
    assert not language.is_multilingual({"seg_langs": ["fin_Latn", "fin_Latn"]})
    assert not language.is_multilingual({})


def test_country_from_tld():
    assert country.country("https://yle.fi/uutiset") == "FI"
    assert country.country("https://www.bbc.co.uk/news") == "GB"
    assert country.country("https://example.com/") is None
    assert country.country("https://startup.io/") is None  # vanity ccTLD
    assert country.country("http://192.168.0.1/x") is None
    assert country.country("yle.fi") == "FI"


def test_register_labels_and_hybrids():
    probs = {"NA": 0.9, "nb": 0.8, "OP": 0.5, "ob": 0.3, "ne": 0.6}
    assert register.labels(probs, 0.4) == ["NA", "OP", "ne", "nb"]
    assert register.annotate({"register": probs}, 0.4)["hybrid"]


def test_subregister_needs_its_main_register():
    assert register.labels({"nb": 0.9}, 0.4) == []


def test_per_language_threshold():
    assert register.threshold_for("eng_Latn") == 0.40
    assert register.threshold_for("fi") == 0.45
    assert register.threshold_for("xyz") == register.DEFAULT_THRESHOLD
    probs = {"NA": 0.42}
    assert register.annotate({"lang": "eng", "register": probs})["registers"] == ["NA"]
    assert register.annotate({"lang": "fin", "register": probs})["registers"] == []


def test_hybrid_is_two_main_registers():
    assert register.annotate({"register": {"NA": 0.9, "OP": 0.8}}, 0.4)["hybrid"]
    assert not register.annotate({"register": {"NA": 0.9, "ne": 0.8, "sr": 0.7}}, 0.4)["hybrid"]
