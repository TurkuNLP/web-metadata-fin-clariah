<!--
  DRAFT. The top half of this file is the FIN-CLARIAH deliverable report, in the
  shape of the 2025 D3.3.3 README (fields from the coordinators' template).
  The description (max. 3000 characters) is also emailed as a Word document.
  Open items are marked TODO.
-->

# D3.3.3 (a) Analysis tools for providing metadata for web data: language, country and register

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/TurkuNLP/web-metadata-fin-clariah/blob/main/notebooks/webmeta_demo.ipynb)

**Project:** [FIN-CLARIAH](https://www.kielipankki.fi/organization/fin-clariah/)  
**Grant agreement:** Research Council of Finland no. 358720  
**Start date:** TODO (the 2025 template says 01-01-2024; check the current phase)  
**Duration:** TODO

**W3.3:** Report on analysis tools for providing metadata for web data: language, country and register  
**Date of reporting:** TODO (due 02-11-2026)

**Report authors:** TODO  
**Contributors:** TODO  
**Deliverable location:**

* Code repository: https://github.com/TurkuNLP/web-metadata-fin-clariah
* Demonstration: [Google Colab notebook](https://colab.research.google.com/github/TurkuNLP/web-metadata-fin-clariah/blob/main/notebooks/webmeta_demo.ipynb)
* Demo data: TODO (multilingual HPLT 4 sample on Hugging Face)

**Keywords:** web data; metadata; language identification; country; web registers; HPLT

**Description**

<!-- TODO: draft text, not yet reviewed. Keep within 3000 characters. -->

Web-crawled datasets are among the largest text resources available to SSH research, but they are noisy and carry little metadata, which makes it hard to find the material a research question needs.

*webmeta* turns a large web corpus into research datasets. It reads corpus metadata (register labels, language, country) and lets a researcher describe the subsample they want: which documents qualify, how to stratify, how large a subsample. The package then produces that subsample reproducibly. This makes each study just a set of settings for the tool, so a single corpus can serve many research projects without new code.

* **Language:** documents are selected by their main language, and multilingual documents can be targeted using segment-level language identification.
* **Country:** a country signal is derived from the document's top-level domain, so that, for example, Swedish written in Finland can be separated from Swedish written in Sweden.
* **Register:** documents are selected by the 25-class web register taxonomy of Skantsi and Laippala (2023), including hybrid documents that combine registers.

The repository is a Python package, `webmeta`, used in three ways. On LUMI, it runs from the command line as batch jobs over large corpus samples. The Colab demo notebook in the repo can be used standalone, where the package is installed straight from the repository and runs end to end on a small demo dataset. The package can also be imported by a researcher's own study code. It reads two kinds of input: validated HPLT 4 samples drawn by TurkuNLP's HPLT sampler, or a user's own corpus in CSV or JSONL, with its fields mapped onto field names used by the package. HPLT 4 documents already carry language identification and register probabilities for 92 languages. This README doubles as the report for Fin-CLARIAH deliverable D3.3.3 (a).

TODO: references; links; events (FIN-CLARIAH meeting poster, 9 Nov 2026).

*FIN-CLARIAH project has received funding from the European Union – NextGenerationEU instrument and is funded by the Research Council of Finland under grant number 358720.*

![](NextGenerationEU.jpg)

---

## Using webmeta

### In Colab
Open [`notebooks/webmeta_demo.ipynb`](notebooks/webmeta_demo.ipynb) in Colab and run all cells: choose the data, filter it, draw a sample with so many documents per cell, and download it.

### In Python
```bash
pip install "webmeta[zst] @ git+https://github.com/TurkuNLP/web-metadata-fin-clariah"
```
```python
import webmeta

docs = webmeta.read("shard.jsonl.zst")                 # HPLT 4 file
for doc in webmeta.run(docs, adapter="hplt4", lang="swe", country="FI", register="NA"):
    print(doc["meta"])   # {'lang': 'swe', 'country': 'FI', 'registers': ['NA', 'nb'], ...}
```

### On the command line
```bash
webmeta check shard.jsonl.zst                          # which steps the data supports
webmeta run shard.jsonl.zst -o out.jsonl --lang swe --country FI --register NA
webmeta count shard.jsonl.zst --by lang,registers         # counts as TSV
webmeta build sample.jsonl.zst --settings study.py -o out/ # a dataset from a settings file
```
On LUMI, webmeta runs on validated samples published by `hplt-sampler`, not on raw shards; see [`lumi/`](lumi/).

### Filters
| Option | Meaning |
|---|---|
| `lang` | language codes; `fi`, `fin` and `fin_Latn` are equivalent |
| `any_segment` | match `lang` in any part of the document, not only its main language |
| `multilingual` | `True`: only documents with two or more segment languages |
| `country` | ISO 3166-1 codes from the top-level domain; generic domains give no country |
| `region`, `subregion` | the country's UN region and subregion, e.g. `Europe`, `Northern Europe` |
| `register` | register labels; a document matches if it has any of them |
| `hybrid` | `True`: only documents with two or more main registers |
| `exclude` | register labels that disqualify a document, e.g. `("MT",)`; default none |
| `threshold` | register probability needed for a label; default: the register model's per-language value (English 0.40, Finnish 0.45, …) |

Every kept document gets a `meta` field with what webmeta derived; source fields are left untouched.

## Country and region

The country comes from the URL: its top-level domain, if that is a country code (`yle.fi` → `FI`, `bbc.co.uk` → `GB`). Generic domains (`.com`, `.org`, …) give no country, and neither do country codes sold worldwide as generic ones (`.io`, `.tv`, `.co`, …). The country is a signal, not a ground truth: a `.fi` site is usually Finnish, a `.com` site could be anywhere.

Each country is then placed from a country table: its name, UN region and subregion, a map point (longitude, latitude) and the languages spoken there with their population shares. Every document's `meta` gets `country`, `country_name`, `region` and `subregion`; `webmeta.geo.lookup("FI")` gives the whole row.

The table is built from public sources: [Natural Earth](https://www.naturalearthdata.com/) 10m countries and map units (public domain), [Unicode CLDR](https://cldr.unicode.org/) territory information (Unicode License), and SIL's [ISO 639-3](https://iso639-3.sil.org/) code table. Country names and borders change, so it is not frozen into a release:

- webmeta uses the cached table in `~/.cache/webmeta/` (`WEBMETA_CACHE_DIR` overrides) while it is younger than 90 days, and otherwise rebuilds it from the sources. Rebuilding needs the `geo` extra (`pip install "webmeta[geo] @ git+…"`) and network access.
- If it cannot rebuild, it falls back to the stale cache, or to the snapshot shipped with webmeta, so offline use always works.
- `WEBMETA_GEO_TABLE=/path/to/countries.json` pins a table, for a reproducible rerun. Every exported dataset records the table it used in `webmeta.json`.
- `webmeta geo` shows the table in use, `webmeta geo --country FI` one row, `webmeta geo --refresh` rebuilds it now.

## Building a dataset

A study is a set of settings: which documents qualify, which fields define the cells, how many documents per cell, and how to write them out. webmeta turns those settings into the dataset, reproducibly.

```python
import webmeta

settings = {
    "adapter": "hplt4",
    "filters": {"lang": ["fin", "swe"], "exclude": ("MT",)},          # as in the table above
    "fields": {"words": lambda r: len(r["text"].split())},          # derived values, stored in meta
    "keep": [lambda r: r["meta"]["words"] >= 200],                  # every rule must hold
    "strata": ("lang", "hybrid"),                                    # the cells
    "n": 50,                                                         # per cell; None = all, 0 = count only
    "seed": 1,
}
sample = webmeta.build(webmeta.read("sample.jsonl.zst"), settings)
print(list(sample.table()))          # per cell: population and how many were taken
webmeta.export(sample, "out/", format="jsonl", dirs="{lang}")
```

| Setting | Meaning |
|---|---|
| `adapter` | `"hplt4"` for HPLT 4 records, `"contract"` for records already in webmeta's field names, or a function |
| `threshold` | register threshold; default: the model's per-language value |
| `filters` | keyword arguments of the filter table above |
| `fields` | `{name: function(record)}`: derived values, stored in `meta` in order, so a later field can use an earlier one |
| `keep` | functions `record -> bool`; a document must pass all of them |
| `strata` | fields whose value combinations are the cells; `()` = one cell, a simple random sample |
| `n` | documents per cell (equal allocation); `None` = every document; `0` = only count the cells |
| `seed` | selection seed |

**Reproducible selection.** Each document gets a pseudo-random rank from the seed and its id, and each cell keeps its `n` lowest-ranked documents. The same settings give the same dataset however the input is ordered or split, and a smaller `n` gives a subset of a larger one.

**Export.** `webmeta.export(sample, outdir, format=...)` writes the documents, always a `cells.tsv` (per cell: its population and how many were taken), and `webmeta.json` (the webmeta version, the selection and the country table used).

| `format` | Output |
|---|---|
| `jsonl` (default) | `documents.jsonl`: full records with `meta`; `fields=(...)` keeps only some record fields |
| `txt` | one text file per document, named by `name` (e.g. `"{id}_{register}"`), plus a `documents.tsv` index of `columns` |
| `csv`, `parquet` | one table of `columns` plus the text (parquet needs pandas and pyarrow) |

`dirs` (e.g. `"{lang}/{register}"`) nests the output in folders: text files go into them, other formats write one file per folder. Large flat folders are slow on shared file systems such as Lustre. In `columns`, a dict-valued field such as `register` becomes one column per label (`register.NA`, …).

**From the command line,** put the settings in a Python file that defines `SETTINGS` and, optionally, `EXPORT` (the keyword arguments of `export`), and run `webmeta build INPUT... --settings FILE -o OUTDIR`; `--counts-only` writes just `cells.tsv`. A worked example: [`examples/news_and_blogs.py`](examples/news_and_blogs.py).

## Your own corpus: the record contract

webmeta works on any corpus whose records provide these fields. HPLT 4 records are converted automatically (`adapter="hplt4"`); for other data, map your field names with `webmeta.from_mapping(record, {"text": "body", "url": "link", ...})`.

| Field | Type | Needed for |
|---|---|---|
| `text` | string | always |
| `url` | string | country |
| `lang` | language code | language |
| `seg_langs` | list of language codes | multilingual documents |
| `register` | `{label: probability}`, or one column per label | register |

A missing field only disables the step that needs it. `webmeta.coverage(records)` reports how many records each step can use. The full contract is in [`src/webmeta/schema.py`](src/webmeta/schema.py).

## Development
```bash
python -m venv .venv && .venv/bin/pip install -e ".[all,dev]"
.venv/bin/pytest
```
The test fixtures are synthetic; see [`tests/fixtures/README.md`](tests/fixtures/README.md).

## Licence
The code is licensed under the [Apache License 2.0](LICENSE). The bundled country table includes data from third-party sources under their own terms; see [NOTICE](NOTICE).
