# 2030 이동 기반 서울 상권 후보 분석 플로우

이 문서는 현재 프로젝트에서 실제로 사용한 raw 데이터, 사용 컬럼, 전처리 방식, 점수 계산 방식, 최종 산출물의 의미를 정리한 분석 방법론 문서입니다.

## 1. 분석 목적

초기 목표는 서울 내에서 2030세대의 이동 신호가 강한 행정동을 찾는 것이었다.

다만 1차 분석 결과에서 신림동, 화양동, 안암동, 신촌동처럼 대학가·고시촌·원룸 밀집지가 상위에 많이 등장했다. 이는 실제 상권 방문이라기보다 2030 자취/거주지 효과일 수 있다.

따라서 현재 분석은 다음 질문으로 수정되었다.

```text
2030이 많이 도착하지만,
단순 자취/거주지 효과가 아닌 방문 목적성이 강한 행정동은 어디인가?
```

이를 위해 이동 데이터에 2030 1인가구 거주성 지표를 결합해 다음 두 그룹을 분리한다.

- 방문 상권 후보
- 2030 자취/거주성 분리 대상

## 2. 사용 Raw 데이터

### 2.1 수도권 생활이동 OD 데이터

파일:

```text
data_archive/raw/seoul_purpose_admdong4_in_202603*.zip
```

출처:

```text
수도권 생활이동 (연령별, 출발-도착지 기준)-내국인 목적별
https://data.seoul.go.kr/dataList/OA-22299/F/1/datasetView.do
```

분석 내 역할:

- 2030 도착 이동량 계산
- 전체 이동 중 2030 비중 계산
- 출발지 다양성 계산
- 저녁 시간대 이동 비중 계산
- 평균 이동 시간/거리 계산
- 기본 이동 점수 `mobility_score` 산출

현재 분석 기간:

```text
2026년 3월 1일~31일 중 원천 페이지에서 제공된 30개 일자
```

2026년 3월 28일 파일은 원천 목록에 없어 제외되었다.

실제 사용 컬럼:

| 원본 컬럼 | 의미 | 분석 사용 방식 |
|---|---|---|
| `o_admdong_cd` | 출발 행정동 코드 | 도착 행정동별 출발지 다양성 계산 |
| `d_admdong_cd` | 도착 행정동 코드 | 분석의 기본 단위 |
| `st_time_cd` | 이동 시작 시간대 | 6~8시(오전), 9~17시(오후), 18~23시(저녁), 23~5시(심야) 비중 계산 |
| `move_dist` | 이동 거리 | 2030 가중 평균 이동 거리 계산 |
| `move_time` | 이동 시간 | 2030 가중 평균 이동 시간 계산 |
| `2030_cnt` | 20·30대 이동량 | 핵심 종속 지표 |
| `total_cnt` | 전체 이동량 | 2030 비중 계산 |
| `etl_ymd` | 기준일 | 요일 분류 및 월별 스냅샷 기준일 확인 |

사용하지 않은 컬럼:

- `0010_cnt`
- `4050_cnt`
- `60plus_cnt`
- 기타 목적/수단 세부 컬럼은 현재 코드에서는 사용하지 않음

현재 분석에서는 도착지가 서울 행정동 코드(`11`로 시작)이고, 행정동명 매핑이 가능한 행정동만 남긴다.

### 2.2 서울시 상권분석서비스 영역-행정동

파일:

```text
data_archive/raw/seoul_admin_dong_area.zip
```

출처:

```text
서울시 상권분석서비스(영역-행정동)
https://data.seoul.go.kr/dataList/OA-22160/S/1/datasetView.do
```

분석 내 역할:

- 생활이동의 `d_admdong_cd`를 행정동명으로 변환
- 서울 행정동만 필터링
- 행정동 중심 좌표를 보조 컬럼으로 저장

실제 사용 컬럼:

| 원본 컬럼 | 의미 | 분석 사용 방식 |
|---|---|---|
| `ADSTRD_CD` | 행정동 코드 | `d_admdong_cd`와 매핑 |
| `ADSTRD_NM` | 행정동명 | 결과 해석용 |
| `XCNTS_VALU` | 중심 X 좌표 | 보조 출력 |
| `YDNTS_VALU` | 중심 Y 좌표 | 보조 출력 |
| `RELM_AR` | 면적 | 보조 출력 |

비고:

- 원천 파일은 shapefile ZIP이지만, 현재 코드는 DBF만 표준 라이브러리로 읽어 코드/명칭을 추출한다.
- geopandas, fiona 같은 공간분석 패키지는 사용하지 않는다.

