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

# SEOUL_RAW_DIR env var overrides the default raw path — used in Colab/Google Drive setups
_raw_env = os.environ.get("SEOUL_RAW_DIR")
RAW_DIR = Path(_raw_env) if _raw_env else ARCHIVE_DIR / "raw"

OUTPUT_ROOT = PROJECT_ROOT / "output"
PROCESSED_DIR = OUTPUT_ROOT / "processed"
REPORTS_DIR = OUTPUT_ROOT / "reports"

SUBWAY_CSV = RAW_DIR / "CARD_SUBWAY_MONTH_202604.csv"
BUS_CSV = RAW_DIR / "bus_time_station_202604.csv"
LIVING_MIGRATION_PATTERN = "seoul_purpose_admdong4_in_202603*.zip"
LIVING_MIGRATION_MONTH_END_MANIFEST = ARCHIVE_DIR / "metadata" / "living_migration_month_end_manifest.csv"
ADMIN_DONG_AREA_ZIP = RAW_DIR / "seoul_admin_dong_area.zip"
LIVING_INTEREST_XLSX = RAW_DIR / "seoul_living_interest_groups_202512.xlsx"

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
        "avg_move_time_2030",
        "avg_move_dist_2030",
        "total_cnt",
        "d_center_x",
        "d_center_y",
    ]
    other_cols = [col for col in enriched.columns if col not in display_cols]
    return enriched[display_cols + other_cols]


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
        f"{dataframe_to_markdown(latest.head(20)[latest_cols])}\n"
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
        "**2. 지하철/버스 — 행정동 공간 결합 미완성**\n\n"
        "현재 지하철·버스 데이터에는 역명·정류장명만 있고 좌표가 없습니다. "
        "행정동 경계(`admin_dong_mapping`)에는 중심 좌표가 있으나 "
        "역명-행정동 텍스트 매핑은 오류율이 높아 사용하지 않았습니다. "
        "다음 단계: 서울 열린데이터광장의 지하철역 좌표 또는 버스정류장 좌표 파일을 추가하면 "
        "행정동 경계와 공간 조인이 가능해 행정동별 교통 접근성 지표를 만들 수 있습니다.\n\n"
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
    print(f"   saved: {visitor_path} ({(dest['residential_filter'] == '방문성 검토').sum():,} rows)")
    print(f"   saved: {mixed_path} ({(dest['residential_filter'] == '혼재형 (상권+거주)').sum():,} rows)")
    print(f"   saved: {residential_dominant_path} ({(dest['residential_filter'] == '2030 자취/거주성 높음').sum():,} rows)")
    print(f"   saved: {hourly_path} ({len(hourly):,} rows)")
    print(f"   saved: {monthly_path} ({len(monthly):,} rows)")
    print(f"   saved: {monthly_visitor_path} ({(monthly['residential_filter'] == '방문성 검토').sum():,} rows)")
    print(f"   saved: {monthly_trend_path} ({len(monthly_trend):,} rows)")
    print(f"   saved: {REPORTS_DIR / 'living_migration_2030_top20.md'}")
    print(f"   saved: {REPORTS_DIR / 'visitor_candidate_top20.md'}")
    print(f"   saved: {REPORTS_DIR / 'mixed_commercial_residential_top20.md'}")
    print(f"   saved: {REPORTS_DIR / 'residential_dominant_2030_top20.md'}")
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


if __name__ == "__main__":
    run_all()
