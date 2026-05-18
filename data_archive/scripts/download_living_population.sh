#!/usr/bin/env bash
# 서울 생활인구 (내국인) — 행정동별 시간대별 추정 생활인구 최신 월 다운로드
# 출처: https://data.seoul.go.kr/dataList/OA-14991/A/1/datasetView.do
#
# 사용법:
#   bash data_archive/scripts/download_living_population.sh
#
# 파일 위치: data_archive/raw/seoul_living_population_latest.csv
# 분석 스크립트: summarize_population_ratio()
#
# 주의: 파일 크기가 크므로 (월 1~2 GB) 다운로드에 시간이 걸릴 수 있습니다.
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT="$BASE_DIR/raw/seoul_living_population_latest.csv"
TMP_ZIP="$BASE_DIR/raw/seoul_living_population_latest.zip"
REFERER="https://data.seoul.go.kr/dataList/OA-14991/A/1/datasetView.do"

if [ -s "$OUTPUT" ]; then
  echo "skip existing: $OUTPUT"
  exit 0
fi

echo "다운로드: 서울 생활인구 내국인 행정동 최신 월..."
# OA-14991 파일 다운로드 목록 기준: seq=2604는 2026년 4월 파일
"$BASE_DIR/scripts/download_seoul_bigdata_file.sh" \
  OA-14991 3 2604 "$TMP_ZIP" "$REFERER"

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
echo "NOTE: seq 값이 맞지 않으면 OA-14991 페이지에서 최신 월의 seq를 확인 후 수정하세요."