### 2.3 서울 시민생활 데이터 - 행정동단위 10개 관심집단수

파일:

```text
data_archive/raw/seoul_living_interest_groups_202512.xlsx
```

출처:

```text
서울 시민생활 데이터
https://data.seoul.go.kr/dataVisual/seoul/seoulLiving.do

행정동단위 10개 관심집단수
https://data.seoul.go.kr/dataList/OA-22266/F/1/datasetView.do
```

분석 내 역할:

- 2030 자취/거주성 보정 지표 생성
- 기존 이동 점수에서 거주지 효과를 분리

실제 사용 컬럼:

| 원본 컬럼 | 의미 | 분석 사용 방식 |
|---|---|---|
| `행정동코드` | 시민생활 데이터 기준 행정동 코드 | 보조 저장 |
| `자치구` | 자치구명 | 생활이동 결과와 매칭 |
| `행정동명` | 행정동명 | 생활이동 결과와 매칭 |
| `성별` | 성별 코드 | 남녀 합산 |
| `연령대` | 5세 단위 연령대 | 20, 25, 30, 35만 사용 |
| `총인구` | 추정 총인구 | 2030 인구 규모 계산 |
| `1인가구수` | 추정 1인가구수 | 2030 자취/거주성 핵심 지표 |
| `휴일 외출이 적은 집단` | 휴일 외출 적은 집단 | 거주성 보조 지표 |
| `외출이 매우 적은 집단(전체)` | 외출 매우 적은 집단 | 거주성 보조 지표 |

사용 연령대:

```text
20, 25, 30, 35
```

이 네 구간을 합쳐 2030으로 정의한다.

비고:

- XLSX 파일은 `openpyxl` 없이 표준 라이브러리로 직접 읽는다.
- 이유는 분석 환경을 가볍게 유지하기 위해서다.

### 2.4 서울시 지하철호선별 역별 승하차 인원

파일:

```text
data_archive/raw/CARD_SUBWAY_MONTH_202604.csv
```

출처:

```text
서울시 지하철호선별 역별 승하차 인원 정보
https://data.seoul.go.kr/dataList/OA-12914/S/1/datasetView.do
```

분석 내 역할:

- 후보 해석용 교통 보조지표
- 지하철역별 월간 승하차량, 주말 비중 계산

실제 사용 컬럼:

| 원본 컬럼 | 의미 | 분석 사용 방식 |
|---|---|---|
| `사용일자` | 이용일자 | 날짜/요일/주말 여부 계산 |
| `노선명` | 지하철 노선 | 현재는 보조 컬럼 |
| `역명` | 역명 | 역별 집계 단위 |
| `승차총승객수` | 승차 인원 | 역별 합산 |
| `하차총승객수` | 하차 인원 | 역별 합산 |
| `등록일자` | 등록일 | 보조 컬럼 |

생성 컬럼:

| 생성 컬럼 | 의미 |
|---|---|
| `board_count` | 승차 인원 |
| `alight_count` | 하차 인원 |
| `total_count` | 승차+하차 |
| `weekday` | 요일 |
| `is_weekend` | 주말 여부 |
| `subway_weekend_share` | 역별 전체 승하차 중 주말 비중 |

주의:

- 현재 지하철 데이터는 행정동과 공간 결합하지 않았다.
- 따라서 후보 행정동을 설명하는 보조 맥락으로만 사용한다.

### 2.5 서울시 상권분석서비스 행정동별 추정매출 (선택)

파일:

```text
data_archive/raw/seoul_commercial_sales_latest.csv
```

출처:

```text
서울시 상권분석서비스 (영역-행정동별 추정매출)
https://data.seoul.go.kr/dataList/OA-15568/S/1/datasetView.do
```

분석 내 역할:

- 단순 통행/경유지가 아닌 실제 소비가 일어나는 행정동 식별
- `commercial_potential_score` 산출에 사용

실제 사용 컬럼:

| 원본 컬럼 | 의미 | 분석 사용 방식 |
|---|---|---|
| `ADSTRD_NM` | 행정동명 | 이동 데이터와 매칭 |
| 매출 합계 컬럼 | 추정 매출액 | `total_sales`, `sales_per_store`, `food_sales_ratio` 생성 |

비고:

- 파일이 없으면 해당 요소를 건너뛰고 나머지 점수만으로 계산한다.
- 다운로드: `bash data_archive/scripts/download_commercial_sales.sh`

