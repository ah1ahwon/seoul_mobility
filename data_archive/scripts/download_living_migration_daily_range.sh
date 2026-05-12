#!/usr/bin/env bash
# 수도권 생활이동 목적별 일별 ZIP을 날짜 범위로 다운로드.
#
# 기본 범위:
#   START_DATE=2023-01-01
#   END_DATE=2026-03-31
#
# 사용 예:
#   bash data_archive/scripts/download_living_migration_daily_range.sh
#   START_DATE=2025-01-01 END_DATE=2025-12-31 bash data_archive/scripts/download_living_migration_daily_range.sh
#   DRY_RUN=1 START_DATE=2025-01-01 END_DATE=2025-01-03 bash data_archive/scripts/download_living_migration_daily_range.sh
#
# 파일 위치:
#   data_archive/raw/seoul_purpose_admdong4_in_YYYYMMDD.zip
#
# 주의:
#   범위를 넓게 잡으면 파일 수와 용량이 매우 큽니다. 이미 있는 파일은 건너뜁니다.
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DL="$BASE_DIR/scripts/download_seoul_bigdata_file.sh"
REFERER="https://data.seoul.go.kr/dataList/OA-22299/F/1/datasetView.do"
START_DATE="${START_DATE:-2023-01-01}"
END_DATE="${END_DATE:-2026-03-31}"
DRY_RUN="${DRY_RUN:-0}"

dates="$(
  START_DATE="$START_DATE" END_DATE="$END_DATE" python3 - <<'PY'
import os
from datetime import date, timedelta

start = date.fromisoformat(os.environ["START_DATE"])
end = date.fromisoformat(os.environ["END_DATE"])
if end < start:
    raise SystemExit("END_DATE must be on or after START_DATE")

cur = start
while cur <= end:
    print(cur.strftime("%Y%m%d"))
    cur += timedelta(days=1)
PY
)"

echo "download range: $START_DATE ~ $END_DATE"
echo "target dir: $BASE_DIR/raw"

for ymd in $dates; do
  yyMMdd="${ymd:2:6}"
  filename="seoul_purpose_admdong4_in_${ymd}.zip"
  output="$BASE_DIR/raw/$filename"

  if [ -s "$output" ]; then
    echo "skip existing: $filename"
    continue
  fi

  if [ "$DRY_RUN" = "1" ]; then
    echo "would download: $filename"
    continue
  fi

  echo "download: $filename"
  if ! "$DL" OA-22299 1 "$yyMMdd" "$output" "$REFERER"; then
    echo "warning: download command failed: $filename"
    rm -f "$output"
    continue
  fi

  if ! python3 - "$output" <<'PY'
import sys
import zipfile
path = sys.argv[1]
try:
    with zipfile.ZipFile(path):
        pass
except zipfile.BadZipFile:
    raise SystemExit(1)
PY
  then
    echo "warning: invalid ZIP returned; removing: $filename"
    rm -f "$output"
  fi
done

echo "done"
