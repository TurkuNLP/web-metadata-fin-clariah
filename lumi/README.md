# Running webmeta on LUMI

**webmeta works on samples, never on raw HPLT 4.** `hplt-sampler` (TurkuNLP)
is the only reader of the raw shards: it draws samples by corpus structure (language,
quality level, source shard), validates them and publishes them to the LUMI-O bucket
`lumi-462001491-private:hplt-samples`, never overwriting. Layout:
`<corpus>/<lang>/<wds>-n<N>-s<seed>/` with `samples.jsonl.zst`, the run record and
`SHA256SUMS`; the contract is in the bucket's `README.md`. Labels, content filters
and counts are webmeta's.

## Setup (once per clone)
```bash
cd <clone>
/usr/bin/python3 -m venv .venv
.venv/bin/pip install -e ".[zst]"
```
Use **`/usr/bin/python3`**, not the CSC AI module's `python3`, which runs in a container
that cannot see parts of `/appl/local`. `rclone` is not on `PATH` in batch jobs;
`run_sample.sh` uses its absolute path (or `module load lumio`).

## A run
See the header of [`run_sample.sh`](run_sample.sh). Example: register label counts
for the English 1M sample at the model's English threshold (0.40):
```bash
SAMPLE=v4/eng_Latn/all-n1000000-s20261015 \
WEBMETA_CMD="count --by lang,registers -o out/eng_registers.tsv" \
sbatch lumi/run_sample.sh
```