### 2.6 서울 생활인구 (내국인) 행정동별 시간대별 (선택)

파일:

```text
data_archive/raw/seoul_living_population_latest.csv
```

출처:

```text
서울 생활인구 (내국인)
https://data.seoul.go.kr/dataList/OA-14939/S/1/datasetView.do
```

분석 내 역할:

- 2030 유동인구 / 상주인구 비율 계산 → 실제 외부 유입 성격 파악
- `daytime_influx_ratio = 낮 시간대 2030 추정인구 / 심야 시간대 2030 추정인구`

비고:

- 월 1~2 GB 규모의 대용량 파일이다.
- 파일이 없으면 해당 요소를 중립값으로 대체한다.
- 다운로드: `bash data_archive/scripts/download_living_population.sh`

### 2.7 서울시 행정동 경계 + 도시계획 용도지역지구도 shapefile (선택)

파일:

```text
data_archive/raw/seoul_admin_dong_boundary.zip   ← 행정동 경계
data_archive/raw/seoul_land_use_zone.zip         ← 용도지역지구도
```

출처:

```text
행정동 경계: 국가공간정보포털(NSDI) / 통계청 SGIS / 서울 열린데이터광장 OA-11677
용도지역: 국토교통부 VWORLD / 서울시 도시공간정보서비스 / 국가공간정보포털
```

분석 내 역할:

- 행정동별 토지 유형 비중 계산 (`commercial_zone_ratio`, `residential_zone_ratio` 등)
- `commercial_potential_score` 산출에 사용

비고:

- `geopandas>=0.14`, `shapely>=2.0` 설치 필요: `pip install geopandas shapely`
- 파일 또는 패키지가 없으면 건너뛰고 나머지 요소만으로 점수 계산한다.
- 안내: `bash data_archive/scripts/download_gis_data.sh`

### 2.8 행정동 → 법정동 코드 매핑 (선택)

파일:

```text
data_archive/metadata/bjdong_admdong_mapping.csv
```

컬럼: `admdong_cd`, `bjdong_cd`, `bjdong_nm`

비고:

- 파일이 없으면 행정동명에서 숫자 접미사를 제거하는 패턴 근사치를 사용한다.
  - 예: `잠실6동` → `잠실동`, `성수2가3동` → `성수2가동`
- 행정안전부/통계청 코드 대응표에서 준비: `bash data_archive/scripts/download_bjdong_mapping.sh`

### 2.9 서울시 버스노선별 정류장별 시간대별 승하차 인원

파일:

```text
data_archive/raw/bus_time_station_202604.csv
```

출처:

```text
서울시 버스노선별 정류장별 시간대별 승하차 인원 정보
https://data.seoul.go.kr/dataList/OA-12913/S/1/datasetView.do
```

분석 내 역할:

- 후보 해석용 교통 보조지표
- 정류장별 월간 승하차량
- 시간대별 승하차 패턴

실제 사용 컬럼:

| 원본 컬럼 | 의미 | 분석 사용 방식 |
|---|---|---|
| `사용년월` | 기준 월 | 보조 컬럼 |
| `노선번호` | 버스 노선번호 | 노선 수 계산 |
| `노선명` | 버스 노선명 | 보조 컬럼 |
| `표준버스정류장ID` | 정류장 ID | 보조 컬럼 |
| `버스정류장ARS번호` | ARS 정류장 번호 | 보조 컬럼 |
| `역명` | 정류장명 | 정류장별 집계 단위 |
| `0시승차총승객수`~`23시승차총승객수` | 시간대별 승차 인원 | long format 변환 |
| `0시하차총승객수`~`23시하차총승객수` | 시간대별 하차 인원 | long format 변환 |

생성 컬럼:

| 생성 컬럼 | 의미 |
|---|---|
| `board_total` | 정류장/노선별 전체 승차 |
| `alight_total` | 정류장/노선별 전체 하차 |
| `total_count` | 승차+하차 |
| `hour` | 시간대 |
| `route_count` | 정류장별 노선 수 |

주의:

- 원본 CSV는 CP949 인코딩으로 읽는다.
- 현재 버스 데이터도 행정동과 공간 결합하지 않았다.

## 3. 전체 분석 플로우

### Step 1. 원천 데이터 아카이빙

`data_archive/raw/`에 원천 데이터를 로컬 보관한다.

단, 원천 파일은 GitHub에 올리지 않는다. `.gitignore`에서 제외한다.

```text
data_archive/raw/*
!data_archive/raw/.gitkeep
```

