# Test fixtures

`hplt4_like.jsonl` is **synthetic**: the texts and URLs are invented. Its field
names and value shapes follow real HPLT 4 records (checked on LUMI against 2,000
records of the English sample, 2026-10-15): `openlid_v3` is `{"lang": [...],
"prob": [...]}` ranked by probability, `seg_langs_openlid_v3` a list of codes,
`web-register` a label→probability dict with all 25 labels. Real records are not
used here because their texts are crawled web content.

`own_corpus.csv` shows a user's own corpus: different column names, register
probabilities as one column per label, one record without a URL.
