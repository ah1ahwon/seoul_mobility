#!/usr/bin/env bash
# 수도권 생활이동 성·연령별 도착지 기준 월별 ZIP(OA-22298)을 다운로드.
#
# 사용 예:
#   MONTHS=202603 bash data_archive/scripts/download_age_gender_destination_months.sh
#   START_MONTH=202501 END_MONTH=202603 bash data_archive/scripts/download_age_gender_destination_months.sh
#   DRY_RUN=1 START_MONTH=202601 END_MONTH=202603 bash data_archive/scripts/download_age_gender_destination_months.sh
#
# 파일 위치:
#   data_archive/raw/seoul_purpose_admdong1_in_YYYYMM.zip
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DL="$BASE_DIR/scripts/download_seoul_bigdata_file.sh"
REFERER="https://data.seoul.go.kr/dataList/OA-22298/F/1/datasetView.do"
DRY_RUN="${DRY_RUN:-0}"

if [ -n "${MONTHS:-}" ]; then
  months="$MONTHS"
else
  START_MONTH="${START_MONTH:-202603}"
  END_MONTH="${END_MONTH:-202603}"
  months="$(
    START_MONTH="$START_MONTH" END_MONTH="$END_MONTH" python3 - <<'PY'
import os

start = os.environ["START_MONTH"]
end = os.environ["END_MONTH"]
sy, sm = int(start[:4]), int(start[4:6])
ey, em = int(end[:4]), int(end[4:6])
if (ey, em) < (sy, sm):
    raise SystemExit("END_MONTH must be on or after START_MONTH")

y, m = sy, sm
while (y, m) <= (ey, em):
    print(f"{y:04d}{m:02d}")
    m += 1
    if m == 13:
        y += 1
        m = 1
PY
  )"
fi

echo "target dir: $BASE_DIR/raw"

for yyyymm in $months; do
  filename="seoul_purpose_admdong1_in_${yyyymm}.zip"
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
  if ! "$DL" OA-22298 1 "$yyyymm" "$output" "$REFERER"; then
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
