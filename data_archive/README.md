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
| `raw/seoul_purpose_admdong4_in_202603*.zip` | 수도권 생활이동 연령별 OD 목적별 내국인 데이터, 2026년 3월 30개 일자 (28일 제외) |
| `raw/seoul_purpose_admdong4_in_YYYYMMDD.zip` | 수도권 생활이동 월말 스냅샷, 2023년 1월~2026년 3월 39개 파일 (장기 추세 분석용) |
| `raw/seoul_admin_dong_area.zip` | 서울시 상권분석서비스 영역-행정동, 행정동 코드 매핑용 |
| `raw/seoul_living_interest_groups_202512.xlsx` | 서울 시민생활 데이터 행정동단위 10개 관심집단수, 2030 자취/거주성 보정용 |
| `raw/seoul_admin_dong_boundary.zip` | 필수 파일. 역·정류장 좌표와 행정동 공간 결합용 |
| `raw/subway_station_coordinates.csv` | 필수 파일. 지하철역 좌표. `station_name`과 위경도 또는 x/y 필요 |
| `raw/bus_stop_coordinates.csv` | 필수 파일. 버스정류장 좌표. `station_id`, `ars_id`, 또는 `station_name`과 위경도 또는 x/y 필요 |
| `raw/seoul_commercial_sales_latest.csv` | 필수 파일. 행정동별 추정매출 |
| `raw/seoul_living_population_latest.csv` | 필수 파일. 행정동별 시간대별 생활인구 |

## Metadata Files

| File | Description |
|---|---|
| `metadata/living_migration_month_end_manifest.csv` | 월말 스냅샷 아카이브 목록 (yyyymm, filename, seq 컬럼). 2023-01~2026-03, 39개 파일. `download_living_migration_month_end.sh`와 분석 스크립트가 이 목록을 기준으로 파일을 로드함 |
| `metadata/living_migration_202603_manifest.csv` | 2026년 3월 일별 파일 목록 (filename, seq 컬럼). 30개 일자(28일 제외). `download_living_migration_202603.sh`에서 참조 |
| `metadata/source_inventory.csv` | 전체 데이터 소스 인벤토리 (infId, 데이터셋명, 용도 등) |

## Sources

- 수도권 생활이동: https://data.seoul.go.kr/dataList/OA-22299/F/1/datasetView.do
- 지하철 승하차: https://data.seoul.go.kr/dataList/OA-12914/S/1/datasetView.do
- 버스 승하차: https://data.seoul.go.kr/dataList/OA-12913/S/1/datasetView.do
- 상권분석서비스 영역-행정동: https://data.seoul.go.kr/dataList/OA-22160/S/1/datasetView.do
- 서울 시민생활 데이터: https://data.seoul.go.kr/dataVisual/seoul/seoulLiving.do
- 행정동단위 10개 관심집단수: https://data.seoul.go.kr/dataList/OA-22266/F/1/datasetView.do

## Scripts

| Script | Description |
|---|---|
| `scripts/download_seoul_bigdata_file.sh` | 서울 열린데이터광장 단일 파일 다운로드 공통 함수 |
| `scripts/download_latest_examples.sh` | 지하철·버스·행정동·관심집단 최신 파일 샘플 다운로드 |
| `scripts/download_living_migration_month_end.sh` | manifest 기준으로 2023-01~2026-03 월말 스냅샷 39개 다운로드 |
| `scripts/download_living_migration_202603.sh` | manifest 기준으로 2026년 3월 일별 30개 파일 다운로드 |
| `scripts/download_living_migration_daily_range.sh` | 날짜 범위 기준으로 생활이동 일별 ZIP 다운로드. 월 전체 집계 커버리지 확대용 |
| `scripts/download_commercial_sales.sh` | 서울시 상권분석서비스 행정동별 추정매출 최신 분기 다운로드 (OA-15568) |
| `scripts/download_living_population.sh` | 서울 생활인구 행정동별 시간대별 최신 월 다운로드 (OA-14939) |
| `scripts/download_bjdong_mapping.sh` | 행정동 → 법정동 코드 매핑 파일 준비 안내 |
| `scripts/download_gis_data.sh` | 서울시 행정동 경계·용도지역 shapefile 다운로드 안내 (geopandas 필요) |

## Secret Handling

`data_archive/.env`는 로컬 실행용이며 Git에 올리지 않습니다. 공유용 템플릿은 `data_archive/.env.example`입니다.
