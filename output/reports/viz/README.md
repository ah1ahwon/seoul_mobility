# Visualization Guide

이 폴더의 PNG 파일은 2030 이동 기반 상권 후보를 해석하기 위한 보조 시각화 자료입니다. `run_###/` 폴더는 실행별 보관본이며, 루트의 PNG는 최근 또는 대표 산출물입니다.

| 이미지 | 시각화 자료 | 목적/해석 포인트 |
|---|---|---|
| [`01_top15_monthly_score_trend.png`](01_top15_monthly_score_trend.png) | 방문성 후보 Top 15 월별 보정 점수 추세 | 최신 월 기준 방문성 후보 상위 15개 행정동의 `adjusted_mobility_score`가 월별로 어떻게 움직였는지 보여주는 선 그래프입니다. 특정 후보가 일시적으로 튄 곳인지, 여러 달 동안 강세를 유지한 곳인지 확인합니다. |
| [`02_heatmap_dong_month.png`](02_heatmap_dong_month.png) | 방문성 후보 Top 30 행정동-월 히트맵 | 장기 평균 또는 추세 점수가 높은 방문성 후보 30개 행정동을 행으로, 월을 열로 놓고 `adjusted_mobility_score`를 색으로 표시합니다. 여러 후보의 계절성, 공통 상승/하락 구간, 특정 월 이상치를 비교합니다. |
| [`03_score_slope_ranking.png`](03_score_slope_ranking.png) | 상승/하락 기울기 Top 15 비교 | 방문성 후보 중 `score_slope`가 큰 상승 후보 15개와 하락 후보 15개를 함께 보여주는 막대 그래프입니다. 새로 강해지는 지역과 약해지는 지역을 빠르게 분리합니다. |
| [`04_latest_month_top20.png`](04_latest_month_top20.png) | 최신 월 방문성 후보 Top 20 | 최신 월의 `adjusted_mobility_score` 기준 방문성 후보 상위 20개 행정동을 정렬한 막대 그래프입니다. 현재 시점에서 우선 검토할 후보지를 뽑는 데 사용하는 직접적인 순위 자료입니다. |
| [`05_candidate_type_distribution.png`](05_candidate_type_distribution.png) | 후보 유형과 거주성 필터 분포 | 최신 월 기준 `candidate_type`별 행정동 개수와 비율을 `residential_filter`로 나누어 보여주는 누적 막대 그래프입니다. 이동 성격이 실제 방문성 후보인지 거주성 후보인지 점검합니다. |
| [`06_total_2030_monthly_trend.png`](06_total_2030_monthly_trend.png) | 서울 전체 2030 유입량 월별 추이 | 월별 전체 행정동의 `cnt_2030` 합계를 보여주는 선 그래프입니다. 후보 점수 변화가 특정 행정동의 변화인지, 전체 2030 이동량의 월별 변동 때문인지 구분합니다. 주말 스냅샷 월은 별도 표시합니다. |
| [`07_bump_chart_visitor_rank.png`](07_bump_chart_visitor_rank.png) | 방문성 후보 Top 10 월별 순위 변화 | 최신 월 상위 10개 방문성 후보의 월별 순위 변화를 보여주는 bump chart입니다. 점수 절대값보다 후보 간 상대 순위가 얼마나 안정적인지, 순위가 급등락하는 후보가 있는지 확인합니다. |
| [`08_visit_pattern_type.png`](08_visit_pattern_type.png) | 방문 패턴 유형 분포 | `visit_pattern_type`별 행정동 수를 보여주는 가로 막대 그래프입니다. 목적 방문형, 복합형, 생활 밀착형, 불명확 유형의 전체 분포를 요약합니다. |
| [`09_commercial_potential_scatter.png`](09_commercial_potential_scatter.png) | 이동 보정 점수와 상권 잠재력 점수 산점도 | `adjusted_mobility_score`를 x축, `commercial_potential_score`를 y축으로 놓은 산점도입니다. 이동 신호는 강하지만 상권 레이어가 약한 곳, 반대로 매출·용도지역·유동인구 보정으로 상권 잠재력이 올라간 곳을 구분합니다. |
| [`10_bjdong_top20.png`](10_bjdong_top20.png) | 법정동 상권 잠재력 Top 20 | 행정동 결과를 법정동 단위로 집계한 뒤 `commercial_potential_score` 기준 상위 20개를 보여주는 막대 그래프입니다. 실제 입지 검토에서 행정동보다 익숙한 법정동 단위로 후보를 비교합니다. |
