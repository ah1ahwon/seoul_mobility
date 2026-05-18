#!/usr/bin/env bash
# 서울시 상권분석서비스 — 행정동별 추정매출 최신 연도 다운로드
# 출처: https://data.seoul.go.kr/dataList/OA-22175/A/1/datasetView.do
#
# 사용법:
#   bash data_archive/scripts/download_commercial_sales.sh
#
# 파일 위치: data_archive/raw/seoul_commercial_sales_latest.csv
# 분석 스크립트: summarize_sales_by_dong()
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT="$BASE_DIR/raw/seoul_commercial_sales_latest.csv"
TMP_ZIP="$BASE_DIR/raw/seoul_commercial_sales_latest.zip"
REFERER="https://data.seoul.go.kr/dataList/OA-22175/A/1/datasetView.do"

if [ -s "$OUTPUT" ]; then
  echo "skip existing: $OUTPUT"
  exit 0
fi

echo "다운로드: 서울시 상권분석서비스 행정동별 추정매출..."
# OA-22175 파일 다운로드 목록 기준: seq=6은 2024년 파일
"$BASE_DIR/scripts/download_seoul_bigdata_file.sh" \
  OA-22175 3 6 "$TMP_ZIP" "$REFERER"

python3 - "$TMP_ZIP" "$OUTPUT" <<'PY'
import sys
import zipfile
from pathlib import Path

zip_path = Path(sys.argv[1])
output = Path(sys.argv[2])

with zipfile.ZipFile(zip_path) as zf:
    csv_names = [name for name in zf.namelist() if name.lower().endswith(".csv")]
    if not csv_names:
        raise SystemExit(f"ZIP 내부 CSV 없음: {zip_path}")
    with zf.open(csv_names[0]) as src, output.open("wb") as dst:
        dst.write(src.read())
PY

rm -f "$TMP_ZIP"

echo "저장: $OUTPUT"
echo ""
echo "NOTE: seq 값이 맞지 않으면 OA-22175 페이지에서 최신 파일의 seq를 확인 후 수정하세요."