새 환경에서는 다음 스크립트로 샘플 원천 데이터를 다시 받을 수 있다.

```bash
bash data_archive/scripts/download_latest_examples.sh
```

월별 추세 분석용 생활이동 월말 스냅샷은 다음 스크립트로 받는다.

```bash
bash data_archive/scripts/download_living_migration_month_end.sh
```

월말 스냅샷 목록은 아래 manifest에 저장한다.

```text
data_archive/metadata/living_migration_month_end_manifest.csv
```

### Step 2. 행정동 코드 매핑

`seoul_admin_dong_area.zip`의 DBF에서 다음 컬럼을 추출한다.

```text
ADSTRD_CD
ADSTRD_NM
XCNTS_VALU
YDNTS_VALU
RELM_AR
```

이를 통해 생활이동의 도착 행정동 코드를 행정동명으로 바꾼다.

### Step 3. 2030 생활이동 요약

두 종류의 생활이동 요약을 만든다.

| 구분 | 사용 파일 | 목적 |
|---|---|---|
| 2026년 3월 상세 분석 | `seoul_purpose_admdong4_in_202603*.zip` 30개 일자 | 최신 구간의 안정적인 행정동 후보 도출 |
| 월별 추세 분석 | 2023년 1월~2026년 3월 월말 스냅샷 39개 | 긴 기간의 반복 강세/변화 방향 확인 |

생활이동 ZIP을 순차적으로 읽고, 각 ZIP 내부 CSV를 chunk 단위로 처리한다.

도착 행정동별로 다음 값을 집계한다.

| 생성 지표 | 계산 방식 |
|---|---|
| `cnt_2030` | 도착 행정동별 `2030_cnt` 합계 |
| `avg_daily_2030` | `cnt_2030 / date_count` |
| `date_count` | 분석에 사용한 생활이동 ZIP 파일 수 |
| `active_days` | 해당 행정동에 2030 이동이 관측된 고유 일수 |
| `total_cnt` | 도착 행정동별 `total_cnt` 합계 |
| `share_2030` | `cnt_2030 / total_cnt` |
| `origin_diversity` | 2030 이동이 있는 출발 행정동 수 |
| `evening_2030_cnt` | 18~23시 2030 이동량 |
| `evening_2030_ratio` | `evening_2030_cnt / cnt_2030` |
| `morning_2030_cnt` | 6~8시 2030 이동량 |
| `morning_2030_ratio` | `morning_2030_cnt / cnt_2030` |
| `afternoon_2030_cnt` | 9~17시 2030 이동량 |
| `afternoon_2030_ratio` | `afternoon_2030_cnt / cnt_2030` |
| `late_night_2030_cnt` | 23~5시 2030 이동량 |
| `late_night_2030_ratio` | `late_night_2030_cnt / cnt_2030` |
| `weekday_2030_cnt` | 월~목(0~3) 2030 이동량 |
| `weekday_2030_ratio` | `weekday_2030_cnt / cnt_2030` |
| `friday_2030_cnt` | 금요일(4) 2030 이동량 |
| `friday_2030_ratio` | `friday_2030_cnt / cnt_2030` |
| `weekend_2030_cnt` | 토~일(5~6) 2030 이동량 |
| `weekend_2030_ratio` | `weekend_2030_cnt / cnt_2030` |
| `avg_move_time_2030` | 2030 이동량 가중 평균 이동 시간 |
| `avg_move_dist_2030` | 2030 이동량 가중 평균 이동 거리 |

월별 추세 분석에서는 월말 스냅샷의 요일 효과를 파악하기 위해 다음 컬럼이 추가된다.

| 생성 지표 | 계산 방식 |
|---|---|
| `snapshot_date_str` | 해당 월 스냅샷의 기준일 (`etl_ymd` 기반) |
| `snapshot_weekday` | 기준일 요일 (예: `Monday`, `Friday`) |
| `is_weekend_snapshot` | 기준일이 토/일이면 `True` |

주의: 스냅샷 기준일이 금요일이면 야간·여가 이동이 과대 추정되고, 화요일이면 과소 추정될 수 있다. 월간 비교 시 `snapshot_weekday`와 `is_weekend_snapshot`을 확인하여 요일 편향을 감안해야 한다.

기본 이동 점수:

```text
mobility_score =
  z(log1p(cnt_2030))
+ z(share_2030)
+ z(log1p(origin_diversity))
+ z(evening_2030_ratio)
```

해석:

