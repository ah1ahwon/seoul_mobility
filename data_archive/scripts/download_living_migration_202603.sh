#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="$BASE_DIR/metadata/living_migration_202603_manifest.csv"
DL="$BASE_DIR/scripts/download_seoul_bigdata_file.sh"
REFERER="https://data.seoul.go.kr/dataList/OA-22299/F/1/datasetView.do"

tail -n +2 "$MANIFEST" | while IFS=, read -r filename seq; do
  output="$BASE_DIR/raw/$filename"
  if [ -s "$output" ]; then
    echo "skip existing: $filename"
    continue
  fi
  echo "download: $filename"
  "$DL" OA-22299 1 "$seq" "$output" "$REFERER"
done
