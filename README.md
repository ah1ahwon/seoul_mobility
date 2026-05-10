# Seoul 2030 Mobility Commercial-Area Analysis

2030세대 이동/교통 데이터를 바탕으로 서울 내 상권 후보지를 1차 탐색하는 Python 분석 프로젝트입니다.

## Project Structure

```text
.
├── seoul_mobility_analysis.py
├── data_archive/
│   ├── raw/
│   ├── metadata/
│   ├── notes/
│   └── scripts/
├── output/
│   ├── processed/
│   └── reports/
├── requirements.txt
└── README.md
```

## Archived Data

`data_archive/raw/`에 원천 파일을 로컬로 보관합니다. 원천 데이터는 용량이 크기 때문에 GitHub에는 올리지 않습니다.

- `CARD_SUBWAY_MONTH_202604.csv`
  - 서울시 지하철호선별 역별 승하차 인원, 2026년 4월
- `bus_time_station_202604.csv`
  - 서울시 버스노선별 정류장별 시간대별 승하차 인원, 2026년 4월
- `seoul_purpose_admdong4_in_20260331.zip`
  - 수도권 생활이동 연령별 출발-도착지 기준, 내국인 목적별, 2026년 3월 31일
- `seoul_admin_dong_area.zip`
  - 서울시 상권분석서비스 영역-행정동, 행정동 코드/명칭 매핑용
- `seoul_living_interest_groups_202512.xlsx`
  - 서울 시민생활 데이터 행정동단위 10개 관심집단수, 2025년 12월
  - 2030 1인가구 거주성 보정용

## Setup

```bash
cd /Users/jeong-awon/Documents/seoul_mobility
python3 -m pip install -r requirements.txt
```

## Run

```bash
python3 seoul_mobility_analysis.py
```

생성 결과는 `output/` 아래에 저장됩니다.

주요 산출물:

- `output/processed/living_migration_2030_destination_summary.csv`
- `output/processed/living_migration_2030_destination_hourly.csv`
- `output/processed/subway_station_summary.csv`
- `output/processed/bus_stop_summary.csv`
- `output/processed/young_single_household_residential_summary.csv`
- `output/processed/visitor_candidate_summary.csv`
- `output/processed/residential_dominant_2030_summary.csv`
- `output/reports/living_migration_2030_top20.md`
- `output/reports/interpretation_report.md`
- `output/reports/visitor_candidate_top20.md`
- `output/reports/residential_dominant_2030_top20.md`

## Current Scoring Logic

현재 `mobility_score`는 후보 발굴용 1차 점수입니다.

```text
mobility_score =
  z(log 2030 도착량)
+ z(2030 비중)
+ z(log 출발지 다양성)
+ z(저녁 2030 비중)
```

`adjusted_mobility_score`는 2030 1인가구 밀집도가 높은 자취/거주성 지역을 분리하기 위한 보정 점수입니다.

```text
adjusted_mobility_score =
  mobility_score
- 0.7 * max(residential_dominance_score, 0)
```

`residential_dominance_score`는 서울 시민생활 데이터의 2030 1인가구수, 2030 1인가구 비율, 외출 적은 집단 비중을 조합해 계산합니다.

후보 유형:

- `핵심 후보형`
- `광역 목적지형`
- `야간 소비형`
- `생활권형`
- `소규모 2030 집중형`
- `관찰 필요`

## Git Notes

`data_archive/raw/`와 `output/`은 Git에서 제외합니다. 원천 데이터와 분석 결과물은 로컬에서 재생성하거나 다시 다운로드하는 방식으로 관리합니다.

`data_archive/.env`에는 API 키가 들어 있으므로 Git에서 제외합니다. 공유할 때는 `data_archive/.env.example`만 사용하세요.

원천 파일이 없는 새 환경에서는 `data_archive/scripts/download_latest_examples.sh`를 실행해 샘플 데이터를 다시 받을 수 있습니다.

```bash
bash data_archive/scripts/download_latest_examples.sh
```
