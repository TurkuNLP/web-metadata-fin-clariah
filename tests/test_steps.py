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
    assert country.country("https://startup.io/") is None  # code used worldwide
    assert country.country("http://192.168.0.1/x") is None
    assert country.country("yle.fi") == "FI"


def test_codes_used_worldwide_keep_only_local_languages():
    assert country.country("https://news.me/a", "bos_Latn") == "ME"   # Montenegrin page on .me
    assert country.country("https://news.me/a", "eng_Latn") is None
    assert country.country("https://tienda.co/", "spa") == "CO"
    assert country.country("https://startup.co/", "eng") is None
    assert country.country("https://berita.cc/", "zsm") is None      # far more than ~600 islanders write
    assert country.country("https://yle.fi/", "eng") == "FI"         # national: every language
    assert country.annotate({"url": "https://x.tv/", "lang": "eng"})["tld_use"] == "gated"


def test_cctld_classes_from_counts(tmp_path):
    from webmeta import cctld
    counts = tmp_path / "counts.csv"
    counts.write_text("tld,language,document_count\n"
                      "fi,fin,900\nfi,eng,100\n"            # national
                      "tv,eng,9000\nme,eng,950\nme,bos,50\n")
    table = {"countries": {"FI": {"languages": {"fin": 0.9}}, "TV": {"languages": {"tvl": 0.9, "eng": 0.5}},
                           "ME": {"languages": {"srp": 0.5}}}}
    t = cctld.build(counts, "test", table=table, population={"FI": 500, "TV": 10, "ME": 600},
                    macro={"srp": {"bos", "hrv", "hbs"}})
    c = t["codes"]
    assert c["FI"]["class"] == "national"
    assert c["TV"]["class"] == "gated" and c["TV"]["local_languages"] == []   # 900 documents per inhabitant
    assert c["ME"]["class"] == "gated" and c["ME"]["local_languages"] == ["bos"]


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
