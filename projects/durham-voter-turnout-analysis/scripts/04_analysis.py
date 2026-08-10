"""
Core analysis: Durham County registration rates and turnout by precinct,
election, and age group.

Inputs (from prior scripts):
  raw/durham_voter_registration.csv   (gitignored, from NC SBE)
  raw/durham_voter_history.csv        (gitignored, from NC SBE)
  data/durham_vtd_population_2020.csv (committed, from Census PL94-171)
  data/durham_precincts.geojson       (committed, from NC SBE precinct shapefile)

Outputs (all committed, aggregate-only, no individual-level data):
  data/durham_precinct_summary.csv
  data/durham_turnout_by_election.csv
  data/durham_turnout_by_age.csv
  figures/*.png
"""
import json
import re
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection

matplotlib.use("Agg")

HERE = Path(__file__).resolve().parent
PROJECT_DIR = HERE.parent
RAW_DIR = PROJECT_DIR / "raw"
DATA_DIR = PROJECT_DIR / "data"
FIG_DIR = PROJECT_DIR / "figures"

# --- palette ---
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#4a3aa7"]  # categorical slots 1,2,3,4,7
SEQ_BLUE_5 = ["#cde2fb", "#9ec5f4", "#5598e7", "#2a78d6", "#184f95"]
STATUS_CRIT = "#d03b3b"
STATUS_GOOD = "#0ca30c"

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

KEY_ELECTIONS = [
    ("11/08/2016", "2016 General"),
    ("11/06/2018", "2018 General"),
    ("11/03/2020", "2020 General"),
    ("11/02/2021", "2021 Municipal"),
    ("11/08/2022", "2022 General"),
    ("11/07/2023", "2023 Municipal"),
    ("11/05/2024", "2024 General"),
]


def normalize_precinct(code: str) -> str:
    """Normalize precinct codes to a common form across the three sources:
    strip leading zeros on the leading numeric run, pad plain numbers to 2
    digits (e.g. '001' / '01' / '1' -> '01'; '055-11' -> '55-11')."""
    if not isinstance(code, str) or not code.strip():
        return ""
    code = code.strip()
    m = re.match(r"^0*(\d+)(.*)$", code)
    if not m:
        return code
    num, rest = m.groups()
    return f"{int(num):02d}{rest}"


def load_registration():
    reg = pd.read_csv(RAW_DIR / "durham_voter_registration.csv", dtype=str)
    reg["precinct_norm"] = reg["precinct_abbrv"].map(normalize_precinct)
    reg["age_at_year_end"] = pd.to_numeric(reg["age_at_year_end"], errors="coerce")
    reg["registr_dt"] = pd.to_datetime(reg["registr_dt"], format="%m/%d/%Y", errors="coerce")
    return reg


def load_history():
    hist = pd.read_csv(RAW_DIR / "durham_voter_history.csv", dtype=str)
    hist["precinct_norm"] = hist["pct_label"].map(normalize_precinct)
    return hist


def load_population():
    pop = pd.read_csv(DATA_DIR / "durham_vtd_population_2020.csv", dtype={"precinct_code": str})
    pop["precinct_norm"] = pop["precinct_code"].map(normalize_precinct)
    return pop.groupby("precinct_norm", as_index=False)["total_population_2020"].sum()


def load_precincts_geojson():
    with open(DATA_DIR / "durham_precincts.geojson") as f:
        gj = json.load(f)
    for feat in gj["features"]:
        feat["properties"]["precinct_norm"] = normalize_precinct(feat["properties"]["precinct_code"])
    return gj


