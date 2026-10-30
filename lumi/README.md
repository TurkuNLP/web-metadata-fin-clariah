# Running webmeta on LUMI

To avoid implementing two pipelines doing the same job, `webmeta` works on samples, not raw HPLT 4. For obtaining a HPLT sample, using `hplt-sampler` is recommended. It draws samples by corpus structure (language, quality level, source shard), validates them, and publishes them to the LUMI-O bucket `lumi-462001491-private:hplt-samples` without overwrites. Layout: `<corpus>/<lang>/<wds>-n<N>-s<seed>/` with `samples.jsonl.zst`, the run record and `SHA256SUMS`. `webmeta` handles labels, content filters and counts.

## Setup (once per clone)
```bash
cd <clone>
/usr/bin/python3.11 -m venv .venv
.venv/bin/pip install -e ".[zst]"
```
Use **`/usr/bin/python3.11`** (plain `/usr/bin/python3` is 3.6, too old for webmeta), not the CSC AI module's `python3`, which runs in a container that cannot see parts of `/appl/local`. `rclone` is not on `PATH` in batch jobs; `run_sample.sh` uses its absolute path (or `module load lumio`).

## A run
See the header of [`run_sample.sh`](run_sample.sh). Example: register label counts for the English 1M sample at the model's English threshold (0.40):
```bash
SAMPLE=v4/eng_Latn/all-n1000000-s20261015 \
WEBMETA_CMD="count --by lang,registers -o out/eng_registers.tsv" \
sbatch lumi/run_sample.sh
```

## Building a dataset
[`build.sh`](build.sh) runs a study's settings file (see the main README, *Building a dataset*) over one or more samples, e.g. one pool per quality level:
```bash
SAMPLES="v4/eng_Latn/5-n8100000-s20261016 v4/eng_Latn/6-n3400000-s20261016" \
SETTINGS=examples/news_and_blogs.py OUT=out/news_and_blogs \
sbatch lumi/build.sh
```
Each sample is fetched once into `samples/` and checked against its `SHA256SUMS`; `CLEAN=1` removes the downloads afterwards. The job refuses to overwrite `OUT`. Labelling runs at about 3,000 documents per second on one core, so 18 M documents take about 1.5 hours.
