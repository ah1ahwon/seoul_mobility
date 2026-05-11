#!/usr/bin/env bash
# 서울시 GIS 데이터 다운로드 안내
# - 서울시 행정동 경계 shapefile → seoul_admin_dong_boundary.zip
# - 서울시 도시계획 용도지역지구도 shapefile → seoul_land_use_zone.zip
#
# 사용법:
#   bash data_archive/scripts/download_gis_data.sh
#
# 필요 패키지: geopandas>=0.14, shapely>=2.0
#   pip install geopandas shapely
#
# 분석 스크립트: summarize_land_use_by_dong()
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== GIS 데이터 다운로드 안내 ==="
echo ""
echo "[ 1 ] 서울시 행정동 경계 shapefile"
echo "  저장 경로: $BASE_DIR/raw/seoul_admin_dong_boundary.zip"
echo ""
echo "  다운로드 방법:"
echo "  A) 국가공간정보포털 (ngii.go.kr)"
echo "     → '행정구역(읍면동)' 또는 '법정동 경계' shapefile 검색 후 다운로드"
echo "  B) 통계청 SGIS (sgis.kostat.go.kr)"
echo "     → '통계지리서비스' > '행정경계' > 서울특별시 행정동 경계 다운로드"
echo "  C) 서울 열린데이터광장"
echo "     https://data.seoul.go.kr/dataList/OA-11677/S/1/datasetView.do"
echo ""
echo "[ 2 ] 서울시 도시계획 용도지역지구도"
echo "  저장 경로: $BASE_DIR/raw/seoul_land_use_zone.zip"
echo ""
echo "  다운로드 방법:"
echo "  A) 국토교통부 VWORLD (vworld.kr)"
echo "     → '도시계획정보' > '용도지역지구도' > 서울특별시 선택 후 다운로드"
echo "  B) 서울시 도시공간정보서비스"
echo "     http://gis.seoul.go.kr → 도시계획 > 용도지역"
echo "  C) 국가공간정보포털"
echo "     https://www.nsdi.go.kr → 도시계획 용도지역 검색"
echo ""
echo "파일을 각 경로에 배치한 후 python3 seoul_mobility_analysis.py 를 실행하면"
echo "자동으로 공간 결합이 수행됩니다."
echo ""
echo "주의: shapefile은 ZIP 파일 안에 .shp, .dbf, .prj 등이 함께 있어야 합니다."
