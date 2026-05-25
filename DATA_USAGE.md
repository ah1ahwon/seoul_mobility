# 데이터 사용 기준표

이 문서는 현재 분석 코드(`seoul_mobility_analysis.py`) 기준으로 원천 데이터의 어떤 컬럼을 어떤 지표로 변환해 사용하는지 정리한다. 목적은 분석 기준을 명확히 남겨서, 이후 데이터 교체나 지표 조정 시 어떤 입력이 결과에 영향을 주는지 바로 확인하는 것이다.

## 1. 핵심 분석 단위

| 기준 | 설명 |
|---|---|
| 기본 공간 단위 | 서울 행정동 (`d_admdong_cd`) |
| 보조 공간 단위 | 법정동 (`bjdong_cd`, `bjdong_nm`) |
| 핵심 타깃 | 20대+30대 이동 및 유입 |
| 상세 분석 기준 월 | 2026년 3월 생활이동 일별 파일 30개 |
| 장기 추세 | 2023년 1월~2026년 3월 월말 스냅샷 |
| 이동 신호 점수 | `mobility_signal_score` |
| 상권 검증 점수 | `commercial_validation_score` |
| 최종 후보 점수 | `final_candidate_score` (`commercial_potential_score`는 호환용 별칭) |
| 주요 보정 점수 | `adjusted_mobility_score`, `residential_dominance_score` |

## 2. 수도권 생활이동 OD 데이터

| 항목 | 내용 |
|---|---|
| 파일 | `data_archive/raw/seoul_purpose_admdong4_in_202603*.zip`, `seoul_purpose_admdong4_in_YYYYMMDD.zip` |
| 출처 | 서울 열린데이터광장 `OA-22299` |
| 분석 역할 | 2030 도착 이동량, 출발지 다양성, 시간대·요일 패턴, 이동 거리/시간, 기본 이동 점수 생성 |

| 원천 컬럼 | 사용 방식 | 생성 지표 |
|---|---|---|
| `d_admdong_cd` | 도착 행정동. 분석의 기본 단위 | 행정동별 집계 키 |
| `o_admdong_cd` | 출발 행정동. 2030 이동이 있는 출발지 개수 계산 | `origin_diversity` |
| `st_time_cd` | 이동 시작 시간대. 오전/오후/저녁/심야 구간 분류 | `morning_2030_ratio`, `afternoon_2030_ratio`, `evening_2030_ratio`, `late_night_2030_ratio` |
| `move_dist` | `2030_cnt`로 가중 평균 | `avg_move_dist_2030` |
| `move_time` | `2030_cnt`로 가중 평균 | `avg_move_time_2030` |
| `2030_cnt` | 20·30대 이동량. 핵심 이동 규모 | `cnt_2030`, `avg_daily_2030`, 시간대별 2030 이동량 |
| `total_cnt` | 전체 연령 이동량 | `share_2030 = cnt_2030 / total_cnt` |
| `etl_ymd` | 기준일. 요일·월 추출 | `date_count`, `active_days`, `weekday_2030_ratio`, `friday_2030_ratio`, `weekend_2030_ratio`, 월별 `yyyymm` |

이 데이터에서 만드는 핵심 점수:

```text
mobility_score =
  z(log1p(cnt_2030))
+ z(share_2030)
+ z(log1p(origin_diversity))
+ z(evening_2030_ratio)
```

해석 기준:

- `cnt_2030`이 크면 실제 유입 규모가 크다.
- `share_2030`이 높으면 전체 이동 중 2030 집중도가 높다.
- `origin_diversity`가 높으면 특정 생활권 내부 이동보다 광역 목적지 가능성이 높다.
- `evening_2030_ratio`가 높으면 퇴근 후 소비·여가 방문 가능성이 커진다.

## 3. 서울 시민생활 데이터 - 행정동단위 10개 관심집단수

사용자가 말한 “생활관심도”에 해당하는 데이터는 현재 코드에서 **2030 자취/거주성 보정**에 사용한다.

| 항목 | 내용 |
|---|---|
| 파일 | `data_archive/raw/seoul_living_interest_groups_202512.xlsx` |
| 출처 | 서울 시민생활 데이터, 서울 열린데이터광장 `OA-22266` |
| 분석 역할 | 2030 이동량이 상권 방문 때문인지, 자취·거주지 효과 때문인지 분리 |