- 값이 높을수록 2030 도착 신호가 강하다.
- 단, 이 점수만 보면 자취/거주지 효과가 섞인다.

월별 추세 분석에서는 같은 점수식을 `yyyymm`별로 따로 계산한다. 전체 이동량이 계절이나 월별로 달라져도, 같은 월 안에서 상대적으로 강한 행정동을 비교하기 위해서다.

### Step 3-2. 요일·시간대별 방문 패턴 분류

`classify_visit_pattern()` 함수가 도착 행정동별로 방문 성격을 분류한다.

전체 행정동 분포의 60번째 백분위수를 기준 임계값으로 사용한다.

| 판단 기준 | 임계값 |
|---|---|
| `weekend_th` | `weekend_2030_ratio` 60th percentile |
| `weekday_th` | `weekday_2030_ratio` 60th percentile |
| `evening_th` | `evening_2030_ratio` 60th percentile |
| `late_night_th` | `late_night_2030_ratio` 60th percentile |

분류 결과:

| `visit_pattern_type` | 조건 |
|---|---|
| `목적 방문형` | 주말 비중 높음 AND 저녁/심야 비중 높음 |
| `생활 밀착형` | 평일 비중 높음 AND 주말 비중 낮음 |
| `복합형` | 주말 비중 높음 AND 평일 비중 높음 |
| `불명확` | 위 조건에 해당하지 않음 |

### Step 3-3. 선택적 레이어 데이터 로드

다음 세 함수는 각 선택 데이터 파일이 존재할 때만 결과를 반환하고, 없으면 빈 DataFrame을 반환한다.

| 함수 | 입력 파일 | 출력 컬럼 |
|---|---|---|
| `summarize_land_use_by_dong()` | `seoul_land_use_zone.zip` + `seoul_admin_dong_boundary.zip` | `commercial_zone_ratio`, `residential_zone_ratio`, `semi_residential_zone_ratio`, `industrial_zone_ratio`, `green_zone_ratio` |
| `summarize_sales_by_dong()` | `seoul_commercial_sales_latest.csv` | `total_sales`, `sales_per_store`, `food_sales_ratio` |
| `summarize_population_ratio()` | `seoul_living_population_latest.csv` | `daytime_influx_ratio` (낮 2030 추정인구 / 심야 2030 추정인구) |

### Step 3-4. 상권 잠재력 복합 점수 (commercial_potential_score)

`add_commercial_potential_score()` 함수가 이동 점수와 선택적 레이어를 결합한 복합 점수를 생성한다.

```text
commercial_potential_score =
  adjusted_mobility_score
+ 0.5 × z(commercial_zone_ratio)        ← GIS 용도지역 레이어 (선택)
+ 0.7 × z(log1p(total_sales))           ← 매출 데이터 (선택)
+ 0.4 × z(daytime_influx_ratio)         ← 생활인구 비율 (선택)
+ visit_bonus                            ← 목적 방문형 +0.5, 복합형 +0.2
− 0.3 × z(residential_zone_ratio)       ← GIS 주거지역 패널티 (선택)
```

선택적 레이어가 없으면 해당 항목의 z-score는 0으로 처리한다.

### Step 3-5. 법정동 단위 집계

`aggregate_to_bjdong()` 함수가 행정동 단위 결과를 법정동 단위로 집계한다.

법정동 매핑 우선순위:
1. `data_archive/metadata/bjdong_admdong_mapping.csv` 파일이 있으면 공식 코드 매핑 사용
2. 없으면 행정동명 패턴 근사치 사용: 숫자 접미사 제거 (`잠실6동` → `잠실동`)

집계 방식:
- `cnt_2030`, `cnt_total` 등 이동량 컬럼: 합산
- `score`, `ratio`, `avg_` 컬럼: 평균
- `candidate_type`, `visit_pattern_type` 등 범주 컬럼: 최빈값

출력 파일:

```text
output/processed/bjdong_candidate_summary.csv
output/reports/bjdong_commercial_candidate_top20.md
```

현재 패턴 근사치 기준: 657개 행정동 → 248개 법정동

Top 5 법정동 (commercial_potential_score 기준):

```text
서강동(마포), 이태원동(용산), 여의동(영등포), 합정동(마포), 화곡본동(강서)
```

### Step 4. 2030 자취/거주성 점수 생성

서울 시민생활 데이터에서 20, 25, 30, 35세 구간을 합산한다.

행정동별로 다음 값을 계산한다.

