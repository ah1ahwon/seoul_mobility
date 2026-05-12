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

import os
import subprocess
import calendar
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import zipfile
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import re


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
ARCHIVE_DIR = PROJECT_ROOT / "data_archive"

# SEOUL_RAW_DIR / SEOUL_OUTPUT_DIR env vars override defaults — used in Colab/Google Drive setups
_raw_env = os.environ.get("SEOUL_RAW_DIR")
RAW_DIR = Path(_raw_env) if _raw_env else ARCHIVE_DIR / "raw"

_output_env = os.environ.get("SEOUL_OUTPUT_DIR")
OUTPUT_ROOT = Path(_output_env) if _output_env else PROJECT_ROOT / "output"
PROCESSED_DIR = OUTPUT_ROOT / "processed"
REPORTS_DIR = OUTPUT_ROOT / "reports"

SUBWAY_CSV = RAW_DIR / "CARD_SUBWAY_MONTH_202604.csv"
BUS_CSV = RAW_DIR / "bus_time_station_202604.csv"
LIVING_MIGRATION_PATTERN = "seoul_purpose_admdong4_in_202603*.zip"
LIVING_MIGRATION_MONTH_END_MANIFEST = ARCHIVE_DIR / "metadata" / "living_migration_month_end_manifest.csv"
ADMIN_DONG_AREA_ZIP = RAW_DIR / "seoul_admin_dong_area.zip"
LIVING_INTEREST_XLSX = RAW_DIR / "seoul_living_interest_groups_202512.xlsx"

# 법정동 매핑 (행정동코드 → 법정동코드/법정동명)
# download_bjdong_mapping.sh 로 생성
BJDONG_MAPPING_CSV = ARCHIVE_DIR / "metadata" / "bjdong_admdong_mapping.csv"

# GIS: 서울시 용도지역지구도 + 행정동 경계 shapefile ZIP
# 서울 열린데이터광장 / 국가공간정보포털에서 다운로드 (download_gis_data.sh)
LAND_USE_ZIP = RAW_DIR / "seoul_land_use_zone.zip"
ADMIN_DONG_BOUNDARY_ZIP = RAW_DIR / "seoul_admin_dong_boundary.zip"

# 서울시 우리마을가게 상권분석서비스 — 행정동별 추정매출 (download_commercial_sales.sh)
COMMERCIAL_SALES_CSV = RAW_DIR / "seoul_commercial_sales_latest.csv"

# 서울 생활인구 — 행정동별 시간대별 추정 유동인구 (download_living_population.sh)
LIVING_POPULATION_CSV = RAW_DIR / "seoul_living_population_latest.csv"

# 필수 좌표 파일: 행정동 경계와 공간 결합해 교통 접근성 지표 생성
SUBWAY_STATION_COORD_CSV = RAW_DIR / "subway_station_coordinates.csv"
BUS_STOP_COORD_CSV = RAW_DIR / "bus_stop_coordinates.csv"

SEOUL_GU_CODE_TO_NAME = {
    "11110": "종로구",
    "11140": "중구",
    "11170": "용산구",
    "11200": "성동구",
    "11215": "광진구",
    "11230": "동대문구",
    "11260": "중랑구",
    "11290": "성북구",
    "11305": "강북구",
    "11320": "도봉구",
    "11350": "노원구",
    "11380": "은평구",
    "11410": "서대문구",
    "11440": "마포구",
    "11470": "양천구",
    "11500": "강서구",
    "11530": "구로구",
    "11545": "금천구",
    "11560": "영등포구",
    "11590": "동작구",
    "11620": "관악구",
    "11650": "서초구",
    "11680": "강남구",
    "11710": "송파구",
    "11740": "강동구",
}


def ensure_output_dirs() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def allow_partial_run() -> bool:
    """Return True only for development runs that intentionally allow missing required layers."""
    return os.environ.get("SEOUL_ALLOW_PARTIAL") == "1"


def require_input(path: Path, label: str, hint: str = "") -> bool:
    """Require an input file unless SEOUL_ALLOW_PARTIAL=1 is explicitly set."""
    if path.exists():
        return True
    message = f"{label} 파일 없음: {path}"
    if hint:
        message += f"\n   준비 방법: {hint}"
    if allow_partial_run():
        print(f"   {message} — SEOUL_ALLOW_PARTIAL=1 이므로 건너뜀")
        return False
    raise FileNotFoundError(message)


def validate_required_inputs() -> None:
    """Fail fast before expensive processing if required final-analysis inputs are missing."""
    required_files = [
        (ADMIN_DONG_AREA_ZIP, "행정동 코드/명칭 매핑", "bash data_archive/scripts/download_latest_examples.sh"),
        (LIVING_INTEREST_XLSX, "서울 시민생활 1인가구", "bash data_archive/scripts/download_latest_examples.sh"),
        (SUBWAY_CSV, "지하철 승하차", "bash data_archive/scripts/download_latest_examples.sh"),
        (BUS_CSV, "버스 승하차", "bash data_archive/scripts/download_latest_examples.sh"),
        (COMMERCIAL_SALES_CSV, "매출 데이터", "bash data_archive/scripts/download_commercial_sales.sh"),
        (LIVING_POPULATION_CSV, "생활인구 데이터", "bash data_archive/scripts/download_living_population.sh"),
        (LAND_USE_ZIP, "용도지역", "bash data_archive/scripts/download_gis_data.sh"),
        (ADMIN_DONG_BOUNDARY_ZIP, "행정동 경계", "bash data_archive/scripts/download_gis_data.sh"),
        (SUBWAY_STATION_COORD_CSV, "지하철역 좌표", "raw/subway_station_coordinates.csv 준비"),
        (BUS_STOP_COORD_CSV, "버스정류장 좌표", "raw/bus_stop_coordinates.csv 준비"),
        (BJDONG_MAPPING_CSV, "행정동-법정동 매핑", "bash data_archive/scripts/download_bjdong_mapping.sh"),
    ]
    missing_messages = []
    for path, label, hint in required_files:
        if not path.exists():
            missing_messages.append(f"- {label}: {path}\n  준비 방법: {hint}")

    living_paths = sorted(RAW_DIR.glob(LIVING_MIGRATION_PATTERN))
    if not living_paths:
        missing_messages.append(
            f"- 2026년 3월 생활이동 일별 ZIP: {RAW_DIR / LIVING_MIGRATION_PATTERN}\n"
            "  준비 방법: bash data_archive/scripts/download_living_migration_202603.sh"
        )

    if missing_messages and allow_partial_run():
        print("0. Required input preflight...")
        print("   SEOUL_ALLOW_PARTIAL=1 — missing inputs will be skipped where supported:")
        print("\n".join(missing_messages))
        return
    if missing_messages:
        raise FileNotFoundError(
            "필수 입력 파일이 부족해 분석을 시작하지 않습니다.\n"
            + "\n".join(missing_messages)
            + "\n\n개발용 부분 실행이 필요할 때만 SEOUL_ALLOW_PARTIAL=1을 설정하세요."
        )

    print("0. Required input preflight passed.")


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


def _xlsx_col_to_idx(cell_ref: str) -> int:
    match = re.match(r"([A-Z]+)", cell_ref)
    if not match:
        return 0
    idx = 0
    for char in match.group(1):
        idx = idx * 26 + ord(char) - 64
    return idx - 1


def read_simple_xlsx(input_path: Path) -> pd.DataFrame:
    """
    Read the first worksheet of a simple XLSX file using only the standard library.

    This project uses it to avoid requiring openpyxl for the Seoul citizen-living
    interest-group file.
    """
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with ZipFile(input_path) as zf:
        shared_strings = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", ns):
                shared_strings.append("".join(t.text or "" for t in item.findall(".//m:t", ns)))

        rows = []
        for _, row in ET.iterparse(zf.open("xl/worksheets/sheet1.xml"), events=("end",)):
            if not row.tag.endswith("row"):
                continue

            values = []
            for cell in row:
                if not cell.tag.endswith("c"):
                    continue
                col_idx = _xlsx_col_to_idx(cell.attrib.get("r", "A"))
                while len(values) <= col_idx:
                    values.append(None)

                value_node = cell.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                if value_node is None:
                    value = None
                elif cell.attrib.get("t") == "s":
                    value = shared_strings[int(value_node.text)]
                else:
                    value = value_node.text
                values[col_idx] = value

            rows.append(values)
            row.clear()

    headers = rows[0]
    while headers and headers[-1] is None:
        headers = headers[:-1]
    width = len(headers)
    data = [row[:width] + [None] * max(0, width - len(row)) for row in rows[1:]]
    return pd.DataFrame(data, columns=headers)