| 원천 컬럼 | 사용 방식 | 생성 지표 |
|---|---|---|
| `자치구` | 생활이동 결과와 `d_gu_name` 기준 매칭 | `gu_name` |
| `행정동명` | 생활이동 결과와 `d_admdong_name` 기준 매칭 | `admdong_name` |
| `행정동코드` | 보조 식별자 | `living_admdong_cd` |
| `성별` | 남녀를 따로 쓰지 않고 합산 | 별도 지표 없음 |
| `연령대` | 20, 25, 30, 35만 사용 | 2030 범위 필터 |
| `총인구` | 20/25/30/35세 구간 합산 | `young_population` |
| `1인가구수` | 20/25/30/35세 구간 합산 | `young_single_households` |
| `휴일 외출이 적은 집단` | 20/25/30/35세 구간 합산 | `young_low_weekend_outing_group` |
| `외출이 매우 적은 집단(전체)` | 20/25/30/35세 구간 합산 | `young_very_low_outing_group` |

생성 지표:

```text
young_single_ratio =
  young_single_households / young_population

young_homebound_ratio =
  (young_low_weekend_outing_group + young_very_low_outing_group)
  / young_population

residential_dominance_score =
  z(log1p(young_single_households))
+ z(young_single_ratio)
+ 0.5 * z(young_homebound_ratio)
```

최종 이동 점수 보정:

```text
residential_penalty = max(residential_dominance_score, 0)

adjusted_mobility_score =
  mobility_score
- 0.7 * residential_penalty
```

이동 상권 분석에서는 이 값을 그대로 `mobility_signal_score`로 사용한다.

```text
mobility_signal_score = adjusted_mobility_score
```

해석 기준:

- 2030 1인가구 수와 비율이 높으면 자취·원룸·대학가 효과일 가능성이 크다.
- 외출 적은 집단 비중이 높으면 도착 이동이 상권 방문보다 생활권·거주성 이동일 가능성이 커진다.
- 이 데이터는 후보를 제거하는 용도가 아니라 `방문성 검토`, `혼재형`, `2030 자취/거주성 높음`으로 분리하는 보정 장치다.

## 4. 행정동 코드/명칭 매핑

| 항목 | 내용 |
|---|---|
| 파일 | `data_archive/raw/seoul_admin_dong_area.zip` |
| 출처 | 서울 열린데이터광장 `OA-22160` |
| 분석 역할 | 생활이동 행정동 코드에 행정동명, 자치구명, 중심 좌표, 면적을 붙임 |

| 원천 컬럼 | 사용 방식 | 생성/출력 지표 |
|---|---|---|
| `ADSTRD_CD` | `d_admdong_cd`와 매칭 | `d_admdong_cd`, `d_gu_cd` |
| `ADSTRD_NM` | 결과 해석용 행정동명 | `d_admdong_name` |
| `XCNTS_VALU` | 행정동 중심 X 좌표 | `d_center_x` |
| `YDNTS_VALU` | 행정동 중심 Y 좌표 | `d_center_y` |
| `RELM_AR` | 행정동 면적 | `d_area_sqm` |

필터 기준:

- `d_admdong_cd`가 `11`로 시작하는 서울 행정동만 남긴다.
- 행정동명 매핑이 안 되는 행정동은 최종 결과에서 제외한다.

## 5. 행정동별 추정매출

| 항목 | 내용 |
|---|---|
| 파일 | `data_archive/raw/seoul_commercial_sales_latest.csv` |
| 출처 | 서울 열린데이터광장 `OA-22175` |
| 분석 역할 | 단순 유동·통행이 아니라 실제 소비가 발생하는 상권인지 보정 |

| 원천 컬럼 | 코드 내 표준 컬럼 | 사용 방식 | 생성 지표 |
|---|---|---|---|
| `행정동_코드` | `admdong_cd` | 행정동 기준 집계 및 이동 결과와 결합 | `d_admdong_cd` |
| `행정동_코드_명` | `admdong_name` | 보조 명칭 | 직접 점수에는 미사용 |
| `서비스_업종_코드_명` | `industry_name` | 음식/식음료/주점/카페/음료 키워드 판별 | `food_sales_ratio` |
| `당월_매출_금액` | `monthly_sales` | 행정동별 합산 | `total_sales` |
| `당월_매출_건수` | `monthly_txn` | 행정동별 합산 | `total_txn` |
| `점포수` | `store_count` | 행정동별 합산 | `total_stores`, `sales_per_store` |

