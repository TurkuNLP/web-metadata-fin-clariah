# Test fixtures

`hplt4_like.jsonl` is **synthetic**: the texts and URLs are invented. Its field
names follow HPLT 4 as found on LUMI (2026-10-13), but the **value shapes**
(`openlid_v3` as a plain code, `seg_langs_openlid_v3` as a list of codes,
`web-register` as a label→probability dict) are assumptions. Replace this file
with a handful of real HPLT 4 records, and adjust `webmeta.io.from_hplt4` if
the shapes differ.

`own_corpus.csv` shows a user's own corpus: different column names, register
probabilities as one column per label, one record without a URL.
