#!/bin/bash
# Run webmeta over one validated HPLT sample from LUMI-O.
#
# webmeta never reads raw HPLT 4 shards: hplt-sampler draws samples from them,
# validates them and publishes them to the LUMI-O bucket `hplt-samples`
# (layout <corpus>/<lang>/<wds>-n<N>-s<seed>/samples.jsonl.zst). This job
# fetches one sample to scratch (once) and runs a webmeta command on it.
#
#   SAMPLE=v4/eng_Latn/all-n1000000-s20261015 \
#   WEBMETA_CMD="count --by lang,registers -o out/eng_registers.tsv" \
#   sbatch lumi/run_sample.sh
#
#SBATCH --job-name=webmeta
#SBATCH --account=project_462001491
#SBATCH --partition=small
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --output=logs/%x_%j.out

set -euo pipefail
SAMPLE=${SAMPLE:?set SAMPLE, e.g. v4/eng_Latn/all-n1000000-s20261015}
WEBMETA_CMD=${WEBMETA_CMD:?set WEBMETA_CMD, e.g. "count -o out/counts.tsv"}
REMOTE=${REMOTE:-lumi-462001491-private:hplt-samples}
CACHE=${CACHE:-$PWD/samples}
VENV=${VENV:-$PWD/.venv}
RCLONE=${RCLONE:-/appl/lumi/SW/system/EB/lumio-ext-tools/1.1.0/bin/rclone}

mkdir -p logs out "$CACHE/$SAMPLE"
FILE="$CACHE/$SAMPLE/samples.jsonl.zst"
if [ ! -s "$FILE" ]; then
  "$RCLONE" copy "$REMOTE/$SAMPLE/" "$CACHE/$SAMPLE/"
  (cd "$CACHE/$SAMPLE" && sha256sum -c SHA256SUMS)
fi

# The subcommand comes first, then the input file, then its options.
set -- $WEBMETA_CMD
"$VENV/bin/webmeta" "$1" "$FILE" "${@:2}"