생성 지표:

```text
total_sales = sum(monthly_sales)
total_stores = sum(store_count)
total_txn = sum(monthly_txn)
sales_per_store = total_sales / total_stores
food_sales_ratio = food_sales / total_sales
```

상권 검증 점수 반영:

```text
+ 0.7 * z(log1p(total_sales))
```

현재 `sales_per_store`, `food_sales_ratio`는 결과 해석과 법정동 리포트에 포함되지만, `commercial_validation_score`에는 `total_sales`만 직접 반영된다.

## 6. 서울 생활인구

| 항목 | 내용 |
|---|---|
| 파일 | `data_archive/raw/seoul_living_population_latest.csv` |
| 출처 | 서울 열린데이터광장 `OA-14991` |
| 분석 역할 | 낮 시간대 2030 유입이 심야 상주성보다 강한지 확인 |

| 원천 컬럼 | 코드 내 표준 컬럼 | 사용 방식 | 생성 지표 |
|---|---|---|---|
| `행정동코드` | `admdong_cd` | 행정동 기준 집계 | `d_admdong_cd` |
| `시간대구분` | `time_slot` | 낮/심야 구분 | `daytime_pop_2030`, `nighttime_pop_2030` |
| `20대생활인구수` | `pop_20s` | 2030 생활인구 합산 | `pop_2030` |
| `30대생활인구수` | `pop_30s` | 2030 생활인구 합산 | `pop_2030` |
| 성별·5세 단위 20~39세 생활인구 컬럼 | 원명 유지 | 20대/30대 컬럼이 없을 때 대체 합산 | `pop_2030` |

시간대 기준:

| 구분 | 시간 |
|---|---|
| 낮 | 9~18시 |
| 심야 | 22~6시 |

생성 지표:

```text
daytime_influx_ratio =
  daytime_pop_2030 / nighttime_pop_2030
```

상권 검증 점수 반영:

```text
+ 0.4 * z(daytime_influx_ratio)
```

해석 기준:

- `daytime_influx_ratio > 1`이면 심야 상주성보다 낮 유입이 강한 지역으로 본다.
- 방문·업무·소비 목적의 외부 유입 가능성을 보정하는 지표다.

## 7. 최종 이동 상권 후보 점수

매출, 생활인구, 방문패턴은 이동 신호가 실제 상권성으로 해석될 수 있는지 확인하는 보조 검증 레이어다. 용도지역·행정동 경계 같은 GIS 데이터는 재현 가능한 자동 다운로드가 어렵기 때문에 기본 분석에서 제외한다.

```text
commercial_validation_score =
  0.7 * z(log1p(total_sales))
+ 0.4 * z(daytime_influx_ratio)
+ visit_bonus

final_candidate_score =
  mobility_signal_score + commercial_validation_score
```

`visit_bonus`는 목적 방문형 +0.5, 복합형 +0.2, 그 외 0.0이다. 결과 CSV에는 `enrichment_status`와 `missing_enrichment_count`를 함께 저장한다. `enrichment_status`에 미반영 항목이 있으면 `final_candidate_score`는 상권 검증이 덜 된 이동 기반 후보 점수로 해석한다.

## 8. 지하철 승하차

| 항목 | 내용 |
|---|---|
| 파일 | `data_archive/raw/CARD_SUBWAY_MONTH_202604.csv` |
| 출처 | 서울 열린데이터광장 `OA-12914` |
| 분석 역할 | 후보 해석용 교통 보조지표. 현재 최종 점수에는 직접 반영하지 않음 |

| 원천 컬럼 | 코드 내 표준 컬럼 | 사용 방식 | 생성 지표 |
|---|---|---|---|
| `사용일자` | `date` | 날짜·요일·주말 여부 계산 | `weekday`, `is_weekend` |
| `노선명` | `line_name` | 역 식별 보조 | 보조 컬럼 |
| `역명` | `station_name` | 역별 집계 단위 | 역별 요약 |
| `승차총승객수` | `board_count` | 역별 승차 합산 | `subway_total_count` |
| `하차총승객수` | `alight_count` | 역별 하차 합산 | `subway_total_count` |
| `등록일자` | `registered_date` | 보조 날짜 | 직접 점수에는 미사용 |

