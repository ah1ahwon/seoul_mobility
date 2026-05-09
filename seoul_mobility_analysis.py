"""
Seoul 2030 mobility analysis starter script.

Purpose
-------
This file collects the workflow built so far:

1. Read archived Seoul mobility/transport source files.
2. Clean subway station daily board/alight data.
3. Clean bus stop-route hourly board/alight data.
4. Analyze capital-region living-migration OD data for 2030 destination demand.
5. Save processed CSVs and a simple top-20 Markdown report.

Data archive expected at:
    /Users/jeong-awon/Documents/seoul-commercial-area-forecast/data_archive

Run from this folder:
    python3 seoul_mobility_analysis.py

If pandas is missing:
    python3 -m pip install pandas numpy

Important notes
---------------
- Subway CSV is UTF-8 with BOM.
- Bus CSV is CP949 encoded.
- Living-migration ZIP contains a large CSV, so this script reads it in chunks.
- The current score is for first-pass candidate discovery, not final prediction.
- Add an administrative-dong mapping table next so codes can be translated to names.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from zipfile import ZipFile


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
ARCHIVE_DIR = PROJECT_ROOT / "data_archive"
RAW_DIR = ARCHIVE_DIR / "raw"

OUTPUT_ROOT = PROJECT_ROOT / "output"
PROCESSED_DIR = OUTPUT_ROOT / "processed"
REPORTS_DIR = OUTPUT_ROOT / "reports"

SUBWAY_CSV = RAW_DIR / "CARD_SUBWAY_MONTH_202604.csv"
BUS_CSV = RAW_DIR / "bus_time_station_202604.csv"
LIVING_MIGRATION_ZIP = RAW_DIR / "seoul_purpose_admdong4_in_20260331.zip"
ADMIN_DONG_AREA_ZIP = RAW_DIR / "seoul_admin_dong_area.zip"


def ensure_output_dirs() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Subway preprocessing
# ---------------------------------------------------------------------------

def clean_subway(input_path: Path = SUBWAY_CSV) -> pd.DataFrame:
    """Clean Seoul subway station daily board/alight data."""
    df = pd.read_csv(input_path, encoding="utf-8-sig", index_col=False)
    df = df.dropna(axis=1, how="all")
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    df = df.rename(
        columns={
            "사용일자": "date",
            "노선명": "line_name",
            "역명": "station_name",
            "승차총승객수": "board_count",
            "하차총승객수": "alight_count",
            "등록일자": "registered_date",
        }
    )

    df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d", errors="coerce")
    df["registered_date"] = pd.to_datetime(
        df["registered_date"].astype(str), format="%Y%m%d", errors="coerce"
    )

    for col in ["board_count", "alight_count"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")

    df["total_count"] = df["board_count"] + df["alight_count"]
    df["weekday"] = df["date"].dt.day_name()
    df["is_weekend"] = df["date"].dt.dayofweek >= 5
    return df


# ---------------------------------------------------------------------------
# Bus preprocessing
# ---------------------------------------------------------------------------

def clean_bus(input_path: Path = BUS_CSV) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Clean Seoul bus route-stop hourly board/alight data."""
    df = pd.read_csv(input_path, encoding="cp949", index_col=False, low_memory=False)
    df = df.dropna(axis=1, how="all")

    df = df.rename(
        columns={
            "사용년월": "year_month",
            "노선번호": "route_no",
            "노선명": "route_name",
            "표준버스정류장ID": "station_id",
            "버스정류장ARS번호": "ars_id",
            "역명": "station_name",
            "등록일자": "registered_date",
        }
    )

    board_cols = [col for col in df.columns if "시승차총승객수" in col]
    alight_cols = [col for col in df.columns if "시하차총승객수" in col]

    for col in board_cols + alight_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")

    base_cols = [
        col
        for col in ["year_month", "route_no", "route_name", "station_id", "ars_id", "station_name"]
        if col in df.columns
    ]

    df["board_total"] = df[board_cols].sum(axis=1) if board_cols else 0
    df["alight_total"] = df[alight_cols].sum(axis=1) if alight_cols else 0
    df["total_count"] = df["board_total"] + df["alight_total"]

    hourly_parts = []
    for hour in range(24):
        board_col = f"{hour}시승차총승객수"
        alight_col = f"{hour}시하차총승객수"
        if board_col not in df.columns or alight_col not in df.columns:
            continue

        part = df[base_cols].copy()
        part["hour"] = hour
        part["board_count"] = df[board_col]
        part["alight_count"] = df[alight_col]
        part["total_count"] = part["board_count"] + part["alight_count"]
        hourly_parts.append(part)

    summary = df[base_cols + ["board_total", "alight_total", "total_count"]]
    hourly = pd.concat(hourly_parts, ignore_index=True) if hourly_parts else pd.DataFrame()
    return summary, hourly