| 생성 지표 | 계산 방식 |
|---|---|
| `young_population` | 20/25/30/35세 총인구 합계 |
| `young_single_households` | 20/25/30/35세 1인가구수 합계 |
| `young_single_ratio` | `young_single_households / young_population` |
| `young_homebound_ratio` | `(휴일 외출이 적은 집단 + 외출이 매우 적은 집단) / young_population` |

자취/거주성 점수:

```text
residential_dominance_score =
  z(log1p(young_single_households))
+ z(young_single_ratio)
+ 0.5 * z(young_homebound_ratio)
```

해석:

- 값이 높으면 2030 자취/거주지 효과가 강하다.
- 이 경우 2030 이동량이 상권 방문보다 생활권 이동일 가능성이 있다.

### Step 5. 방문성 보정 점수 생성

거주성 점수가 높을 때만 감점한다.

```text
residential_penalty = max(residential_dominance_score, 0)

adjusted_mobility_score =
  mobility_score
- 0.7 * residential_penalty
```

해석:

- `mobility_score`: 원래 이동 기반 점수
- `adjusted_mobility_score`: 자취/거주성 효과를 감점한 방문 상권 후보 점수

즉, 신림동·화양동처럼 2030 이동량이 많아도 자취/거주성 점수가 높으면 순위가 내려간다.

### Step 6. 후보 유형 분류

기본 후보 유형은 이동 지표의 분위수를 기준으로 분류한다.

| 유형 | 의미 |
|---|---|
| `핵심 후보형` | 2030 도착량, 2030 비중, 출발지 다양성, 저녁 이동 비중이 모두 높은 지역 |
| `광역 목적지형` | 여러 출발지에서 긴 시간을 들여 방문하는 지역 |
| `야간 소비형` | 저녁 시간대 2030 유입 비중이 높은 지역 |
| `생활권형` | 이동량은 높지만 짧은 이동·낮은 다양성으로 생활권 성격이 강한 지역 |
| `소규모 2030 집중형` | 전체 규모는 작지만 2030 비중이 높은 지역 |
| `관찰 필요` | 월 단위 이동 지표만으로 강한 유형 판단이 어려운 지역 |

추가로 `residential_filter`를 생성한다.

| 값 | 의미 |
|---|---|
| `방문성 검토` | 거주성 신호 약함 → 방문 상권 후보 |
| `혼재형 (상권+거주)` | 거주성 감점 후에도 `adjusted_mobility_score`가 전체 중앙값 이상 → 방문 신호와 거주 효과 공존 |
| `2030 자취/거주성 높음` | 거주성이 강하고 방문 신호가 상대적으로 약함 → 거주지 효과로 분리 |

### Step 7. 결과 분리

최종적으로 네 개의 주요 결과를 만든다.

#### 전체 결과

```text
output/processed/living_migration_2030_destination_summary.csv
```

전체 서울 행정동별 이동 점수, 거주성 점수, 보정 점수, 후보 유형을 포함한다.

#### 방문 상권 후보

```text
output/processed/visitor_candidate_summary.csv
output/reports/visitor_candidate_top20.md
```

`residential_filter == '방문성 검토'` — 2030 자취/거주성 영향이 상대적으로 낮고 방문 목적성이 더 강할 가능성이 있는 후보군이다.

현재 상위 예시 (2026년 3월 30개 일자 기준):

```text
천호3동(강동), 원효로1동(용산), 성수2가3동(성동), 잠실6동(송파), 서초4동(서초)
여의동(영등포), 문래동(영등포), 삼성1동(강남), 자양4동(광진), 왕십리도선동(성동)
```

#### 혼재형 (상권+거주)

```text
output/processed/mixed_commercial_residential_summary.csv
output/reports/mixed_commercial_residential_top20.md
```

`residential_filter == '혼재형 (상권+거주)'` — 거주성 감점 후에도 `adjusted_mobility_score`가 전체 중앙값 이상을 유지한 지역이다. 방문 신호가 충분히 강하지만 거주지 이동이 점수를 일부 끌어올리는 구조가 공존한다.

현재 분석 데이터에서는 48개 행정동이 혼재형으로 집계된다. 이 그룹은 방문 신호가 살아 있지만 거주성 효과도 섞여 있으므로 소비 데이터·점포 밀도·요일별 패턴으로 성격을 추가 분리해야 한다.

#### 2030 자취/거주성 분리 대상

```text
output/processed/residential_dominant_2030_summary.csv
output/reports/residential_dominant_2030_top20.md
```