def build_precinct_summary(reg, hist, pop):
    active = reg[reg["status_cd"] == "A"].copy()

    base = active.groupby("precinct_norm").agg(
        registered_active=("ncid", "count"),
        pct_dem=("party_cd", lambda s: (s == "DEM").mean()),
        pct_rep=("party_cd", lambda s: (s == "REP").mean()),
        pct_una=("party_cd", lambda s: (s == "UNA").mean()),
        pct_black=("race_code", lambda s: (s == "B").mean()),
        pct_white=("race_code", lambda s: (s == "W").mean()),
        median_age=("age_at_year_end", "median"),
    ).reset_index()

    base = base.merge(pop, on="precinct_norm", how="left")
    base["registration_rate"] = base["registered_active"] / base["total_population_2020"]

    # Turnout per key election, restricted to currently-active registrants who
    # were ALREADY REGISTERED as of that election (registr_dt <= election date).
    # Without this filter, older elections look artificially low-turnout simply
    # because many of today's registrants weren't registered yet back then.
    for lbl, name in KEY_ELECTIONS:
        election_date = pd.Timestamp(lbl)
        eligible = active[active["registr_dt"] <= election_date]
        eligible_by_precinct = eligible.groupby("precinct_norm")["ncid"].apply(set)
        voters_this_election = set(hist.loc[hist["election_lbl"] == lbl, "ncid"])
        col = f"turnout_{name.replace(' ', '_')}"
        base[col] = base["precinct_norm"].map(
            lambda p: (len(eligible_by_precinct.get(p, set()) & voters_this_election) / len(eligible_by_precinct.get(p, set())))
            if len(eligible_by_precinct.get(p, set())) > 0 else np.nan
        )

    return base.sort_values("precinct_norm").reset_index(drop=True)


def build_turnout_by_election(reg, hist):
    """Countywide turnout rate among currently-active registrants who were
    already registered as of each election, split General vs Municipal."""
    active = reg[reg["status_cd"] == "A"]
    rows = []
    for lbl, name in KEY_ELECTIONS:
        election_date = pd.Timestamp(lbl)
        eligible_ncids = set(active.loc[active["registr_dt"] <= election_date, "ncid"])
        voters = set(hist.loc[hist["election_lbl"] == lbl, "ncid"])
        turnout = len(eligible_ncids & voters) / len(eligible_ncids)
        kind = "Municipal" if "Municipal" in name else "General"
        rows.append({"election": name, "election_lbl": lbl, "kind": kind,
                      "eligible_registrants": len(eligible_ncids), "turnout_rate": turnout})
    return pd.DataFrame(rows)


def build_turnout_by_age(reg, hist):
    active = reg[reg["status_cd"] == "A"].copy()
    bins = [17, 25, 35, 50, 65, 120]
    labels = ["18-25", "26-35", "36-50", "51-65", "66+"]
    active["age_bucket"] = pd.cut(active["age_at_year_end"], bins=bins, labels=labels)

    focus = [("11/05/2024", "2024 General"), ("11/07/2023", "2023 Municipal")]
    rows = []
    for age_bucket, grp in active.groupby("age_bucket", observed=True):
        row = {"age_bucket": age_bucket}
        for lbl, name in focus:
            election_date = pd.Timestamp(lbl)
            eligible = set(grp.loc[grp["registr_dt"] <= election_date, "ncid"])
            voters = set(hist.loc[hist["election_lbl"] == lbl, "ncid"])
            row[name] = len(eligible & voters) / len(eligible) if eligible else np.nan
        row["registered_active"] = len(grp)
        rows.append(row)
    return pd.DataFrame(rows)


