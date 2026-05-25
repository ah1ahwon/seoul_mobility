#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 5 ]; then
  echo "Usage: $0 INF_ID INF_SEQ FILE_SEQ OUTPUT_PATH REFERER_URL" >&2
  exit 1
fi

INF_ID="$1"
INF_SEQ="$2"
FILE_SEQ="$3"
OUTPUT_PATH="$4"
REFERER_URL="$5"

mkdir -p "$(dirname "$OUTPUT_PATH")"

curl -L \
  -e "$REFERER_URL" \
  -X POST \
  -d "infId=$INF_ID" \
  -d "infSeq=$INF_SEQ" \
  -d "seq=$FILE_SEQ" \
  -d "seqNo=$FILE_SEQ" \
  "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?useCache=false" \
  -o "$OUTPUT_PATH"

if [ ! -s "$OUTPUT_PATH" ]; then
  echo "download failed or empty file: $OUTPUT_PATH" >&2
  rm -f "$OUTPUT_PATH"
  exit 1
fi

case "$OUTPUT_PATH" in
  *.zip)
    if ! python3 - "$OUTPUT_PATH" <<'PY'
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
    then
      echo "downloaded file is not a valid ZIP: $OUTPUT_PATH" >&2
      rm -f "$OUTPUT_PATH"
      exit 1
    fi
    ;;
esac
