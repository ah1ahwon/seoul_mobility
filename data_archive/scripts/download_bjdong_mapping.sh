#!/usr/bin/env bash
# 행정동코드 → 법정동코드 매핑 파일 생성
# 출처: 행정안전부 행정동 코드 / 통계청 법정동 코드
#
# 사용법:
#   bash data_archive/scripts/download_bjdong_mapping.sh
#
# 파일 위치: data_archive/metadata/bjdong_admdong_mapping.csv
# 컬럼: admdong_cd, bjdong_cd, bjdong_nm
# 분석 스크립트: load_bjdong_mapping()
#
# 옵션 1 (행정안전부 주소 API — 자동):
#   행정안전부 도로명주소 개발자센터에서 법정동 코드 전체 자료를 받아 가공합니다.
#   https://www.juso.go.kr/addrlink/devAddrLinkRequestUse.do
#
# 옵션 2 (수동):
#   행정안전부 공공데이터포털에서 '법정동 코드' 또는 '행정동 코드' 파일을 받아
#   아래 형식의 CSV로 변환하세요.
#   admdong_cd: 8자리 행정동 코드 (앞 5자리 = 시군구 코드)
#   bjdong_cd:  10자리 법정동 코드
#   bjdong_nm:  법정동 명칭 (예: 잠실동, 성수1가동)
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT="$BASE_DIR/metadata/bjdong_admdong_mapping.csv"

if [ -s "$OUTPUT" ]; then
  echo "skip existing: $OUTPUT"
  exit 0
fi

echo "법정동 매핑 파일을 수동으로 준비해야 합니다."
echo ""
echo "방법 1 (행정안전부 공공데이터포털):"
echo "  1. https://www.data.go.kr 에서 '행정동 법정동 코드' 검색"
echo "  2. 최신 CSV를 받아 다음 형식으로 변환:"
echo "     admdong_cd,bjdong_cd,bjdong_nm"
echo "     11010101,1101010100,청운효자동"
echo "     ..."
echo "  3. $OUTPUT 에 저장"
echo ""
echo "방법 2 (SGIS 통계지리서비스):"
echo "  https://sgis.kostat.go.kr 에서 행정구역 코드 대응표 다운로드"
echo ""
echo "기본 분석 실행에서는 이 파일이 필수입니다."
echo "개발용 부분 실행(SEOUL_ALLOW_PARTIAL=1)에서만 이름 패턴 근사치(잠실6동→잠실동)로 대체됩니다."