def choropleth(ax, geojson, values: dict, cmap_colors, vmin=None, vmax=None, missing_color="#e1e0d9"):
    vals = [v for v in values.values() if v is not None and not (isinstance(v, float) and np.isnan(v))]
    vmin = vmin if vmin is not None else min(vals)
    vmax = vmax if vmax is not None else max(vals)

    from matplotlib.colors import LinearSegmentedColormap, Normalize
    cmap = LinearSegmentedColormap.from_list("seq", cmap_colors)
    norm = Normalize(vmin=vmin, vmax=vmax)

    patches, colors = [], []
    all_x, all_y = [], []
    for feat in geojson["features"]:
        p = feat["properties"]["precinct_norm"]
        val = values.get(p)
        color = missing_color if (val is None or (isinstance(val, float) and np.isnan(val))) else cmap(norm(val))
        geom = feat["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in polys:
            ring = poly[0]  # exterior ring only
            xs = [pt[0] for pt in ring]
            ys = [pt[1] for pt in ring]
            all_x.extend(xs)
            all_y.extend(ys)
            patches.append(Polygon(list(zip(xs, ys)), closed=True))
            colors.append(color)

    pc = PatchCollection(patches, facecolor=colors, edgecolor=SURFACE, linewidth=0.6)
    ax.add_collection(pc)
    ax.set_xlim(min(all_x), max(all_x))
    ax.set_ylim(min(all_y), max(all_y))
    ax.set_aspect("equal")
    ax.axis("off")
    return cmap, norm


def make_figures(summary, turnout_by_election, turnout_by_age, geojson):
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    # --- Registration rate choropleth ---
    # Cap the color scale at the 95th percentile: one precinct (32, a small,
    # fast-growing precinct) shows >100% because its population grew a lot
    # since the 2020 Census count used as the denominator — capping keeps the
    # map legible; the true value is preserved in the underlying data/CSV.
    fig, ax = plt.subplots(figsize=(7, 6.5))
    values = dict(zip(summary["precinct_norm"], summary["registration_rate"]))
    vmax = float(np.nanpercentile(summary["registration_rate"], 95))
    cmap, norm = choropleth(ax, geojson, values, SEQ_BLUE_5, vmin=0.30, vmax=vmax)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    cbar = fig.colorbar(sm, ax=ax, fraction=0.04, pad=0.02, format=lambda x, _: f"{x:.0%}", extend="max")
    cbar.outline.set_visible(False)
    cbar.ax.tick_params(color=INK_MUTED, labelcolor=INK_MUTED, labelsize=8)
    ax.set_title("Registered (Active) Voters as % of Total Population\nby Precinct", fontsize=12, color=INK_PRIMARY, loc="left")
    fig.text(0.02, 0.02, "Gray = precinct boundary changed since 2020 Census; population not comparable.\nScale capped at 95th pct. — 1 fast-growing precinct exceeds 100% (2020 pop. base).",
              fontsize=7.5, color=INK_MUTED)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "registration_rate_map.png", dpi=160)
    plt.close(fig)

    # --- Turnout gap choropleth (2024 General vs 2023 Municipal) ---
    summary["turnout_gap"] = summary["turnout_2024_General"] - summary["turnout_2023_Municipal"]
    fig, ax = plt.subplots(figsize=(7, 6.5))
    values = dict(zip(summary["precinct_norm"], summary["turnout_gap"]))
    cmap, norm = choropleth(ax, geojson, values, ["#cde2fb", "#2a78d6", "#184f95"])
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    cbar = fig.colorbar(sm, ax=ax, fraction=0.04, pad=0.02, format=lambda x, _: f"{x:.0%}")
    cbar.outline.set_visible(False)
    cbar.ax.tick_params(color=INK_MUTED, labelcolor=INK_MUTED, labelsize=8)
    ax.set_title("Turnout Drop-Off: 2024 General → 2023 Municipal\nby Precinct (percentage points)", fontsize=12, color=INK_PRIMARY, loc="left")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "turnout_gap_map.png", dpi=160)
    plt.close(fig)

    # --- Turnout by election, General vs Municipal ---
    fig, ax = plt.subplots(figsize=(8, 4.4))
    colors = [CAT[0] if k == "General" else CAT[1] for k in turnout_by_election["kind"]]
    bars = ax.bar(turnout_by_election["election"], turnout_by_election["turnout_rate"], color=colors, width=0.6)
    ax.set_ylabel("Turnout rate (of active registrants)")
    ax.set_title("Turnout Among Currently-Registered Durham Voters, by Election", fontsize=12, color=INK_PRIMARY, loc="left", pad=12)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(left=False, axis="x", rotation=30)
    ax.yaxis.set_major_formatter(lambda x, _: f"{x:.0%}")
    ax.set_ylim(0, turnout_by_election["turnout_rate"].max() * 1.15)
    for rect, val in zip(bars, turnout_by_election["turnout_rate"]):
        ax.annotate(f"{val:.0%}", (rect.get_x() + rect.get_width() / 2, rect.get_height()),
                    ha="center", va="bottom", fontsize=8.5, color=INK_SECONDARY, xytext=(0, 3), textcoords="offset points")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=CAT[0], label="General"), Patch(color=CAT[1], label="Municipal")],
              frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.06), ncol=2, fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "turnout_by_election.png", dpi=160)
    plt.close(fig)

    # --- Turnout by age bucket ---
    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    x = np.arange(len(turnout_by_age))
    width = 0.35
    ax.bar(x - width / 2, turnout_by_age["2024 General"], width, color=CAT[0], label="2024 General")
    ax.bar(x + width / 2, turnout_by_age["2023 Municipal"], width, color=CAT[1], label="2023 Municipal")
    ax.set_xticks(x)
    ax.set_xticklabels(turnout_by_age["age_bucket"])
    ax.set_ylabel("Turnout rate")
    ax.set_title("Turnout by Age Group: General vs. Municipal Election", fontsize=12, color=INK_PRIMARY, loc="left", pad=12)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(left=False)
    ax.yaxis.set_major_formatter(lambda x, _: f"{x:.0%}")
    ax.set_ylim(0, max(turnout_by_age["2024 General"].max(), turnout_by_age["2023 Municipal"].max()) * 1.15)
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.14), ncol=2, fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "turnout_by_age.png", dpi=160)
    plt.close(fig)

    # --- Lowest registration-rate precincts (ranked) ---
    ranked = summary.dropna(subset=["registration_rate"]).sort_values("registration_rate").head(15)
    fig, ax = plt.subplots(figsize=(7.5, 6))
    ax.barh(ranked["precinct_norm"], ranked["registration_rate"], color=CAT[0], height=0.62)
    ax.set_xlabel("Registration rate (active registered / total population)")
    ax.set_title("15 Lowest Registration-Rate Precincts", fontsize=12, color=INK_PRIMARY, loc="left", pad=12)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.invert_yaxis()
    ax.tick_params(left=False)
    ax.xaxis.set_major_formatter(lambda x, _: f"{x:.0%}")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "lowest_registration_precincts.png", dpi=160)
    plt.close(fig)


