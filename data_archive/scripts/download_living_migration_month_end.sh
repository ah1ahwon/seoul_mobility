#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="$BASE_DIR/metadata/living_migration_month_end_manifest.csv"
DL="$BASE_DIR/scripts/download_seoul_bigdata_file.sh"
REFERER="https://data.seoul.go.kr/dataList/OA-22299/F/1/datasetView.do"

is_valid_zip() {
  python3 - "$1" <<'PY'
import sys
import zipfile
path = sys.argv[1]
try:
    with zipfile.ZipFile(path) as zf:
        bad = zf.testzip()
except zipfile.BadZipFile:
    raise SystemExit(1)
if bad:
    raise SystemExit(1)
PY
}

tail -n +2 "$MANIFEST" | while IFS=, read -r yyyymm filename seq; do
  output="$BASE_DIR/raw/$filename"
  if [ -s "$output" ]; then
    if is_valid_zip "$output"; then
      echo "skip existing valid ZIP: $yyyymm $filename"
      continue
    fi
    echo "remove corrupt ZIP and re-download: $yyyymm $filename"
    rm -f "$output"
  fi
  echo "download: $yyyymm $filename"
  "$DL" OA-22299 1 "$seq" "$output" "$REFERER"
done
