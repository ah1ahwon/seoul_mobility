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

curl -L \
  -e "$REFERER_URL" \
  -X POST \
  -d "infId=$INF_ID" \
  -d "infSeq=$INF_SEQ" \
  -d "seq=$FILE_SEQ" \
  -d "seqNo=$FILE_SEQ" \
  "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?useCache=false" \
  -o "$OUTPUT_PATH"