생성 지표:

```text
total_count = board_count + alight_count
subway_weekend_share = weekend total_count / total_count
```

주의:

- 기본 지하철 데이터에는 행정동 좌표가 없어 행정동 후보 점수에 직접 연결하지 않는다.
- 역 좌표와 행정동 경계가 필요한 공간 결합은 기본 분석에서 제외한다.

## 9. 버스 승하차

| 항목 | 내용 |
|---|---|
| 파일 | `data_archive/raw/bus_time_station_202604.csv` |
| 출처 | 서울 열린데이터광장 `OA-12913` |
| 분석 역할 | 후보 해석용 교통 보조지표. 현재 최종 점수에는 직접 반영하지 않음 |

| 원천 컬럼 | 코드 내 표준 컬럼 | 사용 방식 | 생성 지표 |
|---|---|---|---|
| `사용년월` | `year_month` | 기준 월 | 보조 컬럼 |
| `노선번호` | `route_no` | 노선 식별 | `route_count` |
| `노선명` | `route_name` | 노선명 | 보조 컬럼 |
| `표준버스정류장ID` | `station_id` | 정류장 식별 | 정류장별 집계 키 |
| `버스정류장ARS번호` | `ars_id` | 정류장 보조 식별 | 정류장별 집계 키 |
| `역명` | `station_name` | 정류장명 | 정류장별 집계 |
| `0시승차총승객수`~`23시승차총승객수` | 시간대별 승차 | long format 변환 | `board_count`, `board_total` |
| `0시하차총승객수`~`23시하차총승객수` | 시간대별 하차 | long format 변환 | `alight_count`, `alight_total` |

생성 지표:

```text
total_count = board_total + alight_total
bus_total_count = sum(total_count)
route_count = 정류장별 노선 수
```

주의:

- `output/processed/bus_stop_route_hourly.csv`는 100MB를 초과해 GitHub에는 올리지 않고 로컬 재생성 대상으로 둔다.
- 정류장 좌표와 행정동 경계가 필요한 공간 결합은 기본 분석에서 제외한다.

## 10. 수도권 생활이동 성·연령별 도착지 데이터

| 항목 | 내용 |
|---|---|
| 파일 | `data_archive/raw/seoul_purpose_admdong1_in_YYYYMM.zip` |
| 출처 | 서울 열린데이터광장 `OA-22298` |
| 분석 역할 | 10대 미만~70대 이상까지 연령대별 도착지 패턴을 분리해서 비교 |

| 원천 컬럼 | 사용 방식 | 생성 지표 |
|---|---|---|
| `d_admdong_cd` | 도착 행정동 | 연령대별 행정동 집계 키 |
| `time_cd` | 시간대 | 연령대별 시간대 비중 |
| `move_purpose` | 이동 목적 | 연령대별 목적 분포 |
| `total_cnt` | 전체 이동량 | `age_share`의 분모 |
| `etl_ymd` | 기준일 | 월(`yyyymm`), 활성 일수 |
| `male_00_cnt`, `feml_00_cnt` | 10대 미만 남녀 이동량 | `age_00` |
| `male_10_cnt`, `feml_10_cnt` | 10대 남녀 이동량 | `age_10` |
| `male_20_cnt`, `feml_20_cnt` | 20대 남녀 이동량 | `age_20` |
| `male_30_cnt`, `feml_30_cnt` | 30대 남녀 이동량 | `age_30` |
| `male_40_cnt`, `feml_40_cnt` | 40대 남녀 이동량 | `age_40` |
| `male_50_cnt`, `feml_50_cnt` | 50대 남녀 이동량 | `age_50` |
| `male_60_cnt`, `feml_60_cnt` | 60대 남녀 이동량 | `age_60` |
| `male_70_cnt`, `feml_70_cnt` | 70대 이상 남녀 이동량 | `age_70plus` |

생성 지표:

```text
age_cnt = male age count + female age count
avg_daily_age_cnt = age_cnt / active_days
age_share = age_cnt / total_cnt

age_mobility_score =
  z(age_cnt, 같은 age_group 내부)
+ z(age_share, 같은 age_group 내부)
+ z(evening_ratio, 같은 age_group 내부)
```

주의:

- 이 데이터에는 출발 행정동이 없어서 `origin_diversity`는 계산하지 않는다.
- 기본 2030 후보 점수의 핵심 데이터는 `OA-22299`이고, 이 데이터는 연령대별 비교 보조 분석이다.

