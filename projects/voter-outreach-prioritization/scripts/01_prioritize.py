"""
Apply the same account-prioritization scoring logic used in
ar-collections-prioritizer (dollar/impact x urgency x history x risk) to
Durham precinct-level voter data from durham-voter-turnout-analysis, to
rank precincts for registration/turnout outreach.

Reads the committed, aggregated precinct summary produced by that project
(no raw individual-level data touched here).
"""
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

matplotlib.use("Agg")

HERE = Path(__file__).resolve().parent
PROJECT_DIR = HERE.parent
DATA_DIR = PROJECT_DIR / "data"
FIG_DIR = PROJECT_DIR / "figures"
SOURCE = PROJECT_DIR.parent / "durham-voter-turnout-analysis" / "data" / "durham_precinct_summary.csv"

INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"
BLUE = "#2a78d6"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "Arial", "sans-serif"],
    "axes.edgecolor": GRID,
    "axes.labelcolor": INK_SECONDARY,
    "text.color": INK_PRIMARY,
    "xtick.color": INK_MUTED,
    "ytick.color": INK_MUTED,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
})


def norm(s: pd.Series) -> pd.Series:
    rng = s.max() - s.min()
    return (s - s.min()) / rng if rng > 0 else s * 0


def main():
    df = pd.read_csv(SOURCE)
    df["turnout_gap"] = df["turnout_2024_General"] - df["turnout_2023_Municipal"]

    # Component A: scale/impact — bigger precincts = more potential registrants/voters
    # gained per unit of outreach effort. Mirrors "open_amount" in the O2C model.
    df["score_scale"] = norm(df["registered_active"])

    # Component B: urgency — how much of a precinct's general-election electorate
    # disengages for municipal elections. Mirrors "days_past_due".
    df["score_turnout_gap"] = norm(df["turnout_gap"])

    # Component C: historical weakness — registration rate gap (1 - rate).
    # Unmatched precincts (post-2020 boundary changes, no comparable population
    # figure) get the median gap imputed rather than being dropped or unfairly
    # penalized/boosted. Mirrors "avg_days_late_historical".
    reg_gap = 1 - df["registration_rate"]
    reg_gap_imputed = reg_gap.fillna(reg_gap.median())
    df["score_registration_gap"] = norm(reg_gap_imputed)
    df["registration_gap_imputed"] = df["registration_rate"].isna()

    # Component D: risk — how weak is municipal turnout in absolute terms, not
    # just relative to general. Mirrors "dispute_writeoff_rate".
    df["score_municipal_weakness"] = norm(1 - df["turnout_2023_Municipal"])

    df["priority_score"] = (
        0.35 * df["score_scale"]
        + 0.35 * df["score_turnout_gap"]
        + 0.20 * df["score_registration_gap"]
        + 0.10 * df["score_municipal_weakness"]
    ).round(3)

    df = df.sort_values("priority_score", ascending=False).reset_index(drop=True)
    df.insert(0, "priority_rank", df.index + 1)

    out_cols = [
        "priority_rank", "precinct_norm", "registered_active", "registration_rate",
        "registration_gap_imputed", "turnout_2024_General", "turnout_2023_Municipal",
        "turnout_gap", "priority_score",
    ]
    worklist = df[out_cols]

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    worklist.to_csv(DATA_DIR / "precinct_outreach_priority.csv", index=False)

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    top15 = worklist.head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    ax.barh(top15["precinct_norm"].astype(str), top15["priority_score"], color=BLUE, height=0.62)
    ax.set_xlabel("Outreach Priority Score (0-1)")
    ax.set_title("Top 15 Durham Precincts — Outreach Priority", fontsize=12, color=INK_PRIMARY, loc="left", pad=12)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(left=False)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "top_priority_precincts.png", dpi=160)
    plt.close(fig)

    print(worklist.head(15).to_string(index=False))
    print(f"\nWrote {DATA_DIR / 'precinct_outreach_priority.csv'}")


if __name__ == "__main__":
    main()