`residential_filter == '2030 자취/거주성 높음'` — 2030 이동량은 높지만 자취/거주성 영향이 강해 상권 방문으로 바로 해석하면 위험한 지역이다.

현재 상위 예시 (2026년 3월 30개 일자 기준):

```text
신림동(관악), 화양동(광진), 안암동(성북), 가산동(금천), 대학동(관악)
이문1동(동대문), 역삼1동(강남), 신촌동(서대문), 청룡동(관악), 사근동(성동)
```

#### 월별 방문 상권 후보

```text
output/processed/monthly_living_migration_2030_summary.csv
output/processed/monthly_living_migration_all_available_summary.csv
output/processed/monthly_visitor_candidate_summary.csv
output/reports/monthly_visitor_candidate_latest_top20.md
```

2023년 1월부터 2026년 3월까지 월말 대표일 기준으로 계산한 월별 후보 결과다.
`monthly_living_migration_all_available_summary.csv`는 `data_archive/raw/`에 보유한 모든 생활이동 ZIP을 월별로 다시 묶는다. 현재 보유 데이터에서는 2026년 3월이 30개 일자 집계이고, 다른 월은 월말 스냅샷 1개 일자 기준이다. `monthly_coverage_type`과 `date_count`로 월별 커버리지를 확인한다.

`monthly_visitor_candidate_latest_top20.md`에는 최신 월 기준 방문성 후보 상위 20개와, 같은 후보군 안에서 보정 점수가 낮은 하위 5개 비교군이 함께 들어간다. 하위 5개는 적극 후보가 아니라 우선순위 조정과 제외 판단에 참고한다.

최신 월인 2026년 3월 월말 스냅샷 기준 상위 예시:

```text
잠실6동(송파), 문래동(영등포), 여의동(영등포)
왕십리도선동(성동), 원효로1동(용산), 서초4동(서초)
성수2가3동(성동), 성수1가2동(성동), 청담동(강남), 염창동(강서)
```

#### 장기 월별 강세 후보

```text
output/processed/monthly_candidate_trend_summary.csv
output/reports/monthly_candidate_trend_top20.md
```

월별 스냅샷 전체에서 최신 점수, 평균 점수, 점수 기울기, 최근 6개월 변화, 방문 후보 Top 20 반복 등장 횟수를 결합한 결과다.

현재 데이터(2023-01 ~ 2026-03, 39개 스냅샷)에서는 순수 상승 후보보다 여러 달 동안 반복적으로 강한 후보가 상위에 많이 나타난다. 따라서 이 결과는 "새로 뜨는 곳"만을 뜻하지 않고, 2030 방문성이 장기간 유지된 강세 지역까지 포함한다.

장기 강세 상위 예시 (trend_candidate_score 기준):

```text
잠실6동(송파, 39개월 연속 Top 20), 문래동(영등포, 39개월)
여의동(영등포, 39개월), 왕십리도선동(성동, 39개월)
원효로1동(용산, 39개월), 서초4동(서초, 39개월)
```

`trend_type`은 `상승` / `하락` / `유지/변동` 세 값이며, `score_slope > 0.03`이고 `score_change_6m > 0`이면 상승으로 분류한다. 현재 대부분의 후보가 `유지/변동`에 해당한다.

#### 법정동 상권 잠재력 Top 20

```text
output/processed/bjdong_candidate_summary.csv
output/reports/bjdong_commercial_candidate_top20.md
```

행정동 결과를 법정동 단위로 재집계한 결과다. `commercial_potential_score` 기준으로 정렬되며, GIS/매출/생활인구 데이터가 있을수록 점수가 더 정교해진다. 선택적 데이터 없이 이동 데이터만으로도 생성된다.

#### 방문 패턴 분류 현황

2026년 3월 30개 일자 기준 분류 결과:

```text
생활 밀착형: 169개 행정동
불명확: 161개 행정동
목적 방문형: 92개 행정동
```

`목적 방문형`과 `복합형` 행정동은 `commercial_potential_score`에 보너스 점수(+0.5 / +0.2)가 부여된다.

#### 후보 지역별 자동 설명

```text
output/processed/candidate_explanations.csv
output/reports/candidate_explanation_report.md
```

방문성 후보와 혼재형 후보 중 상위 후보와 하위 5개 비교군을 대상으로 이동 신호, 시간대·요일 패턴, 거주성 주의점을 짧은 문장으로 자동 생성한다. 하위 5개는 적극 후보가 아니라 우선순위 조정과 제외 판단에 참고하는 비교군이다.

## 4. 최종 해석 기준