## 11. 행정동-법정동 매핑

| 항목 | 내용 |
|---|---|
| 파일 | `data_archive/metadata/bjdong_admdong_mapping.csv` |
| 출처 | 선택 입력. 행정안전부/통계청/data.go.kr 등에서 준비 |
| 분석 역할 | 행정동 결과를 법정동 단위로 재집계 |

| 컬럼 | 사용 방식 |
|---|---|
| `admdong_cd` | 행정동 결과의 `d_admdong_cd`와 매칭 |
| `bjdong_cd` | 법정동 식별자 |
| `bjdong_nm` | 법정동 이름 |

집계 기준:

| 컬럼 유형 | 법정동 집계 방식 |
|---|---|
| `*_cnt`, `total_cnt` | 합산 |
| `*_score`, `*_ratio`, `avg_*` | 평균 |
| `candidate_type`, `visit_pattern_type`, `residential_filter`, `enrichment_status` | 최빈값 |

## 12. 최종 후보 점수에 직접 들어가는 지표

```text
mobility_signal_score =
  adjusted_mobility_score

commercial_validation_score =
+ 0.7 * z(log1p(total_sales))
+ 0.4 * z(daytime_influx_ratio)
+ visit_bonus

final_candidate_score =
  mobility_signal_score + commercial_validation_score
```

| 구성 요소 | 원천 데이터 | 의미 |
|---|---|---|
| `mobility_signal_score` | 생활이동 OD + 시민생활 관심집단 | 2030 이동 신호에서 자취/거주성 효과를 감점한 방문성 점수 |
| `total_sales` | 행정동별 추정매출 | 실제 소비 발생 규모 |
| `daytime_influx_ratio` | 서울 생활인구 | 낮 유입이 심야 상주성보다 강한지 |
| `visit_bonus` | 생활이동 시간대·요일 패턴 | 목적 방문형/복합형 패턴 가산 |

이 점수는 정답 데이터로 학습한 모델이 아니라 후보 스크리닝용 휴리스틱 점수다. `commercial_potential_score`는 기존 산출물 호환을 위해 `final_candidate_score`와 같은 값을 담는다. 각 가중치는 다음 기준으로 둔다.

| 항목 | 기준 |
|---|---|
| `total_sales` 0.7 | 실제 소비 발생 규모라서 보조 지표 중 가장 강하게 반영 |
| `daytime_influx_ratio` 0.4 | 낮 유입은 방문·업무·통행이 섞인 보조 신호라 중간보다 약하게 적용 |
| `목적 방문형` +0.5 | 주말과 저녁/심야 신호가 함께 강해 자발적 방문·소비 가능성이 높다고 판단 |
| `복합형` +0.2 | 방문 신호가 있지만 평일 생활권·업무·거주 신호도 섞여 있어 약한 가산 적용 |

생활인구 시간대 기준:

| 구분 | 시간 |
|---|---|
| 낮 시간대 | 9~18시 |
| 심야 시간대 | 22~6시 |

방문 패턴 분류는 서울 행정동 전체 분포의 60번째 백분위수를 기준으로 한다. `weekend_2030_ratio`, `weekday_2030_ratio`, `evening_2030_ratio`, `late_night_2030_ratio` 각각의 60th percentile을 넘는지를 보고 `목적 방문형`, `복합형`, `생활 밀착형`, `불명확`을 나눈다.

## 13. 최종 해석 순서

1. `residential_filter`로 거주성 후보인지 먼저 분리한다.
2. `enrichment_status`로 매출·생활인구가 실제 결합됐는지 확인한다.
3. `final_candidate_score`로 최종 상권 후보 우선순위를 본다.
4. `mobility_signal_score`로 이동 신호 자체가 강한지 확인한다.
5. `cnt_2030`, `share_2030`, `origin_diversity`로 규모·집중도·광역성을 확인한다.
6. `evening_2030_ratio`, `weekend_2030_ratio`, `visit_pattern_type`으로 방문 성격을 확인한다.
7. `young_single_ratio`, `residential_dominance_score`로 자취/거주성 해석 위험을 확인한다.
8. `trend_candidate_score`, `score_slope`, `top20_visitor_months`로 장기 안정성과 상승/하락을 확인한다.
