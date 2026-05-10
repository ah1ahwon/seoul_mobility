# Data Archive

이 폴더는 서울 2030 이동/교통 분석에 사용한 원천 데이터와 데이터셋 메타데이터를 보관합니다.

## Folders

- `raw/`: 원천 파일
- `metadata/`: 서울 열린데이터광장 데이터셋 페이지 및 출처 인벤토리
- `notes/`: 데이터 해석 및 분석 주의사항
- `scripts/`: 서울 열린데이터광장 파일 재다운로드 스크립트

## Raw Files

| File | Description |
|---|---|
| `raw/CARD_SUBWAY_MONTH_202604.csv` | 서울시 지하철호선별 역별 승하차 인원, 2026년 4월 |
| `raw/bus_time_station_202604.csv` | 서울시 버스노선별 정류장별 시간대별 승하차 인원, 2026년 4월 |
| `raw/seoul_purpose_admdong4_in_20260331.zip` | 수도권 생활이동 연령별 OD 목적별 내국인 데이터, 2026년 3월 31일 |
| `raw/seoul_admin_dong_area.zip` | 서울시 상권분석서비스 영역-행정동, 행정동 코드 매핑용 |
| `raw/seoul_living_interest_groups_202512.xlsx` | 서울 시민생활 데이터 행정동단위 10개 관심집단수, 2030 자취/거주성 보정용 |

## Sources

- 수도권 생활이동: https://data.seoul.go.kr/dataList/OA-22299/F/1/datasetView.do
- 지하철 승하차: https://data.seoul.go.kr/dataList/OA-12914/S/1/datasetView.do
- 버스 승하차: https://data.seoul.go.kr/dataList/OA-12913/S/1/datasetView.do
- 상권분석서비스 영역-행정동: https://data.seoul.go.kr/dataList/OA-22160/S/1/datasetView.do
- 서울 시민생활 데이터: https://data.seoul.go.kr/dataVisual/seoul/seoulLiving.do
- 행정동단위 10개 관심집단수: https://data.seoul.go.kr/dataList/OA-22266/F/1/datasetView.do

## Secret Handling

`data_archive/.env`는 로컬 실행용이며 Git에 올리지 않습니다. 공유용 템플릿은 `data_archive/.env.example`입니다.
