#!/usr/bin/env bash
# 서울 생활인구 (내국인) — 행정동별 시간대별 추정 생활인구 최신 월 다운로드
# 출처: https://data.seoul.go.kr/dataList/OA-14939/S/1/datasetView.do
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
REFERER="https://data.seoul.go.kr/dataList/OA-14939/S/1/datasetView.do"

if [ -s "$OUTPUT" ]; then
  echo "skip existing: $OUTPUT"
  exit 0
fi

echo "다운로드: 서울 생활인구 내국인 최신 월..."
# infId=OA-14939, infSeq=3(최신), seq=1
# seq 값은 서울 열린데이터광장 OA-14939 페이지에서 확인 후 수정
"$BASE_DIR/scripts/download_seoul_bigdata_file.sh" \
  OA-14939 3 1 "$OUTPUT" "$REFERER"

echo "저장: $OUTPUT"
echo ""
echo "NOTE: 서울 생활인구 파일은 압축(ZIP) 또는 CSV 형식으로 제공됩니다."
echo "      ZIP으로 받은 경우 압축 해제 후 seoul_living_population_latest.csv로 저장하세요."
echo "      seq 값은 OA-14939 페이지의 최신 월을 확인 후 수정하세요."
