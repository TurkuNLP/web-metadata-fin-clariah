#!/bin/bash
# Build a dataset with `webmeta build` from one or more validated samples on LUMI-O.
#
# Fetches each sample from the bucket `hplt-samples` (published by hplt-sampler,
# layout <corpus>/<lang>/<wds>-n<N>-s<seed>/), checks its SHA256SUMS, and runs
# the study's settings file over all of them. Refuses to overwrite OUT.
#
#   SAMPLES="v4/eng_Latn/5-n8100000-s20261016 v4/eng_Latn/6-n3400000-s20261016" \
#   SETTINGS=examples/news_and_blogs.py OUT=out/news_and_blogs \
#   sbatch lumi/build.sh
#
# CLEAN=1 deletes the downloaded samples afterwards (the bucket keeps them).
#
#SBATCH --job-name=webmeta-build
#SBATCH --account=project_462001491
#SBATCH --partition=small
#SBATCH --cpus-per-task=2
#SBATCH --mem=32G
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x_%j.out

set -euo pipefail
SAMPLES=${SAMPLES:?set SAMPLES: space-separated sample paths in the bucket}
SETTINGS=${SETTINGS:?set SETTINGS: the study settings file}
OUT=${OUT:?set OUT: output directory}
REMOTE=${REMOTE:-lumi-462001491-private:hplt-samples}
CACHE=${CACHE:-$PWD/samples}
VENV=${VENV:-$PWD/.venv}
RCLONE=${RCLONE:-/appl/lumi/SW/system/EB/lumio-ext-tools/1.1.0/bin/rclone}

[ -f "$SETTINGS" ] || { echo "settings file not found: $SETTINGS (compute nodes cannot see the login node's /tmp)" >&2; exit 1; }
[ -e "$OUT" ] && { echo "refusing to overwrite $OUT" >&2; exit 1; }
mkdir -p logs
FILES=()
for S in $SAMPLES; do
  mkdir -p "$CACHE/$S"
  [ -s "$CACHE/$S/samples.jsonl.zst" ] || "$RCLONE" copy "$REMOTE/$S/" "$CACHE/$S/"
  (cd "$CACHE/$S" && sha256sum --quiet -c SHA256SUMS)
  FILES+=("$CACHE/$S/samples.jsonl.zst")
done
"$VENV/bin/webmeta" build "${FILES[@]}" --settings "$SETTINGS" -o "$OUT"
if [ "${CLEAN:-0}" = 1 ]; then
  for S in $SAMPLES; do rm -rf "${CACHE:?}/$S"; done
fi