# ---------------------------------------------------------------------------
# Administrative-dong code mapping
# ---------------------------------------------------------------------------

def read_admin_dong_mapping(input_path: Path = ADMIN_DONG_AREA_ZIP) -> pd.DataFrame:
    """
    Read ADSTRD_CD -> ADSTRD_NM mapping from the archived Seoul admin-dong
    area shapefile ZIP. This avoids requiring geopandas/fiona.
    """
    with ZipFile(input_path) as zf:
        dbf_name = next(name for name in zf.namelist() if name.lower().endswith(".dbf"))
        data = zf.read(dbf_name)

    record_count = int.from_bytes(data[4:8], "little")
    header_len = int.from_bytes(data[8:10], "little")
    record_len = int.from_bytes(data[10:12], "little")

    fields = []
    pos = 32
    while data[pos] != 0x0D:
        desc = data[pos : pos + 32]
        name = desc[:11].split(b"\x00", 1)[0].decode("ascii", errors="ignore")
        field_type = chr(desc[11])
        length = desc[16]
        fields.append((name, field_type, length))
        pos += 32

    rows = []
    for record_idx in range(record_count):
        start = header_len + record_idx * record_len
        record = data[start : start + record_len]
        if not record or record[0:1] == b"*":
            continue

        offset = 1
        row = {}
        for name, field_type, length in fields:
            raw = record[offset : offset + length]
            offset += length
            text = raw.decode("utf-8", errors="ignore").strip()
            if field_type == "N":
                row[name] = pd.to_numeric(text, errors="coerce")
            else:
                row[name] = text
        rows.append(row)

    mapping = pd.DataFrame(rows)
    mapping = mapping.rename(
        columns={
            "ADSTRD_CD": "admdong_cd",
            "ADSTRD_NM": "admdong_name",
            "XCNTS_VALU": "center_x",
            "YDNTS_VALU": "center_y",
            "RELM_AR": "area_sqm",
        }
    )
    mapping["admdong_cd"] = mapping["admdong_cd"].astype(str)
    mapping["gu_cd"] = mapping["admdong_cd"].str[:5]
    return mapping


# ---------------------------------------------------------------------------
# Living-migration analysis
# ---------------------------------------------------------------------------

def zscore(series: pd.Series) -> pd.Series:
    """Return a stable z-score series."""
    std = series.std(ddof=0)
    if std == 0 or pd.isna(std):
        return pd.Series(0.0, index=series.index)
    return (series - series.mean()) / std


