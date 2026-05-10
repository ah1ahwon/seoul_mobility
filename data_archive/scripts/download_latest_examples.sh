#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DL="$BASE_DIR/scripts/download_seoul_bigdata_file.sh"

"$DL" OA-12914 3 153 "$BASE_DIR/raw/CARD_SUBWAY_MONTH_202604.csv" "https://data.seoul.go.kr/dataList/OA-12914/S/1/datasetView.do"
"$DL" OA-12913 3 109 "$BASE_DIR/raw/bus_time_station_202604.csv" "https://data.seoul.go.kr/dataList/OA-12913/S/1/datasetView.do"
"$DL" OA-22299 1 260331 "$BASE_DIR/raw/seoul_purpose_admdong4_in_20260331.zip" "https://data.seoul.go.kr/dataList/OA-22299/F/1/datasetView.do"
"$DL" OA-22160 3 1 "$BASE_DIR/raw/seoul_admin_dong_area.zip" "https://data.seoul.go.kr/dataList/OA-22160/S/1/datasetView.do"
"$DL" OA-22266 1 30 "$BASE_DIR/raw/seoul_living_interest_groups_202512.xlsx" "https://data.seoul.go.kr/dataList/OA-22266/F/1/datasetView.do"
