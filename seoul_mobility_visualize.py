"""
Generate visualization charts for the Seoul mobility analysis outputs.

This script is intentionally separate from the notebook so the same chart
generation path works in local Python and Google Colab/Drive.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/seoul_mobility_matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/seoul_mobility_cache")
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)
os.makedirs(os.environ["XDG_CACHE_HOME"], exist_ok=True)

import matplotlib

if not os.environ.get("DISPLAY"):
    matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.patches import Patch


VISITOR_FILTERS = ["방문성 검토", "혼재형 (상권+거주)"]


def resolve_output_dir(output_dir: str | None = None) -> Path:
    if output_dir:
        return Path(output_dir)
    env_output = os.environ.get("SEOUL_OUTPUT_DIR")
    if env_output:
        return Path(env_output)
    return Path(__file__).resolve().parent / "output"


def setup_korean_font() -> None:
    """Use a Korean-capable font when available, but never fail charting for it."""
    candidates = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/Library/Fonts/AppleGothic.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for font_path in candidates:
        p = Path(font_path)
        if p.exists():
            try:
                font_manager.fontManager.addfont(str(p))
                plt.rcParams["font.family"] = font_manager.FontProperties(
                    fname=str(p)
                ).get_name()
                break
            except Exception:
                continue
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 120


def cmap(name: str, n: int | None = None):
    try:
        return matplotlib.colormaps[name].resampled(n) if n else matplotlib.colormaps[name]
    except Exception:
        return plt.cm.get_cmap(name, n)


def load_csv(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        print(f"[skip] file not found: {path}")
        return pd.DataFrame()
    try:
        return pd.read_csv(path, **kwargs)
    except Exception as exc:
        print(f"[skip] failed to read {path.name}: {exc}")
        return pd.DataFrame()


def ensure_columns(df: pd.DataFrame, columns: list[str], chart_name: str) -> bool:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        print(f"[skip] {chart_name} missing columns: {', '.join(missing)}")
        return False
    return True


def numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def name_column(df: pd.DataFrame, fallback: str = "d_admdong_cd") -> str:
    return "d_admdong_name" if "d_admdong_name" in df.columns else fallback


def save(fig, path: Path, show: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    print(f"[ok] {path.name}")


def next_run_dir(viz_root: Path) -> tuple[Path, str]:
    """Create a new sequential visualization run directory without overwriting old PNGs."""
    viz_root.mkdir(parents=True, exist_ok=True)
    run_numbers: list[int] = []
    for path in viz_root.iterdir():
        if not path.is_dir():
            continue
        match = re.fullmatch(r"run_(\d{3,})", path.name)
        if match:
            run_numbers.append(int(match.group(1)))
    run_no = max(run_numbers, default=0) + 1
    run_id = f"run_{run_no:03d}"
    run_dir = viz_root / run_id
    run_dir.mkdir(parents=False, exist_ok=False)
    return run_dir, run_id


def chart_path(viz_dir: Path, run_id: str, filename: str) -> Path:
    """Return a run-scoped chart path with the run id in the filename."""
    return viz_dir / f"{run_id}__{filename}"


def chart_1(monthly: pd.DataFrame, latest_month: str | None, months: list[str], viz_dir: Path, run_id: str, show: bool) -> bool:
    title = "chart 1"
    required = ["yyyymm", "d_admdong_cd", "residential_filter", "adjusted_mobility_score"]
    if monthly.empty or latest_month is None or not ensure_columns(monthly, required, title):
        return False
    data = numeric(monthly, ["adjusted_mobility_score"])
    top_dongs = (
        data[
            (data["yyyymm"] == latest_month)
            & data["residential_filter"].isin(VISITOR_FILTERS)
            & data["adjusted_mobility_score"].notna()
        ]
        .sort_values("adjusted_mobility_score", ascending=False)
        .head(15)["d_admdong_cd"]
        .tolist()
    )
    if not top_dongs:
        print("[skip] chart 1 no visitor candidates")
        return False
    fig, ax = plt.subplots(figsize=(16, 6))
    palette = cmap("tab20", len(top_dongs))
    label_col = name_column(data)
    for i, cd in enumerate(top_dongs):
        sub = data[data["d_admdong_cd"] == cd].sort_values("yyyymm")
        sub = sub[sub["adjusted_mobility_score"].notna()]
        if sub.empty:
            continue
        ax.plot(
            sub["yyyymm"],
            sub["adjusted_mobility_score"],
            marker="o",
            markersize=3,
            linewidth=1.5,
            label=str(sub[label_col].iloc[0]),
            color=palette(i / max(1, len(top_dongs))),
        )
    ax.set_title("방문성 후보 Top 15 월별 adjusted_mobility_score 추세", fontsize=14, pad=12)
    ax.set_xlabel("월")
    ax.set_ylabel("adjusted_mobility_score")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8)
    tick_every = max(1, len(months) // 12)
    ax.set_xticks(months[::tick_every])
    ax.tick_params(axis="x", rotation=45)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    save(fig, chart_path(viz_dir, run_id, "01_top15_monthly_score_trend.png"), show)
    return True


def chart_2(monthly: pd.DataFrame, trend: pd.DataFrame, months: list[str], viz_dir: Path, run_id: str, show: bool) -> bool:
    title = "chart 2"
    if monthly.empty or trend.empty:
        print("[skip] chart 2 data empty")
        return False
    if not ensure_columns(monthly, ["yyyymm", "d_admdong_cd", "adjusted_mobility_score"], title):
        return False
    if not ensure_columns(trend, ["d_admdong_cd", "residential_filter"], title):
        return False
    score_col = "avg_adjusted_mobility_score" if "avg_adjusted_mobility_score" in trend.columns else "adjusted_mobility_score"
    if score_col not in trend.columns:
        print("[skip] chart 2 no trend score column")
        return False
    trend_data = numeric(trend, [score_col])
    top_heat = (
        trend_data[trend_data["residential_filter"].isin(VISITOR_FILTERS) & trend_data[score_col].notna()]
        .sort_values(score_col, ascending=False)
        .head(30)
    )
    if top_heat.empty:
        print("[skip] chart 2 no trend candidates")
        return False
    dong_order = top_heat["d_admdong_cd"].tolist()
    label_col = name_column(top_heat)
    name_map = top_heat.set_index("d_admdong_cd")[label_col].to_dict()
    values = numeric(monthly, ["adjusted_mobility_score"])
    heat_df = (
        values[values["d_admdong_cd"].isin(dong_order)]
        .pivot_table(index="d_admdong_cd", columns="yyyymm", values="adjusted_mobility_score")
        .reindex(index=dong_order, columns=months)
    )
    if heat_df.dropna(how="all").empty:
        print("[skip] chart 2 heatmap values empty")
        return False
    heat_df.index = [name_map.get(cd, cd) for cd in heat_df.index]
    fig, ax = plt.subplots(figsize=(max(16, len(months) * 0.45), 10))
    im = ax.imshow(heat_df.astype(float).values, aspect="auto", cmap="RdYlGn", interpolation="nearest")
    plt.colorbar(im, ax=ax, shrink=0.8, label="adjusted_mobility_score")
    ax.set_yticks(range(len(heat_df.index)))
    ax.set_yticklabels(heat_df.index, fontsize=9)
    ax.set_xticks(range(len(heat_df.columns)))
    ax.set_xticklabels(heat_df.columns, rotation=90, fontsize=8)
    ax.set_title("방문성 후보 Top 30 행정동 x 월별 Score 히트맵", fontsize=14, pad=12)
    plt.tight_layout()
    save(fig, chart_path(viz_dir, run_id, "02_heatmap_dong_month.png"), show)
    return True


def chart_3(trend: pd.DataFrame, viz_dir: Path, run_id: str, show: bool) -> bool:
    title = "chart 3"
    if trend.empty or not ensure_columns(trend, ["score_slope", "residential_filter"], title):
        return False
    data = numeric(trend, ["score_slope"])
    tv = data[data["residential_filter"].isin(VISITOR_FILTERS) & data["score_slope"].notna()].copy()
    if tv.empty:
        print("[skip] chart 3 no slope values")
        return False
    combined = pd.concat([tv.nlargest(15, "score_slope"), tv.nsmallest(15, "score_slope")]).drop_duplicates()
    combined = combined.sort_values("score_slope")
    label_col = name_column(combined)
    labels = combined[label_col].astype(str).tolist()
    slopes = combined["score_slope"].tolist()
    colors = ["#d62728" if s < 0 else "#2ca02c" for s in slopes]
    fig, ax = plt.subplots(figsize=(10, max(8, len(labels) * 0.35)))
    ax.barh(range(len(labels)), slopes, color=colors)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Score Slope (월 단위 기울기)")
    ax.set_title("방문성 후보 행정동 Score 추세 - 상승 Top15 / 하락 Top15", fontsize=13, pad=10)
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    save(fig, chart_path(viz_dir, run_id, "03_score_slope_ranking.png"), show)
    return True


def chart_4(monthly: pd.DataFrame, latest_month: str | None, viz_dir: Path, run_id: str, show: bool) -> bool:
    title = "chart 4"
    required = ["yyyymm", "residential_filter", "adjusted_mobility_score"]
    if monthly.empty or latest_month is None or not ensure_columns(monthly, required, title):
        return False
    data = numeric(monthly, ["adjusted_mobility_score"])
    latest = (
        data[
            (data["yyyymm"] == latest_month)
            & data["residential_filter"].isin(VISITOR_FILTERS)
            & data["adjusted_mobility_score"].notna()
        ]
        .sort_values("adjusted_mobility_score", ascending=False)
        .head(20)
    )
    if latest.empty:
        print("[skip] chart 4 no latest visitor candidates")
        return False
    label_col = name_column(latest)
    filter_colors = {"방문성 검토": "#1f77b4", "혼재형 (상권+거주)": "#ff7f0e"}
    bar_colors = [filter_colors.get(r, "#7f7f7f") for r in latest["residential_filter"]]
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.barh(range(len(latest)), latest["adjusted_mobility_score"].values, color=bar_colors)
    ax.set_yticks(range(len(latest)))
    ax.set_yticklabels(latest[label_col].astype(str).tolist(), fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("adjusted_mobility_score")
    ax.set_title(f"최신 월({latest_month}) 방문성 후보 Top 20", fontsize=13, pad=10)
    ax.legend(handles=[Patch(facecolor=v, label=k) for k, v in filter_colors.items()], loc="lower right", fontsize=9)
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    save(fig, chart_path(viz_dir, run_id, "04_latest_month_top20.png"), show)
    return True


def chart_5(monthly: pd.DataFrame, latest_month: str | None, viz_dir: Path, run_id: str, show: bool) -> bool:
    title = "chart 5"
    required = ["yyyymm", "candidate_type", "residential_filter"]
    if monthly.empty or latest_month is None or not ensure_columns(monthly, required, title):
        return False
    latest = monthly[monthly["yyyymm"] == latest_month].copy()
    if latest.empty:
        print("[skip] chart 5 no latest rows")
        return False
    ct_rf = latest.groupby(["candidate_type", "residential_filter"]).size().unstack(fill_value=0)
    if ct_rf.empty:
        print("[skip] chart 5 no grouped values")
        return False
    ct_rf_pct = ct_rf.div(ct_rf.sum(axis=1).replace(0, np.nan), axis=0).fillna(0) * 100
    fig, axes = plt.subplots(1, 2, figsize=(16, 5))
    ct_rf.plot(kind="bar", stacked=True, ax=axes[0], colormap="Set2")
    axes[0].set_title("candidate_type x residential_filter (개수)", fontsize=12)
    axes[0].tick_params(axis="x", rotation=30)
    axes[0].legend(fontsize=8)
    ct_rf_pct.plot(kind="bar", stacked=True, ax=axes[1], colormap="Set2")
    axes[1].set_title("candidate_type x residential_filter (%)", fontsize=12)
    axes[1].set_ylabel("비율 (%)")
    axes[1].tick_params(axis="x", rotation=30)
    axes[1].legend(fontsize=8)
    plt.tight_layout()
    save(fig, chart_path(viz_dir, run_id, "05_candidate_type_distribution.png"), show)
    return True


def chart_6(monthly: pd.DataFrame, months: list[str], viz_dir: Path, run_id: str, show: bool) -> bool:
    title = "chart 6"
    if monthly.empty or not ensure_columns(monthly, ["yyyymm", "cnt_2030"], title):
        return False
    data = numeric(monthly, ["cnt_2030"])
    monthly_total = data.groupby("yyyymm", as_index=False)["cnt_2030"].sum().rename(columns={"cnt_2030": "total_2030"})
    if monthly_total.empty:
        print("[skip] chart 6 no monthly totals")
        return False
    fig, ax = plt.subplots(figsize=(16, 4))
    ax.plot(
        monthly_total["yyyymm"],
        monthly_total["total_2030"],
        marker="o",
        markersize=4,
        linewidth=1.5,
        color="#1f77b4",
        label="전체 2030 유입 합계",
    )
    if "is_weekend_snapshot" in data.columns:
        wknd_months = data.loc[data["is_weekend_snapshot"] == True, "yyyymm"].unique()
        wknd = monthly_total[monthly_total["yyyymm"].isin(wknd_months)]
        ax.scatter(wknd["yyyymm"], wknd["total_2030"], color="orange", zorder=5, s=60, label="주말 스냅샷")
    ax.set_title("서울 전체 월별 2030 유입량 추이 (월말 스냅샷 기준)", fontsize=13, pad=10)
    ax.set_xlabel("월")
    ax.set_ylabel("2030 유입 인원 (합계)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    tick_every = max(1, len(months) // 12)
    ax.set_xticks(months[::tick_every])
    ax.tick_params(axis="x", rotation=45)
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    save(fig, chart_path(viz_dir, run_id, "06_total_2030_monthly_trend.png"), show)
    return True


def chart_7(monthly: pd.DataFrame, latest_month: str | None, months: list[str], viz_dir: Path, run_id: str, show: bool) -> bool:
    title = "chart 7"
    required = ["yyyymm", "d_admdong_cd", "residential_filter", "adjusted_mobility_score"]
    if monthly.empty or latest_month is None or not ensure_columns(monthly, required, title):
        return False
    data = numeric(monthly, ["adjusted_mobility_score"])
    vm = data[data["residential_filter"].isin(VISITOR_FILTERS) & data["adjusted_mobility_score"].notna()].copy()
    if vm.empty:
        print("[skip] chart 7 no visitor candidates")
        return False
    vm["visitor_rank"] = vm.groupby("yyyymm")["adjusted_mobility_score"].rank(ascending=False, method="min")
    top_dongs = vm[vm["yyyymm"] == latest_month].sort_values("visitor_rank").head(10)["d_admdong_cd"].tolist()
    if not top_dongs:
        print("[skip] chart 7 no latest ranks")
        return False
    label_col = name_column(vm)
    fig, ax = plt.subplots(figsize=(16, 6))
    palette = cmap("tab10", len(top_dongs))
    for i, cd in enumerate(top_dongs):
        sub = vm[vm["d_admdong_cd"] == cd].sort_values("yyyymm")
        if sub.empty:
            continue
        ax.plot(
            sub["yyyymm"],
            sub["visitor_rank"],
            marker="o",
            markersize=4,
            linewidth=1.5,
            label=str(sub[label_col].iloc[0]),
            color=palette(i / max(1, len(top_dongs))),
        )
    ax.invert_yaxis()
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.set_title("방문성 후보 Top 10 월별 순위 변화 (1위 = 상단)", fontsize=13, pad=10)
    ax.set_xlabel("월")
    ax.set_ylabel("방문성 후보 순위")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8)
    tick_every = max(1, len(months) // 12)
    ax.set_xticks(months[::tick_every])
    ax.tick_params(axis="x", rotation=45)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    save(fig, chart_path(viz_dir, run_id, "07_bump_chart_visitor_rank.png"), show)
    return True


def chart_8(dest: pd.DataFrame, viz_dir: Path, run_id: str, show: bool) -> bool:
    title = "chart 8"
    if dest.empty or not ensure_columns(dest, ["visit_pattern_type"], title):
        return False
    order = ["목적 방문형", "복합형", "생활 밀착형", "불명확"]
    counts = dest["visit_pattern_type"].value_counts().reindex([v for v in order if v in dest["visit_pattern_type"].values]).dropna()
    if counts.empty:
        print("[skip] chart 8 no visit pattern values")
        return False
    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.barh(counts.index.astype(str), counts.values, color=["#e74c3c", "#f39c12", "#3498db", "#bdc3c7"][: len(counts)])
    ax.bar_label(bars, padding=4)
    ax.set_xlabel("행정동 수")
    ax.set_title("방문 패턴 유형 분포 (visit_pattern_type)", fontsize=13, fontweight="bold")
    ax.invert_yaxis()
    plt.tight_layout()
    save(fig, chart_path(viz_dir, run_id, "08_visit_pattern_type.png"), show)
    return True


def chart_9(dest: pd.DataFrame, viz_dir: Path, run_id: str, show: bool) -> bool:
    title = "chart 9"
    if dest.empty or not ensure_columns(dest, ["adjusted_mobility_score"], title):
        return False
    score_y = "commercial_potential_score" if "commercial_potential_score" in dest.columns else "adjusted_mobility_score"
    data = numeric(dest, ["adjusted_mobility_score", score_y])
    plot_data = data[["adjusted_mobility_score", score_y]].replace([np.inf, -np.inf], np.nan).dropna()
    if plot_data.empty:
        print("[skip] chart 9 no finite score values")
        return False
    data = data.loc[plot_data.index]
    top_n = data.nlargest(min(30, len(data)), score_y)
    label_col = name_column(data)
    fig, ax = plt.subplots(figsize=(10, 6))
    sc = ax.scatter(
        data["adjusted_mobility_score"],
        data[score_y],
        c=data[score_y],
        cmap="RdYlGn",
        alpha=0.6,
        s=30,
        linewidths=0,
    )
    for _, row in top_n.iterrows():
        ax.annotate(str(row[label_col]), (row["adjusted_mobility_score"], row[score_y]), fontsize=7, ha="left", va="bottom")
    plt.colorbar(sc, ax=ax, label=score_y)
    ax.set_xlabel("adjusted_mobility_score")
    ax.set_ylabel(score_y)
    ax.set_title("이동 기반 점수 vs 상권 잠재력 복합 점수", fontsize=13, fontweight="bold")
    plt.tight_layout()
    save(fig, chart_path(viz_dir, run_id, "09_commercial_potential_scatter.png"), show)
    return True


def chart_10(bjdong: pd.DataFrame, viz_dir: Path, run_id: str, show: bool) -> bool:
    title = "chart 10"
    if bjdong.empty:
        print("[skip] chart 10 bjdong data empty")
        return False
    score_col = "commercial_potential_score" if "commercial_potential_score" in bjdong.columns else "adjusted_mobility_score"
    if score_col not in bjdong.columns:
        print("[skip] chart 10 no score column")
        return False
    data = numeric(bjdong, [score_col])
    data = data[data[score_col].notna()]
    if data.empty:
        print("[skip] chart 10 no score values")
        return False
    nm_col = "bjdong_nm" if "bjdong_nm" in data.columns else data.columns[0]
    top20 = data.nlargest(min(20, len(data)), score_col)
    vpt_color = {"목적 방문형": "#e74c3c", "복합형": "#f39c12", "생활 밀착형": "#3498db", "불명확": "#bdc3c7"}
    colors = [vpt_color.get(v, "#95a5a6") for v in top20.get("visit_pattern_type", pd.Series(["불명확"] * len(top20)))]
    fig, ax = plt.subplots(figsize=(10, 7))
    bars = ax.barh(top20[nm_col].astype(str), top20[score_col], color=colors)
    ax.bar_label(bars, fmt="%.2f", padding=4, fontsize=8)
    ax.set_xlabel(score_col)
    ax.set_title(f"법정동 Top 20 - {score_col}", fontsize=13, fontweight="bold")
    ax.invert_yaxis()
    ax.legend(handles=[Patch(facecolor=c, label=l) for l, c in vpt_color.items()], loc="lower right", fontsize=8)
    plt.tight_layout()
    save(fig, chart_path(viz_dir, run_id, "10_bjdong_top20.png"), show)
    return True


def generate_visualizations(output_dir: Path, show: bool = False) -> list[Path]:
    setup_korean_font()
    processed = output_dir / "processed"
    viz_root = output_dir / "reports" / "viz"
    viz_dir, run_id = next_run_dir(viz_root)

    print(f"Output directory: {output_dir}")
    print(f"Visualization run: {run_id}")
    print(f"Visualization directory: {viz_dir}")
    if not processed.exists():
        raise FileNotFoundError(f"processed directory not found: {processed}")

    monthly = load_csv(processed / "monthly_living_migration_2030_summary.csv", dtype={"d_admdong_cd": str})
    trend = load_csv(processed / "monthly_candidate_trend_summary.csv", dtype={"d_admdong_cd": str})
    dest = load_csv(processed / "living_migration_2030_destination_summary.csv", dtype={"d_admdong_cd": str})
    bjdong = load_csv(processed / "bjdong_candidate_summary.csv", dtype={"bjdong_cd": str})

    months: list[str] = []
    latest_month: str | None = None
    if not monthly.empty and "yyyymm" in monthly.columns:
        monthly["yyyymm"] = monthly["yyyymm"].astype(str)
        months = sorted(monthly["yyyymm"].dropna().unique().tolist())
        latest_month = months[-1] if months else None
        print(f"Monthly rows: {len(monthly):,}, months: {months[0] if months else '-'} ~ {latest_month or '-'}")
    else:
        print("[skip] monthly summary is empty or has no yyyymm")

    chart_funcs = [
        lambda: chart_1(monthly, latest_month, months, viz_dir, run_id, show),
        lambda: chart_2(monthly, trend, months, viz_dir, run_id, show),
        lambda: chart_3(trend, viz_dir, run_id, show),
        lambda: chart_4(monthly, latest_month, viz_dir, run_id, show),
        lambda: chart_5(monthly, latest_month, viz_dir, run_id, show),
        lambda: chart_6(monthly, months, viz_dir, run_id, show),
        lambda: chart_7(monthly, latest_month, months, viz_dir, run_id, show),
        lambda: chart_8(dest, viz_dir, run_id, show),
        lambda: chart_9(dest, viz_dir, run_id, show),
        lambda: chart_10(bjdong, viz_dir, run_id, show),
    ]

    made = 0
    for fn in chart_funcs:
        try:
            made += int(bool(fn()))
        except Exception as exc:
            print(f"[skip] chart failed: {type(exc).__name__}: {exc}")

    pngs = sorted(viz_dir.glob("*.png"))
    print(f"Generated {made} charts. PNG files in {viz_dir}:")
    for png in pngs:
        print(f"  {png.name}")
    return pngs


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Seoul mobility visualization PNGs.")
    parser.add_argument("--output-dir", default=None, help="Analysis output directory. Defaults to SEOUL_OUTPUT_DIR or ./output.")
    parser.add_argument("--show", action="store_true", help="Display figures in interactive environments.")
    args = parser.parse_args()

    generate_visualizations(resolve_output_dir(args.output_dir), show=args.show)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