def summarize_living_migration(
    input_path: Path = LIVING_MIGRATION_ZIP,
    chunksize: int = 500_000,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Summarize 2030 destination demand by administrative dong.

    Current score:
        z(log 2030 destination arrivals)
      + z(2030 share among total arrivals)
      + z(log origin diversity)
      + z(evening 2030 ratio)
    """
    usecols = [
        "o_admdong_cd",
        "d_admdong_cd",
        "st_time_cd",
        "move_dist",
        "move_time",
        "2030_cnt",
        "total_cnt",
        "etl_ymd",
    ]

    dest_parts = []
    hour_parts = []
    origin_parts = []

    for chunk in pd.read_csv(
        input_path,
        compression="zip",
        usecols=usecols,
        dtype={
            "o_admdong_cd": "string",
            "d_admdong_cd": "string",
            "st_time_cd": "string",
            "etl_ymd": "string",
        },
        chunksize=chunksize,
    ):
        for col in ["move_dist", "move_time", "2030_cnt", "total_cnt"]:
            chunk[col] = pd.to_numeric(chunk[col], errors="coerce").fillna(0.0)

        chunk["weighted_move_time_2030"] = chunk["move_time"] * chunk["2030_cnt"]
        chunk["weighted_move_dist_2030"] = chunk["move_dist"] * chunk["2030_cnt"]
        chunk["is_evening"] = chunk["st_time_cd"].astype(str).str.zfill(2).isin(
            ["18", "19", "20", "21", "22", "23"]
        )
        chunk["evening_2030_cnt"] = np.where(chunk["is_evening"], chunk["2030_cnt"], 0.0)

        dest_parts.append(
            chunk.groupby("d_admdong_cd", as_index=False).agg(
                cnt_2030=("2030_cnt", "sum"),
                total_cnt=("total_cnt", "sum"),
                weighted_move_time_2030=("weighted_move_time_2030", "sum"),
                weighted_move_dist_2030=("weighted_move_dist_2030", "sum"),
                evening_2030_cnt=("evening_2030_cnt", "sum"),
                row_count=("d_admdong_cd", "size"),
            )
        )

        hour_parts.append(
            chunk.groupby(["d_admdong_cd", "st_time_cd"], as_index=False).agg(
                cnt_2030=("2030_cnt", "sum"),
                total_cnt=("total_cnt", "sum"),
            )
        )

        origin_parts.append(
            chunk.loc[chunk["2030_cnt"] > 0, ["d_admdong_cd", "o_admdong_cd"]].drop_duplicates()
        )

    dest = pd.concat(dest_parts, ignore_index=True)
    dest = dest.groupby("d_admdong_cd", as_index=False).sum(numeric_only=True)

    hourly = pd.concat(hour_parts, ignore_index=True)
    hourly = hourly.groupby(["d_admdong_cd", "st_time_cd"], as_index=False).sum(numeric_only=True)

    origins = pd.concat(origin_parts, ignore_index=True).drop_duplicates()
    origin_counts = origins.groupby("d_admdong_cd", as_index=False).agg(
        origin_diversity=("o_admdong_cd", "nunique")
    )

    dest = dest.merge(origin_counts, on="d_admdong_cd", how="left")
    dest["origin_diversity"] = dest["origin_diversity"].fillna(0).astype("int64")
    dest["share_2030"] = np.where(dest["total_cnt"] > 0, dest["cnt_2030"] / dest["total_cnt"], 0.0)
    dest["avg_move_time_2030"] = np.where(
        dest["cnt_2030"] > 0,
        dest["weighted_move_time_2030"] / dest["cnt_2030"],
        0.0,
    )
    dest["avg_move_dist_2030"] = np.where(
        dest["cnt_2030"] > 0,
        dest["weighted_move_dist_2030"] / dest["cnt_2030"],
        0.0,
    )
    dest["evening_2030_ratio"] = np.where(
        dest["cnt_2030"] > 0,
        dest["evening_2030_cnt"] / dest["cnt_2030"],
        0.0,
    )

    dest["mobility_score"] = (
        zscore(np.log1p(dest["cnt_2030"]))
        + zscore(dest["share_2030"])
        + zscore(np.log1p(dest["origin_diversity"]))
        + zscore(dest["evening_2030_ratio"])
    )

    dest = dest.sort_values(["mobility_score", "cnt_2030"], ascending=False)
    hourly = hourly.sort_values(["d_admdong_cd", "st_time_cd"])
    return dest, hourly


def classify_candidate(row: pd.Series, quantiles: dict[str, float]) -> str:
    high_cnt = row["cnt_2030"] >= quantiles["cnt_2030_75"]
    high_share = row["share_2030"] >= quantiles["share_2030_75"]
    high_diversity = row["origin_diversity"] >= quantiles["origin_diversity_75"]
    high_evening = row["evening_2030_ratio"] >= quantiles["evening_2030_ratio_75"]
    short_trip = row["avg_move_time_2030"] <= quantiles["avg_move_time_25"]

    if high_cnt and high_share and high_diversity and high_evening:
        return "핵심 후보형"
    if high_cnt and high_share and short_trip and not high_diversity:
        return "생활권형"
    if high_cnt and high_diversity and not short_trip:
        return "광역 목적지형"
    if high_evening and row["cnt_2030"] >= quantiles["cnt_2030_50"]:
        return "야간 소비형"
    if high_share and row["cnt_2030"] < quantiles["cnt_2030_50"]:
        return "소규모 2030 집중형"
    return "관찰 필요"


def enrich_destination_summary(dest: pd.DataFrame, admin_mapping: pd.DataFrame) -> pd.DataFrame:
    enriched = dest.copy()
    enriched["d_admdong_cd"] = enriched["d_admdong_cd"].astype(str)

    mapping = admin_mapping.rename(
        columns={
            "admdong_cd": "d_admdong_cd",
            "admdong_name": "d_admdong_name",
            "center_x": "d_center_x",
            "center_y": "d_center_y",
            "area_sqm": "d_area_sqm",
        }
    )
    enriched = enriched.merge(
        mapping[["d_admdong_cd", "d_admdong_name", "d_center_x", "d_center_y", "d_area_sqm"]],
        on="d_admdong_cd",
        how="left",
    )

    quantiles = {
        "cnt_2030_25": enriched["cnt_2030"].quantile(0.25),
        "cnt_2030_50": enriched["cnt_2030"].quantile(0.50),
        "cnt_2030_75": enriched["cnt_2030"].quantile(0.75),
        "share_2030_75": enriched["share_2030"].quantile(0.75),
        "origin_diversity_75": enriched["origin_diversity"].quantile(0.75),
        "evening_2030_ratio_75": enriched["evening_2030_ratio"].quantile(0.75),
        "avg_move_time_25": enriched["avg_move_time_2030"].quantile(0.25),
    }
    enriched["candidate_type"] = enriched.apply(classify_candidate, axis=1, quantiles=quantiles)

    display_cols = [
        "d_admdong_cd",
        "d_admdong_name",
        "candidate_type",
        "mobility_score",
        "cnt_2030",
        "share_2030",
        "origin_diversity",
        "evening_2030_ratio",
        "avg_move_time_2030",
        "avg_move_dist_2030",
        "total_cnt",
        "d_center_x",
        "d_center_y",
    ]
    other_cols = [col for col in enriched.columns if col not in display_cols]
    return enriched[display_cols + other_cols]


def summarize_transport_patterns(
    subway: pd.DataFrame,
    bus_summary: pd.DataFrame,
    bus_hourly: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Create transport-only supporting summaries."""
    subway_station = (
        subway.groupby(["station_name"], as_index=False)
        .agg(
            subway_board_count=("board_count", "sum"),
            subway_alight_count=("alight_count", "sum"),
            subway_total_count=("total_count", "sum"),
            subway_weekend_total=("total_count", lambda s: s[subway.loc[s.index, "is_weekend"]].sum()),
            subway_weekday_total=("total_count", lambda s: s[~subway.loc[s.index, "is_weekend"]].sum()),
        )
        .sort_values("subway_total_count", ascending=False)
    )
    subway_station["subway_weekend_share"] = np.where(
        subway_station["subway_total_count"] > 0,
        subway_station["subway_weekend_total"] / subway_station["subway_total_count"],
        0.0,
    )

    bus_stop = (
        bus_summary.groupby(["station_name"], as_index=False)
        .agg(
            bus_board_total=("board_total", "sum"),
            bus_alight_total=("alight_total", "sum"),
            bus_total_count=("total_count", "sum"),
            route_count=("route_no", "nunique"),
        )
        .sort_values("bus_total_count", ascending=False)
    )

    bus_hour = (
        bus_hourly.groupby("hour", as_index=False)
        .agg(
            board_count=("board_count", "sum"),
            alight_count=("alight_count", "sum"),
            total_count=("total_count", "sum"),
        )
        .sort_values("hour")
    )
    return subway_station, bus_stop, bus_hour


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    """Make a Markdown table without requiring the optional tabulate package."""
    out = df.copy()
    for col in out.select_dtypes(include=["float"]).columns:
        out[col] = out[col].map(lambda value: f"{value:.3f}")

    columns = list(out.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in out.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def write_top20_report(dest: pd.DataFrame) -> None:
    cols = [
        "d_admdong_cd",
        "d_admdong_name",
        "candidate_type",
        "mobility_score",
        "cnt_2030",
        "share_2030",
        "origin_diversity",
        "evening_2030_ratio",
        "avg_move_time_2030",
    ]
    table = dataframe_to_markdown(dest.head(20)[cols])

    report = (
        "# 2030 도착 이동 상위 행정동 Top 20\n\n"
        "이 보고서는 수도권 생활이동 샘플을 기준으로 2030 도착 이동 신호가 강한 "
        "행정동을 순위화한 결과입니다.\n\n"
        "점수 = z(log 2030 도착량) + z(2030 비중) + "
        "z(log 출발지 다양성) + z(저녁 2030 비중).\n\n"
        "이 점수는 최종 예측값이 아니라 후보 발굴용 1차 점수입니다.\n\n"
        f"{table}\n"
    )
    (REPORTS_DIR / "living_migration_2030_top20.md").write_text(report, encoding="utf-8")


def write_interpretation_report(dest: pd.DataFrame, subway_station: pd.DataFrame, bus_stop: pd.DataFrame) -> None:
    type_counts = dest["candidate_type"].value_counts().reset_index()
    type_counts.columns = ["candidate_type", "dong_count"]

    report = (
        "# 2030 이동 기반 상권 후보 해석 보고서\n\n"
        "## 결과의 의미\n\n"
        "현재 결과는 상권 성장을 확정하는 분석이 아니라, 2030 도착 이동이 강하게 나타나는 "
        "행정동을 먼저 걸러내는 1차 후보 발굴 결과입니다. 하루치 생활이동 샘플을 기준으로 "
        "했기 때문에 반복 관측과 소비/점포 데이터 결합 전까지는 후보 신호로 해석해야 합니다.\n\n"
        "## 후보 유형 분포\n\n"
        f"{dataframe_to_markdown(type_counts)}\n\n"
        "## 유형 해석\n\n"
        "- 핵심 후보형: 2030 도착량, 2030 비중, 출발지 다양성, 저녁 이동 비중이 모두 높은 지역입니다.\n"
        "- 생활권형: 2030 이동은 많지만 이동 시간이 짧고 유입 출발지가 제한적인 지역입니다. 주거 생활권 이동일 수 있습니다.\n"
        "- 광역 목적지형: 여러 출발지에서 비교적 긴 시간을 들여 방문하는 지역입니다. 이미 목적지성이 강한 상권/대학가/업무지구일 가능성이 큽니다.\n"
        "- 야간 소비형: 저녁 시간대 2030 유입 비중이 높은 지역입니다. 식음료, 술집, 문화, 약속 수요와 관련될 수 있습니다.\n"
        "- 소규모 2030 집중형: 전체 규모는 작지만 2030 비중이 높은 지역입니다. 초기 신호 후보로 추적할 가치가 있습니다.\n"
        "- 관찰 필요: 하루치 이동 데이터만으로는 유형을 강하게 판단하기 어려운 지역입니다.\n\n"
        "## 2026년 4월 지하철 승하차 상위역\n\n"
        f"{dataframe_to_markdown(subway_station.head(15)[['station_name', 'subway_total_count', 'subway_weekend_share']])}\n\n"
        "## 2026년 4월 버스 승하차 상위 정류장\n\n"
        f"{dataframe_to_markdown(bus_stop.head(15)[['station_name', 'bus_total_count', 'route_count']])}\n\n"
        "## 현재 한계\n\n"
        "지하철/버스 요약은 아직 행정동 공간 경계와 직접 결합하지 않았습니다. "
        "따라서 교통 지표는 후보 행정동을 설명하는 보조 맥락으로만 사용해야 합니다. "
        "다음 단계에서 지하철역/버스정류장 좌표를 행정동 경계와 공간 결합하면 "
        "행정동별 교통 접근성 지표로 바꿀 수 있습니다.\n"
    )
    (REPORTS_DIR / "interpretation_report.md").write_text(report, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def run_all() -> None:
    ensure_output_dirs()

    print("0. Reading administrative-dong mapping...")
    admin_mapping = read_admin_dong_mapping()
    admin_mapping_path = PROCESSED_DIR / "admin_dong_mapping.csv"
    admin_mapping.to_csv(admin_mapping_path, index=False, encoding="utf-8-sig")
    print(f"   saved: {admin_mapping_path} ({len(admin_mapping):,} rows)")

    print("1. Cleaning subway data...")
    subway = clean_subway()
    subway_path = PROCESSED_DIR / "subway_station_daily.csv"
    subway.to_csv(subway_path, index=False, encoding="utf-8-sig")
    print(f"   saved: {subway_path} ({len(subway):,} rows)")

    print("2. Cleaning bus data...")
    bus_summary, bus_hourly = clean_bus()
    bus_summary_path = PROCESSED_DIR / "bus_stop_route_summary.csv"
    bus_hourly_path = PROCESSED_DIR / "bus_stop_route_hourly.csv"
    bus_summary.to_csv(bus_summary_path, index=False, encoding="utf-8-sig")
    bus_hourly.to_csv(bus_hourly_path, index=False, encoding="utf-8-sig")
    print(f"   saved: {bus_summary_path} ({len(bus_summary):,} rows)")
    print(f"   saved: {bus_hourly_path} ({len(bus_hourly):,} rows)")

    print("3. Analyzing 2030 living-migration OD data...")
    dest, hourly = summarize_living_migration()
    dest = enrich_destination_summary(dest, admin_mapping)
    dest_path = PROCESSED_DIR / "living_migration_2030_destination_summary.csv"
    hourly_path = PROCESSED_DIR / "living_migration_2030_destination_hourly.csv"
    dest.to_csv(dest_path, index=False, encoding="utf-8-sig")
    hourly.to_csv(hourly_path, index=False, encoding="utf-8-sig")
    write_top20_report(dest)
    print("4. Creating transport support summaries and interpretation report...")
    subway_station, bus_stop, bus_hour = summarize_transport_patterns(subway, bus_summary, bus_hourly)
    subway_station_path = PROCESSED_DIR / "subway_station_summary.csv"
    bus_stop_path = PROCESSED_DIR / "bus_stop_summary.csv"
    bus_hour_path = PROCESSED_DIR / "bus_hourly_citywide_summary.csv"
    subway_station.to_csv(subway_station_path, index=False, encoding="utf-8-sig")
    bus_stop.to_csv(bus_stop_path, index=False, encoding="utf-8-sig")
    bus_hour.to_csv(bus_hour_path, index=False, encoding="utf-8-sig")
    write_interpretation_report(dest, subway_station, bus_stop)
    print(f"   saved: {subway_station_path} ({len(subway_station):,} rows)")
    print(f"   saved: {bus_stop_path} ({len(bus_stop):,} rows)")
    print(f"   saved: {bus_hour_path} ({len(bus_hour):,} rows)")
    print(f"   saved: {REPORTS_DIR / 'interpretation_report.md'}")
    print(f"   saved: {dest_path} ({len(dest):,} rows)")
    print(f"   saved: {hourly_path} ({len(hourly):,} rows)")
    print(f"   saved: {REPORTS_DIR / 'living_migration_2030_top20.md'}")

    print("\nTop 10 destination administrative dongs:")
    print(
        dest.head(10)[
            ["d_admdong_cd", "d_admdong_name", "candidate_type", "mobility_score", "cnt_2030", "share_2030", "origin_diversity"]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    run_all()