def main():
    print("Loading data...")
    reg = load_registration()
    hist = load_history()
    pop = load_population()
    geojson = load_precincts_geojson()

    print("Building precinct summary...")
    summary = build_precinct_summary(reg, hist, pop)
    matched = summary["total_population_2020"].notna().sum()
    print(f"  {matched}/{len(summary)} precincts matched to a 2020 Census population figure")

    print("Building turnout by election...")
    turnout_by_election = build_turnout_by_election(reg, hist)

    print("Building turnout by age...")
    turnout_by_age = build_turnout_by_age(reg, hist)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(DATA_DIR / "durham_precinct_summary.csv", index=False)
    turnout_by_election.to_csv(DATA_DIR / "durham_turnout_by_election.csv", index=False)
    turnout_by_age.to_csv(DATA_DIR / "durham_turnout_by_age.csv", index=False)

    print("Making figures...")
    make_figures(summary, turnout_by_election, turnout_by_age, geojson)

    print("\n=== Turnout by election ===")
    print(turnout_by_election[["election", "turnout_rate"]].to_string(index=False))
    print("\n=== Turnout by age (2024 General vs 2023 Municipal) ===")
    print(turnout_by_age.to_string(index=False))
    print("\n=== Lowest registration-rate precincts ===")
    print(summary.dropna(subset=["registration_rate"]).sort_values("registration_rate")
          [["precinct_norm", "registered_active", "total_population_2020", "registration_rate"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
