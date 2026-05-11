#!/usr/bin/env bash
# 서울시 우리마을가게 상권분석서비스 — 행정동별 추정매출 최신 분기 다운로드
# 출처: https://data.seoul.go.kr/dataList/OA-15568/S/1/datasetView.do
#
# 사용법:
#   bash data_archive/scripts/download_commercial_sales.sh
#
# 파일 위치: data_archive/raw/seoul_commercial_sales_latest.csv
# 분석 스크립트: summarize_sales_by_dong()
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT="$BASE_DIR/raw/seoul_commercial_sales_latest.csv"
REFERER="https://data.seoul.go.kr/dataList/OA-15568/S/1/datasetView.do"

if [ -s "$OUTPUT" ]; then
  echo "skip existing: $OUTPUT"
  exit 0
fi

echo "다운로드: 서울시 상권분석서비스 행정동별 추정매출..."
# infId=OA-15568, infSeq=3(최신분기), seq=1
# seq 값은 서울 열린데이터광장 OA-15568 페이지에서 확인 후 수정
"$BASE_DIR/scripts/download_seoul_bigdata_file.sh" \
  OA-15568 3 1 "$OUTPUT" "$REFERER"

echo "저장: $OUTPUT"
echo ""
echo "NOTE: seq 값이 맞지 않으면 파일 내용을 확인하세요."
echo "      서울 열린데이터광장 페이지에서 최신 분기의 seq를 확인 후 이 스크립트를 수정하세요."
