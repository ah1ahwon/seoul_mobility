# Seoul 2030 Mobility Commercial-Area Analysis

2030세대 이동/교통 데이터를 바탕으로 서울 내 상권 후보지를 1차 탐색하는 Python 분석 프로젝트입니다.

## Project Structure

```text
.
├── seoul_mobility_analysis.py      # 분석 스크립트 (로컬/Colab 공통)
├── Seoul_Mobility_Full_Pipeline.ipynb  # Colab 전체 파이프라인 (다운로드 → 분석 → 시각화)
├── Seoul_Mobility_Colab.ipynb      # Colab 단순 연결용 (Drive에 데이터 미리 준비 후 실행)
├── ANALYSIS_FLOW.md                # 분석 방법론 상세 문서
├── data_archive/
│   ├── raw/                        # 원천 파일 (gitignore 대상, 로컬/Drive 보관)
│   ├── metadata/                   # manifest CSV, 데이터셋 페이지 HTML
│   ├── notes/                      # 데이터 해석 주의사항
│   └── scripts/                    # 서울 열린데이터광장 재다운로드 스크립트
├── output/
│   ├── processed/                  # 전처리/집계 CSV
│   └── reports/                    # Top 20 순위 및 해석 보고서 .md
├── requirements.txt
└── README.md
```

## 데이터 기간 및 분석 역할

각 데이터의 기간과 분석에서의 역할이 다릅니다. 해석 시 기간 차이를 염두에 두세요.

| 데이터 | 기간 | 역할 |
|---|---|---|
| 생활이동 일별 OD | 2026년 3월 (30개 일자, 28일 제외) | **상세 분석 기준 월** — 후보 발굴, mobility_score, candidate_type 산출의 핵심 |
| 생활이동 월말 스냅샷 | 2023년 1월 ~ 2026년 3월 (39개 파일) | **장기 추세** — 월별 순위, score_slope, trend_type (전체 월간 합계 아님) |
| 지하철 승하차 | 2026년 4월 | 교통 보조 지표 (생활이동보다 한 달 뒤, 행정동 미결합) |
| 버스 승하차 | 2026년 4월 | 교통 보조 지표 (생활이동보다 한 달 뒤, 행정동 미결합) |
| 서울 시민생활 1인가구 | 2025년 12월 | 거주성 보정 기준 (생활이동보다 3개월 전 스냅샷) |

**2026년 3월 한계**: 현재 상세 분석의 기반은 2026년 3월 30개 일자 데이터입니다. 이후 월(4월, 5월 등)로 업데이트하려면 해당 월의 생활이동 일별 파일을 `data_archive/raw/`에 추가하고 `LIVING_MIGRATION_PATTERN`을 수정해야 합니다.

## Archived Data

`data_archive/raw/`에 원천 파일을 로컬로 보관합니다. 원천 데이터는 용량이 크기 때문에 GitHub에는 올리지 않습니다.

- `CARD_SUBWAY_MONTH_202604.csv`
  - 서울시 지하철호선별 역별 승하차 인원, 2026년 4월
- `bus_time_station_202604.csv`
  - 서울시 버스노선별 정류장별 시간대별 승하차 인원, 2026년 4월
- `seoul_purpose_admdong4_in_202603*.zip`
  - 수도권 생활이동 연령별 출발-도착지 기준, 내국인 목적별, 2026년 3월 30개 일자
  - 원천 페이지에 2026년 3월 28일 파일은 없어 30개 파일을 사용
- `seoul_purpose_admdong4_in_YYYYMMDD.zip`
  - 2023년 1월~2026년 3월 월말 스냅샷 39개 파일
  - `data_archive/metadata/living_migration_month_end_manifest.csv` 기준으로 아카이빙
  - 장기 월별 추세 분석용이며, 전체 일별 월간 합계가 아니라 각 월의 월말 대표일 비교
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

### 로컬 실행

```bash
python3 seoul_mobility_analysis.py
```