def summarize_young_single_households(input_path: Path = LIVING_INTEREST_XLSX) -> pd.DataFrame:
    """
    Build an administrative-dong residential dominance metric from Seoul citizen-living data.

    Uses 20, 25, 30, 35 age buckets as the 2030 range and sums both sexes.
    """
    df = read_simple_xlsx(input_path)
    df = df.rename(
        columns={
            "행정동코드": "living_admdong_cd",
            "자치구": "gu_name",
            "행정동명": "admdong_name",
            "성별": "sex",
            "연령대": "age_band",
            "총인구": "population",
            "1인가구수": "single_households",
            "휴일 외출이 적은 집단": "low_weekend_outing_group",
            "외출이 매우 적은 집단(전체)": "very_low_outing_group",
        }
    )

    for col in ["age_band", "population", "single_households", "low_weekend_outing_group", "very_low_outing_group"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    young = df[df["age_band"].isin([20, 25, 30, 35])].copy()
    summary = (
        young.groupby(["gu_name", "admdong_name"], as_index=False)
        .agg(
            living_admdong_cd=("living_admdong_cd", "first"),
            young_population=("population", "sum"),
            young_single_households=("single_households", "sum"),
            young_low_weekend_outing_group=("low_weekend_outing_group", "sum"),
            young_very_low_outing_group=("very_low_outing_group", "sum"),
        )
    )
    summary["young_single_ratio"] = np.where(
        summary["young_population"] > 0,
        summary["young_single_households"] / summary["young_population"],
        0.0,
    )
    summary["young_homebound_ratio"] = np.where(
        summary["young_population"] > 0,
        (summary["young_low_weekend_outing_group"] + summary["young_very_low_outing_group"])
        / summary["young_population"],
        0.0,
    )
    summary["residential_dominance_score"] = (
        zscore(np.log1p(summary["young_single_households"]))
        + zscore(summary["young_single_ratio"])
        + 0.5 * zscore(summary["young_homebound_ratio"])
    )
    return summary.sort_values("residential_dominance_score", ascending=False)


# ---------------------------------------------------------------------------
# Living-migration analysis
# ---------------------------------------------------------------------------

def zscore(series: pd.Series) -> pd.Series:
    """Return a stable z-score series."""
    std = series.std(ddof=0)
    if std == 0 or pd.isna(std):
        return pd.Series(0.0, index=series.index)
    return (series - series.mean()) / std


def zscore_by_group(df: pd.DataFrame, group_col: str, value: pd.Series) -> pd.Series:
    """Return z-scores calculated within each group."""
    temp = pd.DataFrame({group_col: df[group_col], "value": value}, index=df.index)
    return temp.groupby(group_col)["value"].transform(zscore)


def get_month_end_living_migration_paths(
    manifest_path: Path = LIVING_MIGRATION_MONTH_END_MANIFEST,
) -> list[Path]:
    """Return existing month-end living-migration files listed in the archive manifest."""
    manifest = pd.read_csv(manifest_path, dtype={"yyyymm": "string", "filename": "string"})
    paths = [RAW_DIR / filename for filename in manifest["filename"]]
    existing = [path for path in paths if path.exists()]
    if not existing:
        raise FileNotFoundError(f"No month-end living-migration ZIP files found from: {manifest_path}")
    missing = [path.name for path in paths if not path.exists()]
    if missing:
        print(f"   warning: {len(missing)} month-end files are missing and will be skipped")
    return existing


def get_all_living_migration_paths() -> list[Path]:
    """Return all archived living-migration ZIP files available under RAW_DIR."""
    paths = sorted(RAW_DIR.glob("seoul_purpose_admdong4_in_*.zip"))
    if not paths:
        raise FileNotFoundError(f"No living-migration ZIP files found: {RAW_DIR}")
    return paths


def summarize_living_migration(
    input_paths: list[Path] | None = None,
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
    date_parts = []

    if input_paths is None:
        input_paths = sorted(RAW_DIR.glob(LIVING_MIGRATION_PATTERN))
    if not input_paths:
        raise FileNotFoundError(f"No living-migration ZIP files found: {RAW_DIR / LIVING_MIGRATION_PATTERN}")

    for input_path in input_paths:
        try:
            with zipfile.ZipFile(input_path):
                pass
        except zipfile.BadZipFile:
            print(f"   WARNING: skipping invalid ZIP (possibly an error page): {input_path.name}")
            continue

        print(f"   reading living migration: {input_path.name}")
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
            _hour = chunk["st_time_cd"].astype(str).str.zfill(2)
            chunk["is_evening"] = _hour.isin(["18", "19", "20", "21", "22", "23"])
            chunk["evening_2030_cnt"] = np.where(chunk["is_evening"], chunk["2030_cnt"], 0.0)
            chunk["morning_2030_cnt"] = np.where(_hour.isin(["06", "07", "08"]), chunk["2030_cnt"], 0.0)
            chunk["afternoon_2030_cnt"] = np.where(
                _hour.isin([f"{h:02d}" for h in range(9, 18)]), chunk["2030_cnt"], 0.0
            )
            chunk["late_night_2030_cnt"] = np.where(
                _hour.isin(["23", "00", "01", "02", "03", "04", "05"]), chunk["2030_cnt"], 0.0
            )
            _etl_dt = pd.to_datetime(chunk["etl_ymd"].astype(str), format="%Y%m%d", errors="coerce")
            _wday = _etl_dt.dt.dayofweek  # 0=Mon, 6=Sun
            chunk["weekday_2030_cnt"] = np.where(_wday <= 3, chunk["2030_cnt"], 0.0)  # Mon-Thu
            chunk["friday_2030_cnt"] = np.where(_wday == 4, chunk["2030_cnt"], 0.0)
            chunk["weekend_2030_cnt"] = np.where(_wday >= 5, chunk["2030_cnt"], 0.0)

            dest_parts.append(
                chunk.groupby("d_admdong_cd", as_index=False).agg(
                    cnt_2030=("2030_cnt", "sum"),
                    total_cnt=("total_cnt", "sum"),
                    weighted_move_time_2030=("weighted_move_time_2030", "sum"),
                    weighted_move_dist_2030=("weighted_move_dist_2030", "sum"),
                    evening_2030_cnt=("evening_2030_cnt", "sum"),
                    morning_2030_cnt=("morning_2030_cnt", "sum"),
                    afternoon_2030_cnt=("afternoon_2030_cnt", "sum"),
                    late_night_2030_cnt=("late_night_2030_cnt", "sum"),
                    weekday_2030_cnt=("weekday_2030_cnt", "sum"),
                    friday_2030_cnt=("friday_2030_cnt", "sum"),
                    weekend_2030_cnt=("weekend_2030_cnt", "sum"),
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
            date_parts.append(
                chunk.loc[chunk["2030_cnt"] > 0, ["d_admdong_cd", "etl_ymd"]].drop_duplicates()
            )

    dest = pd.concat(dest_parts, ignore_index=True)
    dest = dest.groupby("d_admdong_cd", as_index=False).sum(numeric_only=True)

    hourly = pd.concat(hour_parts, ignore_index=True)
    hourly = hourly.groupby(["d_admdong_cd", "st_time_cd"], as_index=False).sum(numeric_only=True)

    origins = pd.concat(origin_parts, ignore_index=True).drop_duplicates()
    origin_counts = origins.groupby("d_admdong_cd", as_index=False).agg(
        origin_diversity=("o_admdong_cd", "nunique")
    )
    dates = pd.concat(date_parts, ignore_index=True).drop_duplicates()
    date_counts = dates.groupby("d_admdong_cd", as_index=False).agg(
        active_days=("etl_ymd", "nunique")
    )

    dest = dest.merge(origin_counts, on="d_admdong_cd", how="left")
    dest = dest.merge(date_counts, on="d_admdong_cd", how="left")
    dest["origin_diversity"] = dest["origin_diversity"].fillna(0).astype("int64")
    dest["active_days"] = dest["active_days"].fillna(0).astype("int64")
    dest["date_count"] = len(input_paths)
    dest["avg_daily_2030"] = dest["cnt_2030"] / dest["date_count"]
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
    for _ratio, _cnt in [
        ("morning_2030_ratio", "morning_2030_cnt"),
        ("afternoon_2030_ratio", "afternoon_2030_cnt"),
        ("late_night_2030_ratio", "late_night_2030_cnt"),
        ("weekday_2030_ratio", "weekday_2030_cnt"),
        ("friday_2030_ratio", "friday_2030_cnt"),
        ("weekend_2030_ratio", "weekend_2030_cnt"),
    ]:
        dest[_ratio] = np.where(dest["cnt_2030"] > 0, dest[_cnt] / dest["cnt_2030"], 0.0)

    dest["mobility_score"] = (
        zscore(np.log1p(dest["cnt_2030"]))
        + zscore(dest["share_2030"])
        + zscore(np.log1p(dest["origin_diversity"]))
        + zscore(dest["evening_2030_ratio"])
    )

    dest = dest.sort_values(["mobility_score", "cnt_2030"], ascending=False)
    hourly = hourly.sort_values(["d_admdong_cd", "st_time_cd"])
    return dest, hourly


def summarize_living_migration_monthly(
    input_paths: list[Path] | None = None,
    chunksize: int = 500_000,
) -> pd.DataFrame:
    """
    Summarize 2030 destination demand by month and administrative dong.

    The monthly trend uses one month-end snapshot per month. It is intended for
    long-range direction finding, while the full March 2026 daily files remain
    the detailed current-period view.
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
    origin_parts = []
    date_parts = []
    month_file_counts: dict[str, int] = {}

    if input_paths is None:
        input_paths = get_month_end_living_migration_paths()

    for input_path in input_paths:
        try:
            with zipfile.ZipFile(input_path):
                pass
        except zipfile.BadZipFile:
            print(f"   WARNING: skipping invalid ZIP (possibly an error page): {input_path.name}")
            continue

        print(f"   reading monthly snapshot: {input_path.name}")
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
            chunk["yyyymm"] = chunk["etl_ymd"].astype(str).str[:6]

            for col in ["move_dist", "move_time", "2030_cnt", "total_cnt"]:
                chunk[col] = pd.to_numeric(chunk[col], errors="coerce").fillna(0.0)

            chunk["weighted_move_time_2030"] = chunk["move_time"] * chunk["2030_cnt"]
            chunk["weighted_move_dist_2030"] = chunk["move_dist"] * chunk["2030_cnt"]
            chunk["is_evening"] = chunk["st_time_cd"].astype(str).str.zfill(2).isin(
                ["18", "19", "20", "21", "22", "23"]
            )
            chunk["evening_2030_cnt"] = np.where(chunk["is_evening"], chunk["2030_cnt"], 0.0)

            dest_parts.append(
                chunk.groupby(["yyyymm", "d_admdong_cd"], as_index=False).agg(
                    cnt_2030=("2030_cnt", "sum"),
                    total_cnt=("total_cnt", "sum"),
                    weighted_move_time_2030=("weighted_move_time_2030", "sum"),
                    weighted_move_dist_2030=("weighted_move_dist_2030", "sum"),
                    evening_2030_cnt=("evening_2030_cnt", "sum"),
                    row_count=("d_admdong_cd", "size"),
                )
            )

            origin_parts.append(
                chunk.loc[chunk["2030_cnt"] > 0, ["yyyymm", "d_admdong_cd", "o_admdong_cd"]]
                .drop_duplicates()
            )
            date_parts.append(
                chunk.loc[chunk["2030_cnt"] > 0, ["yyyymm", "d_admdong_cd", "etl_ymd"]]
                .drop_duplicates()
            )

    for input_path in input_paths:
        yyyymm = re.search(r"_(\d{6})\d{2}\.zip$", input_path.name)
        if yyyymm:
            key = yyyymm.group(1)
            month_file_counts[key] = month_file_counts.get(key, 0) + 1

    dest = pd.concat(dest_parts, ignore_index=True)
    dest = dest.groupby(["yyyymm", "d_admdong_cd"], as_index=False).sum(numeric_only=True)

    origins = pd.concat(origin_parts, ignore_index=True).drop_duplicates()
    origin_counts = origins.groupby(["yyyymm", "d_admdong_cd"], as_index=False).agg(
        origin_diversity=("o_admdong_cd", "nunique")
    )
    dates = pd.concat(date_parts, ignore_index=True).drop_duplicates()
    date_counts = dates.groupby(["yyyymm", "d_admdong_cd"], as_index=False).agg(
        active_days=("etl_ymd", "nunique")
    )

    # 월말 스냅샷은 하루짜리 대표일이므로 요일 효과(금요일 vs 화요일 등)나 특수 이벤트가
    # 월별 비교에 섞일 수 있다. 요일 정보를 컬럼으로 추가해 해석 시 참고.
    snapshot_meta = dates.groupby("yyyymm", as_index=False).agg(
        snapshot_date_str=("etl_ymd", "first")
    )
    snapshot_meta["_snap_dt"] = pd.to_datetime(
        snapshot_meta["snapshot_date_str"], format="%Y%m%d", errors="coerce"
    )
    snapshot_meta["snapshot_weekday"] = snapshot_meta["_snap_dt"].dt.strftime("%A")
    snapshot_meta["is_weekend_snapshot"] = snapshot_meta["_snap_dt"].dt.dayofweek >= 5
    snapshot_meta = snapshot_meta.drop(columns=["_snap_dt"])

    dest = dest.merge(origin_counts, on=["yyyymm", "d_admdong_cd"], how="left")
    dest = dest.merge(date_counts, on=["yyyymm", "d_admdong_cd"], how="left")
    dest = dest.merge(
        snapshot_meta[["yyyymm", "snapshot_date_str", "snapshot_weekday", "is_weekend_snapshot"]],
        on="yyyymm",
        how="left",
    )
    dest["origin_diversity"] = dest["origin_diversity"].fillna(0).astype("int64")
    dest["active_days"] = dest["active_days"].fillna(0).astype("int64")
    dest["date_count"] = dest["yyyymm"].map(month_file_counts).fillna(1).astype("int64")
    dest["avg_daily_2030"] = dest["cnt_2030"] / dest["date_count"]
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
        zscore_by_group(dest, "yyyymm", np.log1p(dest["cnt_2030"]))
        + zscore_by_group(dest, "yyyymm", dest["share_2030"])
        + zscore_by_group(dest, "yyyymm", np.log1p(dest["origin_diversity"]))
        + zscore_by_group(dest, "yyyymm", dest["evening_2030_ratio"])
    )
    return dest.sort_values(["yyyymm", "mobility_score", "cnt_2030"], ascending=[True, False, False])


def summarize_living_migration_monthly_all_available(
    chunksize: int = 500_000,
) -> pd.DataFrame:
    """
    Summarize monthly demand with every daily ZIP currently present in RAW_DIR.

    Months with only one archived file remain partial-month snapshots. Months
    with many daily files, such as the March 2026 archive, become closer to a
    month-level daily aggregate. The coverage columns make that distinction
    explicit in downstream reports.
    """
    paths = get_all_living_migration_paths()
    summary = summarize_living_migration_monthly(input_paths=paths, chunksize=chunksize)
    coverage = (
        summary[["yyyymm", "date_count"]]
        .drop_duplicates()
        .assign(
            expected_days=lambda df: df["yyyymm"].map(
                lambda ym: calendar.monthrange(int(str(ym)[:4]), int(str(ym)[4:6]))[1]
            ),
            monthly_coverage_type=lambda df: np.where(
                df["date_count"] >= 20,
                "월 전체/대부분 일별 집계",
                "부분 일자/월말 스냅샷",
            ),
        )
    )
    coverage["coverage_ratio"] = coverage["date_count"] / coverage["expected_days"]
    coverage["missing_days_count"] = (coverage["expected_days"] - coverage["date_count"]).clip(lower=0)
    return summary.merge(coverage, on=["yyyymm", "date_count"], how="left")


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
    enriched = enriched[enriched["d_admdong_cd"].str.startswith("11")].copy()
    enriched["d_gu_cd"] = enriched["d_admdong_cd"].str[:5]
    enriched["d_gu_name"] = enriched["d_gu_cd"].map(SEOUL_GU_CODE_TO_NAME)

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
    enriched = enriched[enriched["d_admdong_name"].notna()].copy()

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
        "d_gu_name",
        "d_admdong_name",
        "candidate_type",
        "mobility_score",
        "cnt_2030",
        "avg_daily_2030",
        "date_count",
        "share_2030",
        "origin_diversity",
        "evening_2030_ratio",
        "morning_2030_ratio",
        "afternoon_2030_ratio",
        "late_night_2030_ratio",
        "weekday_2030_ratio",
        "friday_2030_ratio",
        "weekend_2030_ratio",
        "avg_move_time_2030",
        "avg_move_dist_2030",
        "total_cnt",
        "d_center_x",
        "d_center_y",
    ]
    actual_display_cols = [col for col in display_cols if col in enriched.columns]
    other_cols = [col for col in enriched.columns if col not in actual_display_cols]
    return enriched[actual_display_cols + other_cols]


def classify_visit_pattern(dest: pd.DataFrame) -> pd.Series:
    """
    요일·시간대 비율로 2030 방문 패턴을 분류.

    목적 방문형: 주말 비중 상위 40% + 저녁/심야 집중 → 약속·여가·소비 목적 방문
    생활 밀착형: 평일(월~목) 비중 상위 40% + 주말 신호 약함 → 주거 생활권 이동
    복합형: 목적 방문·생활 이동 신호 동시에 강함 → 상권성·거주성 공존
    불명확: 분류 근거 불충분
    """
    if "weekend_2030_ratio" not in dest.columns:
        return pd.Series("불명확", index=dest.index)

    weekend_th = dest["weekend_2030_ratio"].quantile(0.60)
    weekday_th = dest["weekday_2030_ratio"].quantile(0.60)
    evening_th = dest["evening_2030_ratio"].quantile(0.60)
    late_night_th = dest["late_night_2030_ratio"].quantile(0.60)

    is_weekend_heavy = dest["weekend_2030_ratio"] >= weekend_th
    is_weekday_heavy = dest["weekday_2030_ratio"] >= weekday_th
    is_evening_heavy = (
        (dest["evening_2030_ratio"] >= evening_th)
        | (dest["late_night_2030_ratio"] >= late_night_th)
    )

    return pd.Series(
        np.select(
            [
                is_weekend_heavy & is_weekday_heavy,    # 양쪽 모두 강함
                is_weekend_heavy & is_evening_heavy,   # 주말·저녁/심야 집중
                is_weekday_heavy & ~is_weekend_heavy,   # 평일 중심, 주말 약함
            ],
            ["복합형", "목적 방문형", "생활 밀착형"],
            default="불명확",
        ),
        index=dest.index,
    )


# ---------------------------------------------------------------------------
# 법정동 집계
# ---------------------------------------------------------------------------

def _infer_bjdong_name(admdong_name: str) -> str:
    """
    행정동명 끝의 번호 접미사를 제거해 법정동명을 근사 추정.
    예: '잠실6동' → '잠실동', '성수2가3동' → '성수2가동'
    공식 매핑 파일(BJDONG_MAPPING_CSV)이 있으면 load_bjdong_mapping()을 사용할 것.
    """
    return re.sub(r"(\d+)동$", "동", admdong_name)


def load_bjdong_mapping(
    mapping_path: Path = BJDONG_MAPPING_CSV,
) -> pd.DataFrame | None:
    """
    행정동코드 → 법정동코드/법정동명 매핑 CSV 로드.

    CSV 컬럼 형식: admdong_cd, bjdong_cd, bjdong_nm
    파일이 없으면 기본 실행에서는 실패. SEOUL_ALLOW_PARTIAL=1이면 이름 패턴 근사치 사용.

    다운로드: bash data_archive/scripts/download_bjdong_mapping.sh
    출처: 행정안전부 행정동-법정동 코드 대응표
    """
    if not mapping_path.exists():
        if allow_partial_run():
            print(f"   법정동 매핑 없음 ({mapping_path.name}) — SEOUL_ALLOW_PARTIAL=1 이므로 이름 패턴 근사치 사용")
            return None
        raise FileNotFoundError(
            f"법정동 매핑 파일 없음: {mapping_path}\n"
            "   준비 방법: bash data_archive/scripts/download_bjdong_mapping.sh"
        )
    df = pd.read_csv(mapping_path, dtype={"admdong_cd": "string", "bjdong_cd": "string"})
    required = {"admdong_cd", "bjdong_cd", "bjdong_nm"}
    if not required.issubset(df.columns):
        if allow_partial_run():
            print(f"   법정동 매핑 컬럼 부족 — SEOUL_ALLOW_PARTIAL=1 이므로 이름 패턴 근사치 사용")
            return None
        raise ValueError(f"법정동 매핑 컬럼 부족: 필요 컬럼 {sorted(required)}")
    return df


def aggregate_to_bjdong(
    dest: pd.DataFrame,
    bjdong_map: pd.DataFrame | None,
) -> pd.DataFrame:
    """
    행정동 단위 분석 결과를 법정동(洞) 단위로 집계.

    스코어/비율: 평균, cnt 계열: 합계로 처리.
    candidate_type / visit_pattern_type: 최빈값으로 대표.
    """
    df = dest.copy()
    df["d_admdong_cd"] = df["d_admdong_cd"].astype(str)

    if bjdong_map is not None:
        df = df.merge(
            bjdong_map.rename(columns={"admdong_cd": "d_admdong_cd"}),
            on="d_admdong_cd",
            how="left",
        )
        df["bjdong_cd"] = df["bjdong_cd"].fillna(df["d_admdong_cd"])
        df["bjdong_nm"] = df["bjdong_nm"].fillna(df["d_admdong_name"].apply(_infer_bjdong_name))
    else:
        df["bjdong_nm"] = df["d_admdong_name"].apply(_infer_bjdong_name)
        df["bjdong_cd"] = df["d_admdong_cd"]

    sum_cols = [c for c in df.columns if c.endswith("_cnt") or c == "total_cnt"]
    score_cols = [c for c in df.columns if c.endswith("_score") or c.endswith("_ratio")]
    group_cols = ["bjdong_cd"] if bjdong_map is not None else ["d_gu_name", "bjdong_nm"]
    key_cols = ["d_gu_name", "bjdong_cd", "bjdong_nm"]

    agg_dict: dict = {c: "sum" for c in sum_cols if c in df.columns}
    agg_dict.update({c: "mean" for c in score_cols if c in df.columns})
    agg_dict.update({c: "first" for c in key_cols if c in df.columns and c not in group_cols})
    for cat_col in ["candidate_type", "visit_pattern_type", "residential_filter"]:
        if cat_col in df.columns:
            agg_dict[cat_col] = lambda s: s.value_counts().index[0] if len(s) > 0 else "불명확"

    result = df.groupby(group_cols, as_index=False, dropna=False).agg(agg_dict)
    sort_col = "commercial_potential_score" if "commercial_potential_score" in result.columns else "adjusted_mobility_score"
    if sort_col in result.columns:
        result = result.sort_values(sort_col, ascending=False)
    return result


# ---------------------------------------------------------------------------
# GIS 용도지역 분석 (필수 레이어, geopandas 필요)
# ---------------------------------------------------------------------------

def summarize_land_use_by_dong(
    land_use_path: Path = LAND_USE_ZIP,
    admin_dong_path: Path = ADMIN_DONG_BOUNDARY_ZIP,
) -> pd.DataFrame:
    """
    행정동별 용도지역(상업·주거·준주거·공업·녹지) 면적 비율 계산.

    필요 파일
    ----------
    LAND_USE_ZIP: 서울시 도시계획 용도지역지구도 shapefile ZIP
        서울시 도시공간정보서비스 또는 국토교통부 VWORLD
    ADMIN_DONG_BOUNDARY_ZIP: 서울시 행정동 경계 shapefile ZIP
        국가공간정보포털(ngii.go.kr) 또는 SGIS(sgis.kostat.go.kr)

    다운로드: bash data_archive/scripts/download_gis_data.sh

    반환 컬럼
    ----------
    d_admdong_cd, commercial_zone_ratio, residential_zone_ratio,
    semi_residential_zone_ratio, industrial_zone_ratio, green_zone_ratio
    """
    if not require_input(land_use_path, "용도지역", "bash data_archive/scripts/download_gis_data.sh"):
        return pd.DataFrame()
    if not require_input(admin_dong_path, "행정동 경계", "bash data_archive/scripts/download_gis_data.sh"):
        return pd.DataFrame()
    try:
        import geopandas as gpd
    except ImportError:
        if allow_partial_run():
            print("   geopandas 미설치 — SEOUL_ALLOW_PARTIAL=1 이므로 GIS 분석 건너뜀 (pip install geopandas)")
            return pd.DataFrame()
        raise ImportError("geopandas 미설치: pip install geopandas shapely")

    print("   행정동 경계 로드...")
    dongs = gpd.read_file(f"zip://{admin_dong_path}")
    print("   용도지역 로드...")
    land_use = gpd.read_file(f"zip://{land_use_path}")
    land_use = land_use.to_crs(dongs.crs)

    cd_col = next(
        (c for c in dongs.columns if any(k in c.lower() for k in ["adm", "emd", "dong_cd", "hjdong"])),
        None,
    )
    zone_col = next(
        (c for c in land_use.columns if any(k in c for k in ["용도", "UNAME", "zone"])),
        None,
    )
    if cd_col is None or zone_col is None:
        if allow_partial_run():
            print(f"   컬럼 탐지 실패 (dong={cd_col}, zone={zone_col}) — SEOUL_ALLOW_PARTIAL=1 이므로 GIS 분석 건너뜀")
            return pd.DataFrame()
        raise ValueError(f"GIS 컬럼 탐지 실패 (dong={cd_col}, zone={zone_col})")

    print("   공간 교차 분석 중 (시간 소요)...")
    inter = gpd.overlay(
        dongs[[cd_col, "geometry"]].rename(columns={cd_col: "admdong_cd"}),
        land_use[[zone_col, "geometry"]].rename(columns={zone_col: "zone_type"}),
        how="intersection",
        keep_geom_type=True,
    )
    inter["area_m2"] = inter.geometry.area

    def _classify_zone(name: str) -> str:
        if not isinstance(name, str):
            return "기타"
        if "상업" in name:
            return "commercial"
        if "준주거" in name:
            return "semi_residential"
        if "주거" in name:
            return "residential"
        if "공업" in name or "준공업" in name:
            return "industrial"
        if "녹지" in name:
            return "green"
        return "기타"

    inter["zone_class"] = inter["zone_type"].apply(_classify_zone)
    dong_total = inter.groupby("admdong_cd")["area_m2"].sum()
    pivot = (
        inter.groupby(["admdong_cd", "zone_class"])["area_m2"]
        .sum()
        .unstack(fill_value=0.0)
    )
    for cls in ["commercial", "residential", "semi_residential", "industrial", "green"]:
        if cls not in pivot.columns:
            pivot[cls] = 0.0
    pivot = pivot.div(dong_total, axis=0).fillna(0.0)
    result = pivot[["commercial", "residential", "semi_residential", "industrial", "green"]].rename(
        columns={
            "commercial": "commercial_zone_ratio",
            "residential": "residential_zone_ratio",
            "semi_residential": "semi_residential_zone_ratio",
            "industrial": "industrial_zone_ratio",
            "green": "green_zone_ratio",
        }
    ).reset_index().rename(columns={"admdong_cd": "d_admdong_cd"})
    result["d_admdong_cd"] = result["d_admdong_cd"].astype(str)
    print(f"   용도지역 분석 완료: {len(result)}개 행정동")
    return result


# ---------------------------------------------------------------------------
# 매출 데이터 (서울시 우리마을가게 상권분석서비스)
# ---------------------------------------------------------------------------

def summarize_sales_by_dong(
    input_path: Path = COMMERCIAL_SALES_CSV,
) -> pd.DataFrame:
    """
    서울시 우리마을가게 상권분석서비스 행정동별 추정매출 집계.

    필요 파일: COMMERCIAL_SALES_CSV
    다운로드: bash data_archive/scripts/download_commercial_sales.sh
    출처: 서울 열린데이터광장 OA-15568
          https://data.seoul.go.kr/dataList/OA-15568/S/1/datasetView.do

    반환 컬럼: d_admdong_cd, total_sales, total_stores, sales_per_store,
              food_sales_ratio (음식/주점/카페 매출 비중)
    """
    if not require_input(input_path, "매출 데이터", "bash data_archive/scripts/download_commercial_sales.sh"):
        return pd.DataFrame()

    df = pd.read_csv(input_path, encoding="utf-8-sig", low_memory=False)
    col_map = {
        "행정동_코드": "admdong_cd",
        "행정동_코드_명": "admdong_name",
        "서비스_업종_코드_명": "industry_name",
        "당월_매출_금액": "monthly_sales",
        "당월_매출_건수": "monthly_txn",
        "점포수": "store_count",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    for col in ["monthly_sales", "monthly_txn", "store_count"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    summary = df.groupby("admdong_cd", as_index=False).agg(
        total_sales=("monthly_sales", "sum"),
        total_stores=("store_count", "sum"),
        total_txn=("monthly_txn", "sum"),
    )
    if "industry_name" in df.columns:
        food_kw = ["음식", "식음료", "주점", "카페", "음료"]
        food_mask = df["industry_name"].str.contains("|".join(food_kw), na=False)
        food_sales = df[food_mask].groupby("admdong_cd")["monthly_sales"].sum().reset_index()
        food_sales.columns = ["admdong_cd", "food_sales"]
        summary = summary.merge(food_sales, on="admdong_cd", how="left")
        summary["food_sales"] = summary["food_sales"].fillna(0.0)
        summary["food_sales_ratio"] = np.where(
            summary["total_sales"] > 0, summary["food_sales"] / summary["total_sales"], 0.0
        )
    else:
        summary["food_sales_ratio"] = 0.0

    summary["sales_per_store"] = np.where(
        summary["total_stores"] > 0, summary["total_sales"] / summary["total_stores"], 0.0
    )
    summary = summary.rename(columns={"admdong_cd": "d_admdong_cd"})
    summary["d_admdong_cd"] = summary["d_admdong_cd"].astype(str)
    print(f"   매출 집계 완료: {len(summary)}개 행정동")
    return summary


# ---------------------------------------------------------------------------
# 유동인구 vs 상주인구 (서울 생활인구 OA-14939)
# ---------------------------------------------------------------------------

def summarize_population_ratio(
    input_path: Path = LIVING_POPULATION_CSV,
) -> pd.DataFrame:
    """
    서울 생활인구에서 낮(9-18시) / 심야(22-6시) 2030 생활인구를 집계해
    유동인구 유입 비율(daytime_influx_ratio) 계산.

    필요 파일: LIVING_POPULATION_CSV
    다운로드: bash data_archive/scripts/download_living_population.sh
    출처: 서울 열린데이터광장 OA-14939
          https://data.seoul.go.kr/dataList/OA-14939/S/1/datasetView.do

    daytime_influx_ratio = 낮 2030 평균 / 심야 2030 평균
    > 1이면 낮에 외부에서 유입되는 인구가 거주자보다 많음 (유동인구 강세)
    """
    if not require_input(input_path, "생활인구 데이터", "bash data_archive/scripts/download_living_population.sh"):
        return pd.DataFrame()

    parts = []
    for chunk in pd.read_csv(input_path, encoding="utf-8-sig", chunksize=500_000, low_memory=False):
        col_map = {
            "행정동코드": "admdong_cd",
            "시간대구분": "time_slot",
            "20대생활인구수": "pop_20s",
            "30대생활인구수": "pop_30s",
        }
        chunk = chunk.rename(columns={k: v for k, v in col_map.items() if k in chunk.columns})
        for col in ["pop_20s", "pop_30s"]:
            if col in chunk.columns:
                chunk[col] = pd.to_numeric(chunk[col], errors="coerce").fillna(0.0)

        if "pop_20s" in chunk.columns and "pop_30s" in chunk.columns:
            chunk["pop_2030"] = chunk["pop_20s"] + chunk["pop_30s"]
        else:
            continue

        if "time_slot" in chunk.columns:
            ts = pd.to_numeric(chunk["time_slot"], errors="coerce")
            chunk["is_daytime"] = ts.between(9, 18)
            chunk["is_nighttime"] = (ts <= 6) | (ts >= 22)
        else:
            chunk["is_daytime"] = True
            chunk["is_nighttime"] = False

        parts.append(
            chunk.groupby("admdong_cd", as_index=False).agg(
                daytime_pop_2030=("pop_2030", lambda s: s[chunk.loc[s.index, "is_daytime"]].mean()),
                nighttime_pop_2030=("pop_2030", lambda s: s[chunk.loc[s.index, "is_nighttime"]].mean()),
            )
        )

    if not parts:
        return pd.DataFrame()

    result = pd.concat(parts, ignore_index=True)
    result = result.groupby("admdong_cd", as_index=False).mean(numeric_only=True)
    result["daytime_influx_ratio"] = np.where(
        result["nighttime_pop_2030"] > 0,
        result["daytime_pop_2030"] / result["nighttime_pop_2030"],
        1.0,
    )
    result = result.rename(columns={"admdong_cd": "d_admdong_cd"})
    result["d_admdong_cd"] = result["d_admdong_cd"].astype(str)
    print(f"   생활인구 집계 완료: {len(result)}개 행정동")
    return result


# ---------------------------------------------------------------------------
# 통합 상권 잠재력 점수
# ---------------------------------------------------------------------------

def add_commercial_potential_score(
    dest: pd.DataFrame,
    land_use: pd.DataFrame | None = None,
    sales: pd.DataFrame | None = None,
    pop_ratio: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    adjusted_mobility_score에 용도지역·매출·유동인구·방문패턴을 결합해
    commercial_potential_score(상권 잠재력 점수)를 계산.

    데이터가 없는 요소는 z-score = 0으로 처리(영향 없음).

    점수 구성
    ---------
    + adjusted_mobility_score          (이동·거주성 보정)
    + 0.5 * z(commercial_zone_ratio)   (상업지역 비율: 실제 상권 입지)
    + 0.7 * z(log1p(total_sales))      (매출 발생: 단순 통행이 아닌 소비 확인)
    + 0.4 * z(daytime_influx_ratio)    (유동인구 유입: 상주 대비 방문자 강세)
    + visit_bonus (목적방문형+0.5, 복합형+0.2) (요일 패턴 보정)
    - 0.3 * z(residential_zone_ratio)  (순 주거지역 비율: 상권 적합성 감점)
    """
    df = dest.copy()

    # 용도지역 결합
    if land_use is not None and not land_use.empty:
        lu = land_use.copy()
        if "d_admdong_cd" not in lu.columns and "admdong_cd" in lu.columns:
            lu = lu.rename(columns={"admdong_cd": "d_admdong_cd"})
        df = df.merge(lu, on="d_admdong_cd", how="left")
    for col in ["commercial_zone_ratio", "residential_zone_ratio"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # 매출 결합
    if sales is not None and not sales.empty:
        sl = sales.copy()
        if "d_admdong_cd" not in sl.columns and "admdong_cd" in sl.columns:
            sl = sl.rename(columns={"admdong_cd": "d_admdong_cd"})
        df = df.merge(sl, on="d_admdong_cd", how="left")
    for col in ["total_sales", "sales_per_store", "food_sales_ratio"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # 유동인구 결합
    if pop_ratio is not None and not pop_ratio.empty:
        pr = pop_ratio.copy()
        if "d_admdong_cd" not in pr.columns and "admdong_cd" in pr.columns:
            pr = pr.rename(columns={"admdong_cd": "d_admdong_cd"})
        df = df.merge(pr, on="d_admdong_cd", how="left")
    if "daytime_influx_ratio" not in df.columns:
        df["daytime_influx_ratio"] = 1.0
    df["daytime_influx_ratio"] = pd.to_numeric(df["daytime_influx_ratio"], errors="coerce").fillna(1.0)

    # 방문 패턴 가산점
    visit_bonus = pd.Series(0.0, index=df.index)
    if "visit_pattern_type" in df.columns:
        visit_bonus = df["visit_pattern_type"].map(
            {"목적 방문형": 0.5, "복합형": 0.2, "생활 밀착형": 0.0, "불명확": 0.0}
        ).fillna(0.0)

    def _safe_zscore(series: pd.Series) -> pd.Series:
        std = series.std(ddof=0)
        if std == 0 or pd.isna(std):
            return pd.Series(0.0, index=series.index)
        return (series - series.mean()) / std

    z_commercial = _safe_zscore(df["commercial_zone_ratio"])
    z_sales = _safe_zscore(np.log1p(df["total_sales"]))
    z_influx = _safe_zscore(df["daytime_influx_ratio"])
    z_res_zone = _safe_zscore(df["residential_zone_ratio"])

    df["commercial_potential_score"] = (
        df["adjusted_mobility_score"]
        + 0.5 * z_commercial
        + 0.7 * z_sales
        + 0.4 * z_influx
        + visit_bonus
        - 0.3 * z_res_zone
    )
    return df.sort_values("commercial_potential_score", ascending=False)


def enrich_monthly_destination_summary(dest: pd.DataFrame, admin_mapping: pd.DataFrame) -> pd.DataFrame:
    enriched_parts = []
    for _, month_df in dest.groupby("yyyymm", sort=True):
        enriched_parts.append(enrich_destination_summary(month_df, admin_mapping))
    return pd.concat(enriched_parts, ignore_index=True)


def add_residential_adjustment(dest: pd.DataFrame, residential: pd.DataFrame) -> pd.DataFrame:
    enriched = dest.merge(
        residential,
        left_on=["d_gu_name", "d_admdong_name"],
        right_on=["gu_name", "admdong_name"],
        how="left",
        suffixes=("", "_res"),
    )

    enriched["residential_match_note"] = np.where(
        enriched["admdong_name"].isna(),
        "미매칭",
        "매칭",
    )

    fill_zero_cols = [
        "young_population",
        "young_single_households",
        "young_low_weekend_outing_group",
        "young_very_low_outing_group",
        "young_single_ratio",
        "young_homebound_ratio",
        "residential_dominance_score",
    ]
    for col in fill_zero_cols:
        if col in enriched.columns:
            enriched[col] = pd.to_numeric(enriched[col], errors="coerce").fillna(0.0)

    enriched["residential_penalty"] = enriched["residential_dominance_score"].clip(lower=0.0)
    enriched["adjusted_mobility_score"] = enriched["mobility_score"] - 0.7 * enriched["residential_penalty"]
    residential_threshold = enriched["residential_dominance_score"].quantile(0.75)
    single_ratio_threshold = enriched["young_single_ratio"].quantile(0.75)
    mobility_median = enriched["adjusted_mobility_score"].quantile(0.5)

    is_high_residential = (
        (enriched["residential_dominance_score"] >= residential_threshold)
        | (enriched["young_single_ratio"] >= single_ratio_threshold)
    )
    is_high_mobility_after_penalty = enriched["adjusted_mobility_score"] >= mobility_median

    # 3단계 분류:
    #   방문성 검토   - 거주성 신호가 약함 → 방문 상권 후보
    #   혼재형        - 거주성·방문성이 동시에 강함 → 별도 해석 필요 (서교동, 신촌동, 역삼1동 등)
    #   자취/거주성   - 거주성이 강하고 방문 신호가 상대적으로 약함 → 거주지 효과로 분리
    enriched["residential_filter"] = np.select(
        [
            ~is_high_residential,
            is_high_residential & is_high_mobility_after_penalty,
        ],
        ["방문성 검토", "혼재형 (상권+거주)"],
        default="2030 자취/거주성 높음",
    )

    front_cols = [
        "d_admdong_cd",
        "d_gu_name",
        "d_admdong_name",
        "residential_filter",
        "candidate_type",
        "adjusted_mobility_score",
        "mobility_score",
        "residential_dominance_score",
        "cnt_2030",
        "avg_daily_2030",
        "date_count",
        "share_2030",
        "young_single_households",
        "young_single_ratio",
        "young_homebound_ratio",
        "origin_diversity",
        "evening_2030_ratio",
        "avg_move_time_2030",
    ]
    other_cols = [col for col in enriched.columns if col not in front_cols]
    return enriched[front_cols + other_cols].sort_values(
        ["adjusted_mobility_score", "mobility_score"], ascending=False
    )


def build_monthly_candidate_trends(monthly: pd.DataFrame) -> pd.DataFrame:
    """Create cross-month visitor-candidate trend metrics by administrative dong."""
    latest_month = monthly["yyyymm"].max()
    latest_period = pd.Period(latest_month, freq="M")
    compare_month = (latest_period - 6).strftime("%Y%m")

    ranked = monthly.copy()
    ranked["monthly_rank_all"] = ranked.groupby("yyyymm")["adjusted_mobility_score"].rank(
        ascending=False,
        method="min",
    )
    ranked["monthly_rank_visitor"] = np.nan
    visitor_mask = ranked["residential_filter"].isin(["방문성 검토", "혼재형 (상권+거주)"])
    ranked.loc[visitor_mask, "monthly_rank_visitor"] = ranked.loc[visitor_mask].groupby("yyyymm")[
        "adjusted_mobility_score"
    ].rank(ascending=False, method="min")

    def slope(values: pd.Series) -> float:
        if len(values) < 3:
            return 0.0
        x = np.arange(len(values))
        return float(np.polyfit(x, values.to_numpy(dtype=float), 1)[0])

    trend = (
        ranked.groupby(["d_admdong_cd", "d_gu_name", "d_admdong_name"], as_index=False)
        .agg(
            observed_months=("yyyymm", "nunique"),
            first_month=("yyyymm", "min"),
            latest_month=("yyyymm", "max"),
            avg_adjusted_mobility_score=("adjusted_mobility_score", "mean"),
            latest_adjusted_mobility_score=(
                "adjusted_mobility_score",
                lambda s: ranked.loc[s.index].sort_values("yyyymm").iloc[-1]["adjusted_mobility_score"],
            ),
            score_slope=("adjusted_mobility_score", slope),
            avg_monthly_2030=("cnt_2030", "mean"),
            latest_monthly_2030=(
                "cnt_2030",
                lambda s: ranked.loc[s.index].sort_values("yyyymm").iloc[-1]["cnt_2030"],
            ),
            avg_share_2030=("share_2030", "mean"),
            latest_share_2030=(
                "share_2030",
                lambda s: ranked.loc[s.index].sort_values("yyyymm").iloc[-1]["share_2030"],
            ),
            avg_evening_2030_ratio=("evening_2030_ratio", "mean"),
            latest_evening_2030_ratio=(
                "evening_2030_ratio",
                lambda s: ranked.loc[s.index].sort_values("yyyymm").iloc[-1]["evening_2030_ratio"],
            ),
            visitor_months=("residential_filter", lambda s: (s == "방문성 검토").sum()),
            top20_visitor_months=("monthly_rank_visitor", lambda s: (s <= 20).sum()),
            latest_visitor_rank=(
                "monthly_rank_visitor",
                lambda s: ranked.loc[s.index].sort_values("yyyymm").iloc[-1]["monthly_rank_visitor"],
            ),
            residential_dominance_score=("residential_dominance_score", "first"),
            young_single_ratio=("young_single_ratio", "first"),
            residential_filter=("residential_filter", "first"),
        )
    )

    compare = ranked[ranked["yyyymm"].isin([compare_month, latest_month])].pivot_table(
        index="d_admdong_cd",
        columns="yyyymm",
        values="adjusted_mobility_score",
        aggfunc="first",
    )
    if latest_month in compare.columns and compare_month in compare.columns:
        trend["score_change_6m"] = trend["d_admdong_cd"].map(compare[latest_month] - compare[compare_month])
    else:
        trend["score_change_6m"] = np.nan

    trend["trend_type"] = np.select(
        [
            (trend["score_slope"] > 0.03) & (trend["score_change_6m"].fillna(0) > 0),
            (trend["score_slope"] < -0.03) & (trend["score_change_6m"].fillna(0) < 0),
        ],
        ["상승", "하락"],
        default="유지/변동",
    )
    trend["trend_candidate_score"] = (
        zscore(trend["latest_adjusted_mobility_score"])
        + zscore(trend["avg_adjusted_mobility_score"])
        + zscore(trend["score_slope"])
        + zscore(trend["top20_visitor_months"])
        + zscore(trend["score_change_6m"].fillna(0))
    )
    return trend.sort_values(
        ["trend_candidate_score", "latest_adjusted_mobility_score"],
        ascending=False,
    )


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


def _read_coordinate_csv(input_path: Path) -> pd.DataFrame:
    """Read a point CSV and normalize common coordinate/name/id columns."""
    df = pd.read_csv(input_path, encoding="utf-8-sig", low_memory=False)
    rename_map = {}
    for col in df.columns:
        lower = str(col).lower()
        if col in ["역명", "역사명", "정류장명", "station_nm", "station_name"]:
            rename_map[col] = "station_name"
        elif col in ["표준버스정류장ID", "station_id", "NODE_ID", "node_id"]:
            rename_map[col] = "station_id"
        elif col in ["버스정류장ARS번호", "ars_id", "ARS_ID", "ars_no"]:
            rename_map[col] = "ars_id"
        elif col in ["경도", "lon", "lng", "longitude", "x좌표", "x_coord"] or lower in ["x", "lon", "lng"]:
            rename_map[col] = "x"
        elif col in ["위도", "lat", "latitude", "y좌표", "y_coord"] or lower in ["y", "lat"]:
            rename_map[col] = "y"
    df = df.rename(columns=rename_map)
    if "x" not in df.columns or "y" not in df.columns:
        raise ValueError(f"Coordinate columns not found in {input_path.name}")
    df["x"] = pd.to_numeric(df["x"], errors="coerce")
    df["y"] = pd.to_numeric(df["y"], errors="coerce")
    return df.dropna(subset=["x", "y"]).copy()


def _points_from_coordinate_df(df: pd.DataFrame):
    """Build a GeoDataFrame from normalized x/y columns."""
    import geopandas as gpd

    crs = "EPSG:4326" if df["x"].abs().max() <= 180 and df["y"].abs().max() <= 90 else "EPSG:5186"
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["x"], df["y"]), crs=crs)


def summarize_transport_access_by_dong(
    subway_station: pd.DataFrame,
    bus_stop: pd.DataFrame,
    admin_dong_path: Path = ADMIN_DONG_BOUNDARY_ZIP,
    subway_coord_path: Path = SUBWAY_STATION_COORD_CSV,
    bus_coord_path: Path = BUS_STOP_COORD_CSV,
) -> pd.DataFrame:
    """
    Spatially join required station/stop coordinate files to admin-dong boundaries.

    Expected files:
      - subway_station_coordinates.csv: station_name, longitude/latitude or x/y
      - bus_stop_coordinates.csv: station_id or ars_id or station_name, longitude/latitude or x/y
    """
    if not require_input(admin_dong_path, "행정동 경계", "bash data_archive/scripts/download_gis_data.sh"):
        return pd.DataFrame()
    if not require_input(subway_coord_path, "지하철역 좌표", "raw/subway_station_coordinates.csv 준비"):
        return pd.DataFrame()
    if not require_input(bus_coord_path, "버스정류장 좌표", "raw/bus_stop_coordinates.csv 준비"):
        return pd.DataFrame()
    try:
        import geopandas as gpd
    except ImportError:
        if allow_partial_run():
            print("   geopandas 미설치 — SEOUL_ALLOW_PARTIAL=1 이므로 교통 접근성 공간 결합 건너뜀")
            return pd.DataFrame()
        raise ImportError("geopandas 미설치: pip install geopandas shapely")

    dongs = gpd.read_file(f"zip://{admin_dong_path}")
    cd_col = next(
        (c for c in dongs.columns if any(k in c.lower() for k in ["adm", "emd", "dong_cd", "hjdong"])),
        None,
    )
    if cd_col is None:
        if allow_partial_run():
            print("   행정동 코드 컬럼 탐지 실패 — SEOUL_ALLOW_PARTIAL=1 이므로 교통 접근성 공간 결합 건너뜀")
            return pd.DataFrame()
        raise ValueError("행정동 경계 파일에서 행정동 코드 컬럼을 찾지 못했습니다.")
    dongs = dongs[[cd_col, "geometry"]].rename(columns={cd_col: "d_admdong_cd"})

    parts = []
    if subway_coord_path.exists():
        coords = _read_coordinate_csv(subway_coord_path)
        if "station_name" in coords.columns:
            pts = _points_from_coordinate_df(coords).to_crs(dongs.crs)
            joined = gpd.sjoin(pts, dongs, how="inner", predicate="within")
            subway_joined = joined.merge(subway_station, on="station_name", how="left")
            subway_summary = subway_joined.groupby("d_admdong_cd", as_index=False).agg(
                subway_station_count=("station_name", "nunique"),
                subway_total_count=("subway_total_count", "sum"),
            )
            parts.append(subway_summary)

    if bus_coord_path.exists():
        coords = _read_coordinate_csv(bus_coord_path)
        pts = _points_from_coordinate_df(coords).to_crs(dongs.crs)
        joined = gpd.sjoin(pts, dongs, how="inner", predicate="within")
        merge_key = next((c for c in ["station_id", "ars_id", "station_name"] if c in joined.columns and c in bus_stop.columns), None)
        if merge_key is not None:
            bus_joined = joined.merge(bus_stop, on=merge_key, how="left")
        else:
            bus_joined = joined.copy()
            bus_joined["bus_total_count"] = 0.0
            bus_joined["route_count"] = 0.0
        bus_summary = bus_joined.groupby("d_admdong_cd", as_index=False).agg(
            bus_stop_count=("geometry", "size"),
            bus_total_count=("bus_total_count", "sum"),
            bus_route_count=("route_count", "sum"),
        )
        parts.append(bus_summary)

    if not parts:
        return pd.DataFrame()
    result = parts[0]
    for part in parts[1:]:
        result = result.merge(part, on="d_admdong_cd", how="outer")
    for col in ["subway_station_count", "subway_total_count", "bus_stop_count", "bus_total_count", "bus_route_count"]:
        if col not in result.columns:
            result[col] = 0.0
        result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0.0)
    result["transport_access_score"] = (
        zscore(np.log1p(result["subway_total_count"]))
        + zscore(np.log1p(result["bus_total_count"]))
        + zscore(np.log1p(result["subway_station_count"] + result["bus_stop_count"]))
    )
    result["d_admdong_cd"] = result["d_admdong_cd"].astype(str)
    print(f"   교통 접근성 공간 결합 완료: {len(result)}개 행정동")
    return result


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


def build_candidate_explanations(dest: pd.DataFrame, top_n: int = 30, bottom_n: int = 5) -> pd.DataFrame:
    """Create short rule-based explanations for top and bottom candidate dongs."""
    source = dest[
        dest["residential_filter"].isin(["방문성 검토", "혼재형 (상권+거주)"])
    ].copy()
    if "commercial_potential_score" not in source.columns:
        source["commercial_potential_score"] = source["adjusted_mobility_score"]
    source = source.sort_values(["commercial_potential_score", "adjusted_mobility_score"], ascending=False)
    thresholds = {
        col: dest[col].quantile(q) if col in dest.columns else None
        for col, q in [
            ("origin_diversity", 0.75),
            ("evening_2030_ratio", 0.75),
            ("weekend_2030_ratio", 0.60),
            ("share_2030", 0.75),
            ("young_single_ratio", 0.75),
        ]
    }
    rows = []
    slices = [
        ("상위", source.head(top_n)),
        ("하위", source.tail(bottom_n).sort_values(["commercial_potential_score", "adjusted_mobility_score"])),
    ]
    for group, group_df in slices:
        for rank, (_, row) in enumerate(group_df.iterrows(), start=1):
            name = f"{row['d_gu_name']} {row['d_admdong_name']}"
            signals = []
            cautions = []

            if thresholds["origin_diversity"] is not None and row.get("origin_diversity", 0) >= thresholds["origin_diversity"]:
                signals.append("출발지 다양성이 높아 광역 유입 신호가 강함")
            if thresholds["evening_2030_ratio"] is not None and row.get("evening_2030_ratio", 0) >= thresholds["evening_2030_ratio"]:
                signals.append("저녁 시간대 2030 도착 비중이 높음")
            if thresholds["weekend_2030_ratio"] is not None and row.get("weekend_2030_ratio", 0) >= thresholds["weekend_2030_ratio"]:
                signals.append("주말 방문 비중이 상대적으로 높음")
            if thresholds["share_2030"] is not None and row.get("share_2030", 0) >= thresholds["share_2030"]:
                signals.append("전체 이동 중 2030 비중이 높음")
            if row.get("residential_filter") == "혼재형 (상권+거주)":
                cautions.append("거주성 신호도 함께 강해 소비·점포 데이터로 추가 확인 필요")
            if thresholds["young_single_ratio"] is not None and row.get("young_single_ratio", 0) >= thresholds["young_single_ratio"]:
                cautions.append("2030 1인가구 비율이 높아 자취/생활권 효과가 섞일 수 있음")
            if not signals:
                if group == "하위":
                    signals.append("방문성 후보군 안에서는 보정 이동 점수가 낮아 우선순위가 낮음")
                else:
                    signals.append("보정 이동 점수 기준 상위권이나 세부 패턴은 추가 확인 필요")
            if not cautions:
                if group == "하위":
                    cautions.append("현재 기준에서는 적극 후보보다 비교·제외 후보로 보는 것이 적절함")
                else:
                    cautions.append("현재 이동 데이터 기준의 1차 후보이며 매출·용도지역 결합 시 재평가 필요")
            signal_text = " ".join(f"{signal}." for signal in signals)
            caution_text = " ".join(f"{caution}." for caution in cautions)

            rows.append(
                {
                    "rank_group": group,
                    "rank": rank,
                    "d_gu_name": row["d_gu_name"],
                    "d_admdong_name": row["d_admdong_name"],
                    "residential_filter": row["residential_filter"],
                    "candidate_type": row["candidate_type"],
                    "visit_pattern_type": row.get("visit_pattern_type", "불명확"),
                    "commercial_potential_score": row.get("commercial_potential_score", row["adjusted_mobility_score"]),
                    "adjusted_mobility_score": row["adjusted_mobility_score"],
                    "summary": f"{name}은 {row['candidate_type']} 후보입니다. {signal_text}",
                    "caution": caution_text,
                }
            )
    return pd.DataFrame(rows)


def write_candidate_explanation_report(explanations: pd.DataFrame) -> None:
    """Write an automatic narrative report for candidate dongs."""
    if explanations.empty:
        return
    sections = ["# 후보 지역별 자동 설명 리포트\n"]
    for group, title in [("상위", "상위 후보"), ("하위", "하위 후보")]:
        group_df = explanations[explanations["rank_group"] == group].copy()
        if group_df.empty:
            continue
        sections.append(f"\n# {title}\n")
        if group == "하위":
            group_df = group_df.head(5)
        for _, row in group_df.iterrows():
            sections.append(
                "\n"
                f"## {row['rank_group']} {int(row['rank'])}. {row['d_gu_name']} {row['d_admdong_name']}\n\n"
                f"- 분류: {row['residential_filter']} / {row['candidate_type']} / {row['visit_pattern_type']}\n"
                f"- 점수: commercial_potential_score {row['commercial_potential_score']:.3f}, "
                f"adjusted_mobility_score {row['adjusted_mobility_score']:.3f}\n"
                f"- 해석: {row['summary']}\n"
                f"- 주의: {row['caution']}\n"
            )
    (REPORTS_DIR / "candidate_explanation_report.md").write_text("\n".join(sections), encoding="utf-8")


def write_top20_report(dest: pd.DataFrame) -> None:
    cols = [
        "d_admdong_cd",
        "d_gu_name",
        "d_admdong_name",
        "residential_filter",
        "candidate_type",
        "adjusted_mobility_score",
        "mobility_score",
        "residential_dominance_score",
        "cnt_2030",
        "avg_daily_2030",
        "date_count",
        "share_2030",
        "young_single_households",
        "young_single_ratio",
        "origin_diversity",
        "evening_2030_ratio",
        "avg_move_time_2030",
    ]
    table = dataframe_to_markdown(dest.head(20)[cols])

    report = (
        "# 2030 도착 이동 상위 행정동 Top 20\n\n"
        "이 보고서는 수도권 생활이동 샘플을 기준으로 2030 도착 이동 신호가 강한 "
        "행정동을 순위화한 결과입니다.\n\n"
        "`mobility_score`는 기존 이동 기반 점수이고, `adjusted_mobility_score`는 "
        "2030 1인가구 거주 밀집도를 감점한 방문성 보정 점수입니다.\n\n"
        "보정 점수 = 이동 기반 점수 - 0.7 * 2030 자취/거주성 점수.\n\n"
        f"{table}\n"
    )
    (REPORTS_DIR / "living_migration_2030_top20.md").write_text(report, encoding="utf-8")


def write_split_candidate_reports(dest: pd.DataFrame) -> None:
    cols = [
        "d_gu_name",
        "d_admdong_name",
        "residential_filter",
        "candidate_type",
        "adjusted_mobility_score",
        "mobility_score",
        "residential_dominance_score",
        "cnt_2030",
        "share_2030",
        "young_single_households",
        "young_single_ratio",
        "origin_diversity",
        "evening_2030_ratio",
        "avg_move_time_2030",
    ]
    visitor = dest[dest["residential_filter"] == "방문성 검토"].head(20)
    mixed = (
        dest[dest["residential_filter"] == "혼재형 (상권+거주)"]
        .sort_values(["adjusted_mobility_score", "mobility_score"], ascending=False)
        .head(20)
    )
    residential = (
        dest[dest["residential_filter"] == "2030 자취/거주성 높음"]
        .sort_values(["residential_dominance_score", "mobility_score"], ascending=False)
        .head(20)
    )

    visitor_report = (
        "# 방문 상권 후보 Top 20\n\n"
        "2030 1인가구 거주 밀집 신호가 상대적으로 낮고, 이동 기반 점수가 높은 행정동입니다.\n\n"
        f"{dataframe_to_markdown(visitor[cols])}\n"
    )
    mixed_report = (
        "# 혼재형 (상권+거주 동시 강함) Top 20\n\n"
        "2030 이동 기반 방문 신호와 1인가구 거주 밀집 신호가 동시에 높게 나타나는 행정동입니다. "
        "서교동, 신촌동, 역삼1동처럼 상권성과 거주성이 공존하는 지역이 포함됩니다.\n\n"
        "`adjusted_mobility_score`는 거주성 감점 후에도 전체 중앙값 이상을 유지했으므로 "
        "방문 신호 자체가 강하다고 볼 수 있지만, 거주지 이동이 점수를 끌어올리는 부분도 공존합니다. "
        "소비 데이터·점포 밀도·요일별 패턴 등 추가 정보로 성격을 분리해야 합니다.\n\n"
        f"{dataframe_to_markdown(mixed[cols])}\n"
    )
    residential_report = (
        "# 2030 자취/거주성 분리 대상 Top 20\n\n"
        "2030 1인가구 밀집도가 높아 이동량이 상권 방문보다 생활권/거주 이동의 영향을 받을 수 있는 행정동입니다.\n\n"
        f"{dataframe_to_markdown(residential[cols])}\n"
    )
    (REPORTS_DIR / "visitor_candidate_top20.md").write_text(visitor_report, encoding="utf-8")
    (REPORTS_DIR / "mixed_commercial_residential_top20.md").write_text(mixed_report, encoding="utf-8")
    (REPORTS_DIR / "residential_dominant_2030_top20.md").write_text(residential_report, encoding="utf-8")


def write_monthly_reports(monthly: pd.DataFrame, trend: pd.DataFrame) -> None:
    latest_month = monthly["yyyymm"].max()
    latest = monthly[
        (monthly["yyyymm"] == latest_month)
        & monthly["residential_filter"].isin(["방문성 검토", "혼재형 (상권+거주)"])
    ].sort_values(["adjusted_mobility_score", "mobility_score"], ascending=False)

    latest_cols = [
        "yyyymm",
        "d_gu_name",
        "d_admdong_name",
        "candidate_type",
        "adjusted_mobility_score",
        "mobility_score",
        "cnt_2030",
        "share_2030",
        "origin_diversity",
        "evening_2030_ratio",
        "avg_move_time_2030",
    ]
    trend_cols = [
        "d_gu_name",
        "d_admdong_name",
        "trend_type",
        "trend_candidate_score",
        "latest_adjusted_mobility_score",
        "avg_adjusted_mobility_score",
        "score_slope",
        "score_change_6m",
        "top20_visitor_months",
        "latest_monthly_2030",
        "latest_share_2030",
        "latest_evening_2030_ratio",
    ]

    weekend_months = (
        sorted(monthly.loc[monthly["is_weekend_snapshot"].fillna(False), "yyyymm"].unique().tolist())
        if "is_weekend_snapshot" in monthly.columns
        else []
    )
    weekend_note = (
        "\n> **주말 스냅샷 포함 월:** "
        + ", ".join(weekend_months)
        + " — 해당 월은 주말 이동 패턴이 반영되어 야간·여가 지역이 평일 기준 대비 "
        "다르게 나타날 수 있습니다. 월간 비교 시 요일 차이를 고려하세요.\n"
        if weekend_months
        else ""
    )

    latest_report = (
        f"# 월별 방문 상권 후보 Top 20 - {latest_month}\n\n"
        "2023년 1월부터 2026년 3월까지 확보 가능한 월말 생활이동 스냅샷을 사용했습니다. "
        "아래 표는 최신 월 스냅샷에서 2030 자취/거주성 보정 후 방문성이 높게 남은 행정동입니다. "
        "혼재형 (상권+거주)도 방문 신호가 살아있으므로 함께 포함했습니다."
        f"{weekend_note}\n\n"
        "## 상위 20\n\n"
        f"{dataframe_to_markdown(latest.head(20)[latest_cols])}\n"
        "\n## 하위 5\n\n"
        "같은 방문성 후보군 안에서 보정 점수가 낮은 비교군입니다. 적극 후보라기보다 우선순위 조정과 "
        "제외 판단에 참고합니다.\n\n"
        f"{dataframe_to_markdown(latest.tail(5).sort_values('adjusted_mobility_score')[latest_cols])}\n"
    )
    trend_report = (
        "# 장기 월별 강세 후보 Top 20\n\n"
        "월별 스냅샷 전체에서 최신 점수, 평균 점수, 점수 기울기, 최근 6개월 변화, "
        "방문 후보 Top 20 반복 등장 횟수를 합쳐 장기 후보 점수를 계산했습니다. "
        "현재 데이터에서는 순수 상승 후보보다 여러 달 동안 반복적으로 강한 후보가 상위에 많이 나타납니다.\n\n"
        f"{dataframe_to_markdown(trend.head(20)[trend_cols])}\n"
    )

    (REPORTS_DIR / "monthly_visitor_candidate_latest_top20.md").write_text(
        latest_report,
        encoding="utf-8",
    )
    (REPORTS_DIR / "monthly_candidate_trend_top20.md").write_text(
        trend_report,
        encoding="utf-8",
    )


def write_interpretation_report(dest: pd.DataFrame, subway_station: pd.DataFrame, bus_stop: pd.DataFrame) -> None:
    type_counts = dest["candidate_type"].value_counts().reset_index()
    type_counts.columns = ["candidate_type", "dong_count"]
    residential_counts = dest["residential_filter"].value_counts().reset_index()
    residential_counts.columns = ["residential_filter", "dong_count"]

    report = (
        "# 2030 이동 기반 상권 후보 해석 보고서\n\n"
        "## 결과의 의미\n\n"
        "현재 결과는 상권 성장을 확정하는 분석이 아니라, 2030 도착 이동이 강하게 나타나는 "
        "행정동을 먼저 걸러내는 1차 후보 발굴 결과입니다. 이번 버전에서는 서울 시민생활 데이터의 "
        "2030 1인가구 지표를 결합해 자취/거주성 높은 지역을 별도로 표시하고 감점했습니다.\n\n"
        "## 2030 자취/거주성 분리 결과\n\n"
        f"{dataframe_to_markdown(residential_counts)}\n\n"
        "- `2030 자취/거주성 높음`: 2030 1인가구수, 1인가구 비율, 외출 적은 집단 비중이 높은 지역입니다.\n"
        "- `방문성 검토`: 자취 밀집 신호가 상대적으로 약해 방문 상권 후보로 추가 검토할 지역입니다.\n\n"
        "## 후보 유형 분포\n\n"
        f"{dataframe_to_markdown(type_counts)}\n\n"
        "## 유형 해석\n\n"
        "- 핵심 후보형: 2030 도착량, 2030 비중, 출발지 다양성, 저녁 이동 비중이 모두 높은 지역입니다.\n"
        "- 생활권형: 2030 이동은 많지만 이동 시간이 짧고 유입 출발지가 제한적인 지역입니다. 주거 생활권 이동일 수 있습니다.\n"
        "- 광역 목적지형: 여러 출발지에서 비교적 긴 시간을 들여 방문하는 지역입니다. 이미 목적지성이 강한 상권/대학가/업무지구일 가능성이 큽니다.\n"
        "- 야간 소비형: 저녁 시간대 2030 유입 비중이 높은 지역입니다. 식음료, 술집, 문화, 약속 수요와 관련될 수 있습니다.\n"
        "- 소규모 2030 집중형: 전체 규모는 작지만 2030 비중이 높은 지역입니다. 초기 신호 후보로 추적할 가치가 있습니다.\n"
        "- 관찰 필요: 월 단위 이동 지표만으로는 유형을 강하게 판단하기 어려운 지역입니다.\n\n"
        "## 2026년 4월 지하철 승하차 상위역\n\n"
        f"{dataframe_to_markdown(subway_station.head(15)[['station_name', 'subway_total_count', 'subway_weekend_share']])}\n\n"
        "## 2026년 4월 버스 승하차 상위 정류장\n\n"
        f"{dataframe_to_markdown(bus_stop.head(15)[['station_name', 'bus_total_count', 'route_count']])}\n\n"
        "## 혼재형 (상권+거주) 해석 지침\n\n"
        "`혼재형 (상권+거주)`은 거주성 감점(−0.7 × residential_dominance_score) 이후에도 "
        "`adjusted_mobility_score`가 전체 행정동 중앙값 이상을 유지한 경우입니다. "
        "즉, 방문 신호가 거주성 효과를 어느 정도 상회할 만큼 강하지만, "
        "거주지 이동이 점수를 일부 끌어올리는 구조가 공존합니다.\n\n"
        "이 카테고리는 순수 방문 상권도, 순수 자취 밀집지도 아닌 **해석 보류** 구간입니다. "
        "다음 추가 데이터로 성격을 분리해야 합니다:\n\n"
        "- 소비 데이터(카드 매출): 실제 소비가 발생하면 방문 상권으로 분류 가능\n"
        "- 점포 밀도: 외식·주점·문화 업종 비중이 높으면 상권성이 강한 혼재형\n"
        "- 요일별 이동 패턴: 주말에 유입이 크게 늘면 방문 목적성 확인\n"
        "- 이동 시작지 분포: 해당 행정동 내부 출발 비중이 높으면 거주성 효과가 크다는 신호\n\n"
        "## 현재 데이터 한계\n\n"
        "**1. 생활이동 월별 추세 — 월말 요일 편향**\n\n"
        "월별 추세 분석은 각 월의 월말 대표일 하루짜리 스냅샷을 사용합니다. "
        "해당 날짜가 금요일이면 야간·여가 이동이 과대 추정되고, "
        "화요일이면 과소 추정될 수 있습니다. "
        "`snapshot_weekday`, `is_weekend_snapshot` 컬럼이 이를 표시하므로 "
        "월간 비교 시 참고하세요. 전체 일별 월간 합계가 아니라는 점도 유의해야 합니다.\n\n"
        "**2. 지하철/버스 — 행정동 공간 결합**\n\n"
        "기본 지하철·버스 데이터에는 역명·정류장명만 있고 좌표가 없습니다. "
        "`seoul_admin_dong_boundary.zip`과 좌표 파일(`subway_station_coordinates.csv`, "
        "`bus_stop_coordinates.csv`)이 있으면 공간 조인으로 `transport_access_by_dong.csv`를 생성합니다. "
        "기본 실행에서는 이 파일들이 필수이며, 누락 시 분석을 중단합니다.\n\n"
        "**3. 소비/점포 데이터 미결합**\n\n"
        "현재 분석은 이동량 신호만 사용합니다. "
        "실제 상권성 확인을 위해서는 카드 매출 집계, 업종별 점포 수 등의 결합이 필요합니다. "
        "서울 열린데이터광장의 상권분석서비스 데이터를 행정동 코드 기준으로 조인하면 "
        "이동 신호와 실제 소비 간의 갭을 확인할 수 있습니다.\n\n"
        "**4. 거주성 보정 설계 의도**\n\n"
        "`adjusted_mobility_score = mobility_score - 0.7 × residential_dominance_score`는 "
        "거주성 높은 지역을 완전히 제거하지 않고 **감점·분리**하는 장치입니다. "
        "거주성이 높아도 방문 신호가 충분히 강하면 혼재형으로 남길 수 있어야 하기 때문입니다. "
        "0.7 계수는 조정 가능하며, 값을 높이면 거주성 지역이 더 강하게 억제됩니다.\n"
    )
    (REPORTS_DIR / "interpretation_report.md").write_text(report, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def run_all() -> None:
    ensure_output_dirs()
    validate_required_inputs()

    print("0. Reading administrative-dong mapping...")
    admin_mapping = read_admin_dong_mapping()
    admin_mapping_path = PROCESSED_DIR / "admin_dong_mapping.csv"
    admin_mapping.to_csv(admin_mapping_path, index=False, encoding="utf-8-sig")
    print(f"   saved: {admin_mapping_path} ({len(admin_mapping):,} rows)")

    print("0-1. Reading 2030 single-household residential data...")
    residential = summarize_young_single_households()
    residential_path = PROCESSED_DIR / "young_single_household_residential_summary.csv"
    residential.to_csv(residential_path, index=False, encoding="utf-8-sig")
    print(f"   saved: {residential_path} ({len(residential):,} rows)")

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
    dest = add_residential_adjustment(dest, residential)

    print("3-2. Classifying visit patterns (weekday/time breakdown)...")
    dest["visit_pattern_type"] = classify_visit_pattern(dest)
    visit_pattern_counts = dest["visit_pattern_type"].value_counts()
    print(f"   목적 방문형: {visit_pattern_counts.get('목적 방문형', 0)}, "
          f"생활 밀착형: {visit_pattern_counts.get('생활 밀착형', 0)}, "
          f"복합형: {visit_pattern_counts.get('복합형', 0)}, "
          f"불명확: {visit_pattern_counts.get('불명확', 0)}")

    print("3-3. Loading required enrichment data (GIS / sales / population)...")
    land_use_df = summarize_land_use_by_dong()
    sales_df = summarize_sales_by_dong()
    pop_ratio_df = summarize_population_ratio()

    print("3-4. Computing commercial_potential_score...")
    dest = add_commercial_potential_score(
        dest,
        land_use_df if not land_use_df.empty else None,
        sales_df if not sales_df.empty else None,
        pop_ratio_df if not pop_ratio_df.empty else None,
    )

    print("3-5. Aggregating to 법정동(洞) unit...")
    bjdong_map = load_bjdong_mapping()
    bjdong_summary = aggregate_to_bjdong(dest, bjdong_map)
    bjdong_path = PROCESSED_DIR / "bjdong_candidate_summary.csv"
    bjdong_summary.to_csv(bjdong_path, index=False, encoding="utf-8-sig")
    print(f"   saved: {bjdong_path} ({len(bjdong_summary):,} 법정동)")

    if not land_use_df.empty:
        lu_path = PROCESSED_DIR / "land_use_by_dong.csv"
        land_use_df.to_csv(lu_path, index=False, encoding="utf-8-sig")
        print(f"   saved: {lu_path} ({len(land_use_df):,} rows)")
    if not sales_df.empty:
        sl_path = PROCESSED_DIR / "sales_by_dong.csv"
        sales_df.to_csv(sl_path, index=False, encoding="utf-8-sig")
        print(f"   saved: {sl_path} ({len(sales_df):,} rows)")
    if not pop_ratio_df.empty:
        pr_path = PROCESSED_DIR / "population_ratio_by_dong.csv"
        pop_ratio_df.to_csv(pr_path, index=False, encoding="utf-8-sig")
        print(f"   saved: {pr_path} ({len(pop_ratio_df):,} rows)")

    dest_path = PROCESSED_DIR / "living_migration_2030_destination_summary.csv"
    hourly_path = PROCESSED_DIR / "living_migration_2030_destination_hourly.csv"
    dest.to_csv(dest_path, index=False, encoding="utf-8-sig")
    hourly.to_csv(hourly_path, index=False, encoding="utf-8-sig")
    visitor_path = PROCESSED_DIR / "visitor_candidate_summary.csv"
    mixed_path = PROCESSED_DIR / "mixed_commercial_residential_summary.csv"
    residential_dominant_path = PROCESSED_DIR / "residential_dominant_2030_summary.csv"
    dest[dest["residential_filter"] == "방문성 검토"].to_csv(
        visitor_path, index=False, encoding="utf-8-sig"
    )
    dest[dest["residential_filter"] == "혼재형 (상권+거주)"].sort_values(
        ["adjusted_mobility_score", "mobility_score"], ascending=False
    ).to_csv(mixed_path, index=False, encoding="utf-8-sig")
    dest[dest["residential_filter"] == "2030 자취/거주성 높음"].sort_values(
        ["residential_dominance_score", "mobility_score"], ascending=False
    ).to_csv(residential_dominant_path, index=False, encoding="utf-8-sig")

    explanations = build_candidate_explanations(dest)
    explanations_path = PROCESSED_DIR / "candidate_explanations.csv"
    explanations.to_csv(explanations_path, index=False, encoding="utf-8-sig")
    write_candidate_explanation_report(explanations)

    # 법정동 Top 20 보고서
    bjdong_report_cols = [
        c for c in [
            "bjdong_nm", "d_gu_name", "visit_pattern_type", "residential_filter", "candidate_type",
            "commercial_potential_score", "adjusted_mobility_score", "cnt_2030",
            "weekend_2030_ratio", "evening_2030_ratio", "late_night_2030_ratio",
            "food_sales_ratio", "daytime_influx_ratio", "commercial_zone_ratio",
        ]
        if c in bjdong_summary.columns
    ]
    bjdong_report = (
        "# 법정동(洞) 단위 상권 잠재력 Top 20\n\n"
        "행정동 단위 분석 결과를 법정동 단위로 집계하고, "
        "용도지역·매출·유동인구·방문패턴을 결합한 `commercial_potential_score` 기준 순위입니다. "
        "GIS·매출·생활인구 데이터를 모두 결합한 `commercial_potential_score` 기준 순위입니다.\n\n"
        f"{dataframe_to_markdown(bjdong_summary.head(20)[bjdong_report_cols])}\n"
    )
    (REPORTS_DIR / "bjdong_commercial_candidate_top20.md").write_text(bjdong_report, encoding="utf-8")

    write_top20_report(dest)
    write_split_candidate_reports(dest)

    print("3-1. Analyzing monthly 2030 living-migration snapshots...")
    monthly = summarize_living_migration_monthly()
    monthly = enrich_monthly_destination_summary(monthly, admin_mapping)
    monthly = add_residential_adjustment(monthly, residential)
    monthly["monthly_rank_all"] = monthly.groupby("yyyymm")["adjusted_mobility_score"].rank(
        ascending=False,
        method="min",
    )
    monthly["monthly_rank_visitor"] = np.nan
    monthly_visitor_mask = monthly["residential_filter"].isin(["방문성 검토", "혼재형 (상권+거주)"])
    monthly.loc[monthly_visitor_mask, "monthly_rank_visitor"] = monthly.loc[
        monthly_visitor_mask
    ].groupby("yyyymm")["adjusted_mobility_score"].rank(ascending=False, method="min")
    monthly_trend = build_monthly_candidate_trends(monthly)
    monthly_path = PROCESSED_DIR / "monthly_living_migration_2030_summary.csv"
    monthly_visitor_path = PROCESSED_DIR / "monthly_visitor_candidate_summary.csv"
    monthly_trend_path = PROCESSED_DIR / "monthly_candidate_trend_summary.csv"
    monthly.to_csv(monthly_path, index=False, encoding="utf-8-sig")
    monthly[monthly["residential_filter"].isin(["방문성 검토", "혼재형 (상권+거주)"])].to_csv(
        monthly_visitor_path,
        index=False,
        encoding="utf-8-sig",
    )
    monthly_trend.to_csv(monthly_trend_path, index=False, encoding="utf-8-sig")
    write_monthly_reports(monthly, monthly_trend)

    print("3-1b. Analyzing all available daily files by month...")
    monthly_all = summarize_living_migration_monthly_all_available()
    monthly_all = enrich_monthly_destination_summary(monthly_all, admin_mapping)
    monthly_all = add_residential_adjustment(monthly_all, residential)
    monthly_all_path = PROCESSED_DIR / "monthly_living_migration_all_available_summary.csv"
    monthly_all.to_csv(monthly_all_path, index=False, encoding="utf-8-sig")

    print("4. Creating transport support summaries and interpretation report...")
    subway_station, bus_stop, bus_hour = summarize_transport_patterns(subway, bus_summary, bus_hourly)
    subway_station_path = PROCESSED_DIR / "subway_station_summary.csv"
    bus_stop_path = PROCESSED_DIR / "bus_stop_summary.csv"
    bus_hour_path = PROCESSED_DIR / "bus_hourly_citywide_summary.csv"
    subway_station.to_csv(subway_station_path, index=False, encoding="utf-8-sig")
    bus_stop.to_csv(bus_stop_path, index=False, encoding="utf-8-sig")
    bus_hour.to_csv(bus_hour_path, index=False, encoding="utf-8-sig")
    transport_access = summarize_transport_access_by_dong(subway_station, bus_stop)
    if not transport_access.empty:
        transport_access_path = PROCESSED_DIR / "transport_access_by_dong.csv"
        transport_access.to_csv(transport_access_path, index=False, encoding="utf-8-sig")
        print(f"   saved: {transport_access_path} ({len(transport_access):,} rows)")
    write_interpretation_report(dest, subway_station, bus_stop)
    print(f"   saved: {subway_station_path} ({len(subway_station):,} rows)")
    print(f"   saved: {bus_stop_path} ({len(bus_stop):,} rows)")
    print(f"   saved: {bus_hour_path} ({len(bus_hour):,} rows)")
    print(f"   saved: {REPORTS_DIR / 'interpretation_report.md'}")
    print(f"   saved: {dest_path} ({len(dest):,} rows)")
    print(f"   saved: {visitor_path} ({(dest['residential_filter'] == '방문성 검토').sum():,} rows)")
    print(f"   saved: {mixed_path} ({(dest['residential_filter'] == '혼재형 (상권+거주)').sum():,} rows)")
    print(f"   saved: {residential_dominant_path} ({(dest['residential_filter'] == '2030 자취/거주성 높음').sum():,} rows)")
    print(f"   saved: {explanations_path} ({len(explanations):,} rows)")
    print(f"   saved: {hourly_path} ({len(hourly):,} rows)")
    print(f"   saved: {monthly_path} ({len(monthly):,} rows)")
    print(f"   saved: {monthly_all_path} ({len(monthly_all):,} rows)")
    print(f"   saved: {monthly_visitor_path} ({(monthly['residential_filter'] == '방문성 검토').sum():,} rows)")
    print(f"   saved: {monthly_trend_path} ({len(monthly_trend):,} rows)")
    print(f"   saved: {REPORTS_DIR / 'living_migration_2030_top20.md'}")
    print(f"   saved: {REPORTS_DIR / 'visitor_candidate_top20.md'}")
    print(f"   saved: {REPORTS_DIR / 'mixed_commercial_residential_top20.md'}")
    print(f"   saved: {REPORTS_DIR / 'residential_dominant_2030_top20.md'}")
    print(f"   saved: {REPORTS_DIR / 'candidate_explanation_report.md'}")
    print(f"   saved: {REPORTS_DIR / 'monthly_visitor_candidate_latest_top20.md'}")
    print(f"   saved: {REPORTS_DIR / 'monthly_candidate_trend_top20.md'}")

    print("\nTop 10 destination administrative dongs:")
    print(
        dest.head(10)[
            [
                "d_admdong_cd",
                "d_gu_name",
                "d_admdong_name",
                "residential_filter",
                "candidate_type",
                "adjusted_mobility_score",
                "mobility_score",
                "young_single_ratio",
                "cnt_2030",
                "avg_daily_2030",
                "date_count",
            ]
        ].to_string(index=False)
    )

    print("\n5. Committing output files to git...")
    if os.environ.get("SEOUL_SKIP_GIT") == "1":
        print("   SEOUL_SKIP_GIT=1 — skipping commit/push")
    else:
        commit_outputs()


def commit_outputs(
    git_user_name: str = "seoul-mobility-bot",
    git_user_email: str = "bot@seoul-mobility",
) -> None:
    """Stage output files, create a timestamped git commit, and push to remote."""
    repo_root = PROJECT_ROOT

    def run(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(args, cwd=repo_root, capture_output=True, text=True, check=check)

    # git이 없으면 건너뜀
    if subprocess.run(["which", "git"], capture_output=True).returncode != 0:
        print("   git not found — skipping commit")
        return

    # 저장소가 없으면 초기화
    if not (repo_root / ".git").exists():
        run(["git", "init"])
        print(f"   git init: {repo_root}")

    # Colab 등 git config가 없는 환경에서 최소 설정
    if not run(["git", "config", "user.name"], check=False).stdout.strip():
        run(["git", "config", "user.name", git_user_name])
        run(["git", "config", "user.email", git_user_email])

    # output 하위의 .md / .png / .csv 만 스테이징
    # SEOUL_OUTPUT_DIR이 repo 밖(Drive 등)이면 git add 대상이 없으므로 repo 내 output/ 경로도 시도
    output_rel = OUTPUT_ROOT.relative_to(repo_root) if OUTPUT_ROOT.is_relative_to(repo_root) else None
    base = str(output_rel) if output_rel else "output"
    patterns = [f"{base}/**/*.md", f"{base}/**/*.png", f"{base}/**/*.csv"]
    for pattern in patterns:
        result = run(["git", "add", "--", pattern], check=False)
        if result.returncode != 0 and result.stderr.strip():
            print(f"   warning (git add {pattern}): {result.stderr.strip()}")

    status = run(["git", "status", "--porcelain"], check=False).stdout.strip()
    if not status:
        print("   nothing to commit — output files unchanged")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"chore: update analysis outputs [{timestamp}]"
    result = run(["git", "commit", "-m", msg], check=False)
    if result.returncode != 0:
        print(f"   git commit failed: {result.stderr.strip()}")
        return

    short_hash = run(["git", "rev-parse", "--short", "HEAD"], check=False).stdout.strip()
    print(f"   committed: {short_hash} — {msg}")

    # 원격 저장소가 있으면 push
    remotes = run(["git", "remote"], check=False).stdout.strip()
    if not remotes:
        print("   no remote configured — skipping push (add one with: git remote add origin <url>)")
        return

    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], check=False).stdout.strip()
    push_result = run(["git", "push", "origin", branch], check=False)
    if push_result.returncode == 0:
        print(f"   pushed to origin/{branch}")
    else:
        print(f"   push failed: {push_result.stderr.strip()}")


if __name__ == "__main__":
    run_all()
