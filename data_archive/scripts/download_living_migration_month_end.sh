#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="$BASE_DIR/metadata/living_migration_month_end_manifest.csv"
DL="$BASE_DIR/scripts/download_seoul_bigdata_file.sh"
REFERER="https://data.seoul.go.kr/dataList/OA-22299/F/1/datasetView.do"

tail -n +2 "$MANIFEST" | while IFS=, read -r yyyymm filename seq; do
  output="$BASE_DIR/raw/$filename"
  if [ -s "$output" ]; then
    echo "skip existing: $yyyymm $filename"
    continue
  fi
  echo "download: $yyyymm $filename"
  "$DL" OA-22299 1 "$seq" "$output" "$REFERER"
done