현재 분석에서는 다음 순서로 결과를 본다.

1. `residential_filter`
   - 자취/거주성 높은 지역인지 먼저 확인
2. `adjusted_mobility_score`
   - 자취/거주성을 보정한 후에도 이동 신호가 강한지 확인
3. `candidate_type`
   - 광역 목적지형인지, 야간 소비형인지, 생활권형인지 확인
4. `cnt_2030`, `share_2030`, `origin_diversity`
   - 실제 2030 이동 규모와 확산 범위 확인
5. `young_single_ratio`, `residential_dominance_score`
   - 자취/거주지 효과가 얼마나 강한지 확인

## 5. 현재 한계

현재 분석은 다음 한계를 가진다.

- 생활이동 데이터는 2026년 3월 30개 일자 샘플이다. 3월 28일 파일은 원천 목록에 없어 제외되었다.
- 월별 추세 분석은 2023년 1월~2026년 3월 월말 대표일 39개 파일을 사용한다. 전체 일별 월간 합계가 아니므로 특정 월말 이벤트나 요일 효과가 섞일 수 있다. 보유한 모든 일별 ZIP을 월별로 묶는 확장 산출물도 함께 생성한다.
- 지하철/버스 행정동 공간 결합은 선택 좌표 파일과 행정동 경계 파일이 있을 때 수행된다. 파일이 없으면 기존 역·정류장 단위 보조지표만 생성한다.
- `commercial_potential_score`는 선택적 데이터(GIS/매출/생활인구)가 모두 없을 때 이동 지표만으로 계산되므로 용도지역·매출 차이가 반영되지 않는다.
- 2030 자취/거주성 보정은 완전 제거가 아니라 감점/분리 장치다.
- `혼재형 (상권+거주)` 카테고리는 방문 신호와 거주성 신호가 함께 강한 구간이므로, 순수 방문 상권으로 바로 해석하지 않는다.
- 법정동 매핑 파일이 없을 때 사용하는 패턴 근사치(`잠실6동` → `잠실동`)는 복잡한 이름 규칙을 완전히 처리하지 못한다. 공식 매핑 파일을 준비하면 정확도가 높아진다.

## 6. 다음 단계

분석 신뢰도를 높이기 위한 다음 단계는 다음과 같다.

### 완료된 항목

- [x] 요일/시간대별 이동 비중 분해 (평일·금요일·주말, 오전·오후·저녁·심야)
- [x] `visit_pattern_type` 분류 (목적 방문형 / 생활 밀착형 / 복합형 / 불명확)
- [x] GIS 용도지역 레이어 결합 구조 구현 (`summarize_land_use_by_dong`)
- [x] 매출 데이터 결합 구조 구현 (`summarize_sales_by_dong`)
- [x] 생활인구 유동/상주 비율 구현 (`summarize_population_ratio`)
- [x] `commercial_potential_score` 복합 점수 생성
- [x] 법정동 단위 집계 (`aggregate_to_bjdong`)
- [x] 선택적 데이터 로더와 파이프라인 검증
  - 매출: `bash data_archive/scripts/download_commercial_sales.sh`
  - 생활인구: `bash data_archive/scripts/download_living_population.sh`
  - 법정동 매핑: `bash data_archive/scripts/download_bjdong_mapping.sh`
  - GIS: `bash data_archive/scripts/download_gis_data.sh` + `pip install geopandas shapely`
  - 파일이 없거나 패키지가 없으면 해당 레이어를 건너뛰고 이동 데이터 기준으로 계속 실행
- [x] 보유한 모든 생활이동 일별 ZIP을 월별로 묶는 확장 산출물 생성 (`monthly_living_migration_all_available_summary.csv`)
- [x] 역·정류장 좌표와 행정동 경계의 선택적 공간 결합 구조 구현 (`transport_access_by_dong.csv`)
- [x] 후보 지역별 자동 설명 리포트 생성 (`candidate_explanation_report.md`)

### 운영상 확인 항목

- 매출·생활인구 다운로드 스크립트의 `seq`는 서울 열린데이터광장 원천 페이지에서 최신 파일 기준으로 바뀔 수 있다.
- `seoul_admin_dong_boundary.zip`, `subway_station_coordinates.csv`, `bus_stop_coordinates.csv`가 없으면 교통 접근성 공간 결합은 건너뛴다.
- 월별 전체 일별 집계를 완전히 만들려면 각 월의 모든 일별 생활이동 ZIP을 추가로 확보해야 한다.