환경변수로 경로를 오버라이드할 수 있습니다.

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `SEOUL_RAW_DIR` | `data_archive/raw/` | 원천 파일 위치 |
| `SEOUL_OUTPUT_DIR` | `output/` (스크립트 기준) | 결과 파일 저장 위치 |
| `SEOUL_SKIP_GIT` | 미설정 | `1`이면 분석 후 자동 commit/push를 건너뜀 |

### Google Colab 실행

두 가지 Colab 노트북이 있습니다.

#### `Seoul_Mobility_Full_Pipeline.ipynb` (권장)

데이터 다운로드부터 분석·시각화까지 한 번에 실행하는 자동화 파이프라인입니다. 분석 스크립트는 기본적으로 결과물 commit/push까지 시도하므로, 결과만 확인하려면 `SEOUL_SKIP_GIT=1`을 설정하세요.

1. Google Drive 마운트
2. GitHub에서 최신 코드 clone/pull
3. 서울 열린데이터광장에서 직접 데이터 다운로드 (약 3 GB, 72개 파일) → Drive 저장
4. 불량 ZIP 파일 자동 감지·삭제
5. `seoul_mobility_analysis.py` 실행
6. 7개 시각화 차트 생성

아래 URL에서 직접 열 수 있습니다.

```
https://colab.research.google.com/github/ah1ahwon/seoul_mobility/blob/main/Seoul_Mobility_Full_Pipeline.ipynb
```

내부적으로 `SEOUL_RAW_DIR`과 `SEOUL_OUTPUT_DIR`을 Drive 경로로 설정합니다.

#### `Seoul_Mobility_Colab.ipynb` (단순 연결)

Drive에 데이터를 미리 준비해 둔 경우 분석 스크립트만 실행합니다.

```python
import os
os.environ["SEOUL_RAW_DIR"]    = "/content/drive/MyDrive/seoul_mobility/raw"
os.environ["SEOUL_OUTPUT_DIR"] = "/content/drive/MyDrive/seoul_mobility/output"

!python3 /content/seoul_mobility/seoul_mobility_analysis.py
```

분석 완료 후 기본적으로 `commit_outputs()`가 실행되어 repo 안 `output/` 하위 파일을 git 커밋하고 원격 저장소에 push합니다. `SEOUL_SKIP_GIT=1`을 설정하면 이 단계를 건너뜁니다. `SEOUL_OUTPUT_DIR`이 repo 밖(Drive 경로)이면 해당 Drive 결과물은 git 스테이징 대상이 아니므로, 버전 관리가 필요하면 결과 저장 경로를 repo 안으로 두고 remote를 설정해야 합니다.

생성 결과는 `output/` 아래에 저장됩니다.

주요 산출물:

**processed/**

| 파일 | 설명 |
|---|---|
| `admin_dong_mapping.csv` | 행정동 코드-명칭-좌표 매핑 |
| `young_single_household_residential_summary.csv` | 2030 1인가구 거주성 요약 |
| `subway_station_daily.csv` | 지하철 역별 일별 승하차 원본 전처리 |
| `subway_station_summary.csv` | 지하철 역별 집계 요약 |
| `bus_stop_route_summary.csv` | 버스 정류장/노선별 집계 요약 |
| `bus_stop_route_hourly.csv` | 버스 정류장/노선별 시간대별 long format |
| `bus_stop_summary.csv` | 버스 정류장별 집계 요약 |
| `bus_hourly_citywide_summary.csv` | 시간대별 서울 전체 버스 집계 |
| `living_migration_2030_destination_summary.csv` | 2030 생활이동 행정동별 전체 결과 |
| `living_migration_2030_destination_hourly.csv` | 2030 생활이동 행정동별 시간대별 결과 |
| `visitor_candidate_summary.csv` | 방문 상권 후보 (거주성 낮음) |
| `mixed_commercial_residential_summary.csv` | 혼재형 후보 (상권+거주 동시 강함) |
| `residential_dominant_2030_summary.csv` | 2030 자취/거주성 분리 대상 |
| `monthly_living_migration_2030_summary.csv` | 월별 2030 생활이동 전체 요약 |
| `monthly_living_migration_all_available_summary.csv` | 보유한 모든 일별 ZIP을 월별로 집계한 확장 요약 |
| `monthly_visitor_candidate_summary.csv` | 월별 방문 상권 후보 |
| `monthly_candidate_trend_summary.csv` | 장기 월별 강세 후보 트렌드 |
| `candidate_explanations.csv` | 후보 지역별 상위/하위 자동 설명 요약 |
| `transport_access_by_dong.csv` | 선택 좌표 파일이 있을 때 생성되는 행정동별 교통 접근성 지표 |

**reports/**

| 파일 | 설명 |
|---|---|
| `living_migration_2030_top20.md` | 전체 Top 20 보정 점수 순위 |
| `visitor_candidate_top20.md` | 방문 상권 후보 Top 20 |
| `mixed_commercial_residential_top20.md` | 혼재형 후보 Top 20 |
| `residential_dominant_2030_top20.md` | 2030 자취/거주성 분리 대상 Top 20 |
| `monthly_visitor_candidate_latest_top20.md` | 최신 월 방문 상권 후보 Top 20 |
| `monthly_candidate_trend_top20.md` | 장기 월별 강세 후보 Top 20 |
| `candidate_explanation_report.md` | 후보 지역별 상위/하위 자동 설명 리포트 |
| `interpretation_report.md` | 전체 결과 해석 보고서 |

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

월별 분석에서는 같은 점수식을 각 월 안에서 다시 표준화합니다. 이렇게 해야 월별 전체 이동량 차이가 아니라, 해당 월 안에서 상대적으로 강한 행정동을 비교할 수 있습니다.

거주성 분류 (`residential_filter`):

- `방문성 검토`: 거주성 신호 약함 → 방문 상권 후보 (현재 데이터: 305개 동)
- `혼재형 (상권+거주)`: 거주성 감점 후에도 `adjusted_mobility_score`가 전체 중앙값 이상 → 방문·거주 신호 공존 (현재 데이터: 48개 동)
- `2030 자취/거주성 높음`: 거주성 강하고 방문 신호 상대적으로 약함 → 거주지 효과로 분리 (현재 데이터: 69개 동, 예: 신림동, 화양동, 안암동)

후보 유형 (`candidate_type`):

- `핵심 후보형`
- `광역 목적지형`
- `야간 소비형`
- `생활권형`
- `소규모 2030 집중형`
- `관찰 필요`

## Git Notes

`data_archive/raw/`는 용량이 크므로 Git에서 제외합니다. 원천 데이터는 로컬에서 재다운로드하는 방식으로 관리합니다.

`data_archive/.env`에는 API 키가 들어 있으므로 Git에서 제외합니다. 공유할 때는 `data_archive/.env.example`만 사용하세요.

`output/` 하위의 분석 결과물(`.md`, `.png`, `.csv`)은 분석 스크립트 실행 완료 시 기본적으로 `commit_outputs()`가 git 커밋하고 원격 저장소에 push합니다. 이 동작을 끄려면 `SEOUL_SKIP_GIT=1`을 설정하세요. Colab에서 Drive 경로로 저장할 경우 해당 Drive 결과물은 git 스테이징 대상에서 벗어나므로, 결과를 버전 관리하려면 `SEOUL_OUTPUT_DIR`을 repo 내 경로로 설정하고 원격 저장소 remote를 준비해야 합니다.

원천 파일이 없는 새 환경에서는 아래 스크립트로 샘플 데이터를 다시 받을 수 있습니다.

```bash
bash data_archive/scripts/download_latest_examples.sh
```

월별 추세용 생활이동 월말 파일은 아래 스크립트로 받을 수 있습니다.

```bash
bash data_archive/scripts/download_living_migration_month_end.sh
```
