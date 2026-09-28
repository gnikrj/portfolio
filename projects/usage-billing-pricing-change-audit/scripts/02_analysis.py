"""
Independent re-rating audit of billed invoices across a price-book change,
plus the AR consequences of getting billing wrong.

Approach: rebuild what every invoice *should* have been from two sources the
billing team doesn't control - the contract terms (commit, v2 effective
month) and the metered usage feed - then compare line by line to what was
actually billed. No answer key is used; the generator's error flags were
never written to disk.

Outputs:
  data/billing_exceptions.csv        ranked worklist: credit-memo vs rebill
  data/exception_summary_by_month.csv
  data/ar_by_channel.csv
  data/control_tests.csv
  figures/exceptions_by_month.png
  figures/dispute_rate_by_billing_accuracy.png
  figures/dso_by_channel.png
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

AS_OF = pd.Timestamp("2026-08-31")
PRICE_CHANGE = pd.Timestamp("2025-11-01")
V1_HOSTING_RATE, V1_AI_RATE, V2_HOSTING_RATE = 12.00, 0.08, 15.00

# --- palette (same validated default palette as the other projects) ---
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"
BLUE = "#2a78d6"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # categorical slots 1-4, fixed order

EXCEPTION_TYPES = [  # fixed order -> fixed color
    "Overage not billed",
    "AI add-on billed after bundle",
    "Stale v1 rate after renewal",
    "v2 rate applied before renewal",
]
# Errors the customer can see on the invoice (a line or rate that isn't in
# their contract) vs. errors they can't (a charge that's simply missing).
CUSTOMER_VISIBLE = {"AI add-on billed after bundle", "v2 rate applied before renewal"}

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "Arial", "DejaVu Sans"],
    "axes.edgecolor": GRID,
    "axes.labelcolor": INK_SECONDARY,
    "text.color": INK_PRIMARY,
    "xtick.color": INK_MUTED,
    "ytick.color": INK_MUTED,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
})


def load():
    accounts = pd.read_csv(DATA_DIR / "accounts.csv", parse_dates=["v2_effective_month"])
    usage = pd.read_csv(DATA_DIR / "usage_monthly.csv", parse_dates=["month"])
    lines = pd.read_csv(DATA_DIR / "invoice_lines.csv", parse_dates=["service_month"])
    invoices = pd.read_csv(DATA_DIR / "invoices.csv", parse_dates=["service_month", "issue_date", "due_date", "payment_date"])
    return accounts, usage, lines, invoices


def expected_billing(accounts, usage):
    """What each account-month should have been billed under its contract."""
    e = usage.merge(accounts, on="account_id")
    e["expected_on_v2"] = e["month"] >= e["v2_effective_month"]
    e["expected_rate"] = np.where(e["expected_on_v2"], V2_HOSTING_RATE, V1_HOSTING_RATE)
    e["expected_overage_gb"] = (e["gb_hosted"] - e["committed_gb_per_month"]).clip(lower=0).round(1)
    e["expected_amount"] = (
        e["committed_gb_per_month"] * e["expected_rate"]
        + e["expected_overage_gb"] * e["expected_rate"]
        + np.where(e["expected_on_v2"], 0.0, e["ai_docs_reviewed"] * V1_AI_RATE)
    ).round(2)
    return e.rename(columns={"month": "service_month"})


def find_exceptions(expected, lines, invoices):
    billed = lines.pivot_table(index="invoice_id", columns="line_type", values="amount", aggfunc="sum").fillna(0.0)
    hosting_rate = lines[lines.line_type == "Committed hosting"].set_index("invoice_id")["unit_rate"]
    billed = billed.join(hosting_rate.rename("billed_rate"))

    df = invoices.merge(expected, on=["account_id", "service_month"]).set_index("invoice_id").join(billed)
    for col in ["Hosting overage", "AI review add-on"]:
        if col not in df:
            df[col] = 0.0

    rate_off = ~np.isclose(df["billed_rate"], df["expected_rate"])
    conditions = [
        rate_off & df["expected_on_v2"],                                  # v1 rate still applied after renewal
        rate_off & ~df["expected_on_v2"],                                 # v2 rate applied before renewal
        df["expected_on_v2"] & (df["AI review add-on"] > 0),              # AI charged after bundle
        (df["expected_overage_gb"] > 0) & (df["Hosting overage"] == 0),   # overage missed
    ]
    choices = ["Stale v1 rate after renewal", "v2 rate applied before renewal",
               "AI add-on billed after bundle", "Overage not billed"]
    df["exception"] = np.select(conditions, choices, default="")
    df["variance"] = (df["amount"] - df["expected_amount"]).round(2)
    df["action"] = np.where(df["variance"] > 0, "Issue credit memo", np.where(df["variance"] < 0, "Rebill / supplemental invoice", ""))
    return df.reset_index()


def ar_by_channel(df):
    rows = []
    trailing = df[(df.issue_date > AS_OF - pd.Timedelta(days=91)) & (df.issue_date <= AS_OF)]
    for channel, g in df.groupby("channel"):
        open_ar = g.loc[g.status != "Paid", "amount"].sum()
        past_due = g.loc[(g.status != "Paid") & (g.due_date < AS_OF), "amount"].sum()
        billed_91 = trailing.loc[trailing.channel == channel, "amount"].sum()
        paid = g[g.status == "Paid"]
        rows.append({
            "channel": channel,
            "open_ar": round(open_ar, 0),
            "pct_past_due": round(past_due / open_ar * 100, 1) if open_ar else 0.0,
            "dso_days": round(open_ar / billed_91 * 91, 1) if billed_91 else np.nan,
            "avg_days_to_pay": round((paid.payment_date - paid.issue_date).dt.days.mean(), 1),
            "dispute_rate_pct": round(g.ever_disputed.mean() * 100, 1),
            "usage_volatility_cv": round(g.groupby("account_id").gb_hosted.agg(lambda s: s.std() / s.mean()).mean(), 2),
        })
    return pd.DataFrame(rows).sort_values("dso_days", ascending=False)


def control_tests(df):
    post = df[df.service_month >= PRICE_CHANGE]
    tests = [
        ("Hosting rate on invoice matches contracted price book", df, ~np.isin(df.exception, ["Stale v1 rate after renewal", "v2 rate applied before renewal"])),
        ("No AI add-on billed on bundled (v2) contracts", df[df.expected_on_v2], df.loc[df.expected_on_v2, "exception"] != "AI add-on billed after bundle"),
        ("All metered overage above commit is invoiced", df[df.expected_overage_gb > 0], df.loc[df.expected_overage_gb > 0, "exception"] != "Overage not billed"),
        ("Invoice total ties to re-rated contract x usage (+/- $1)", df, df.variance.abs() <= 1),
        ("  ...same test, post price-change months only", post, post.variance.abs() <= 1),
    ]
    rows = []
    for name, pop, passed in tests:
        n = len(pop)
        rows.append({"control_test": name, "population": n, "exceptions": int(n - passed.sum()),
                     "pass_rate_pct": round(passed.sum() / n * 100, 1)})
    return pd.DataFrame(rows)


def style_axes(ax):
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)


def plot_exceptions_by_month(summary):
    months = pd.date_range(summary.index.min(), summary.index.max(), freq="MS")
    summary = summary.reindex(months, fill_value=0.0)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    bottom = np.zeros(len(summary))
    x = np.arange(len(summary))
    for etype, color in zip(EXCEPTION_TYPES, SERIES):
        vals = summary.get(etype, pd.Series(0.0, index=summary.index)).values / 1000
        ax.bar(x, vals, bottom=bottom, color=color, width=0.72, label=etype, edgecolor=SURFACE, linewidth=1.5)
        bottom += vals
    pc = list(summary.index).index(PRICE_CHANGE)
    ax.axvline(pc - 0.5, color=INK_SECONDARY, linewidth=1, linestyle="--")
    ax.set_ylim(0, bottom.max() * 1.22)
    ax.text(pc - 0.35, bottom.max() * 1.2, "Price book v2 launches\n(existing contracts move at renewal)",
            color=INK_SECONDARY, fontsize=9, va="top")
    ax.set_xticks(x[::2])
    ax.set_xticklabels([d.strftime("%b %y") for d in summary.index[::2]], fontsize=9)
    ax.set_ylabel("Mis-billed amount, $K (absolute)")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    style_axes(ax)
    ax.legend(frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncols=4)
    ax.set_title("Billing exceptions jump when two price books run side by side", loc="left", fontsize=13, pad=12)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "exceptions_by_month.png", dpi=150)
    plt.close(fig)


def plot_dispute_rate(df):
    grp = np.where(df.exception.isin(CUSTOMER_VISIBLE), "Visible error\n(line/rate not in contract)",
                   np.where(df.exception != "", "Silent error\n(missing charge)", "Clean invoices"))
    order = ["Clean invoices", "Silent error\n(missing charge)", "Visible error\n(line/rate not in contract)"]
    stats = df.assign(group=grp).groupby("group").agg(rate=("ever_disputed", "mean"), n=("invoice_id", "count")).reindex(order)
    fig, ax = plt.subplots(figsize=(8, 3.6))
    y = np.arange(len(order))
    ax.barh(y, stats.rate * 100, color=BLUE, height=0.55)
    for yi, (rate, n) in enumerate(zip(stats.rate, stats.n)):
        ax.text(rate * 100 + 0.8, yi, f"{rate*100:.0f}%  (n={n:,})", va="center", fontsize=10, color=INK_PRIMARY)
    ax.set_yticks(y)
    ax.set_yticklabels(order, fontsize=10, color=INK_SECONDARY)
    ax.invert_yaxis()
    ax.set_xlim(0, stats.rate.max() * 100 * 1.35)
    ax.set_xlabel("Share of invoices disputed")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    style_axes(ax)
    ax.set_title("Customers dispute the errors they can see", loc="left", fontsize=13, pad=12)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "dispute_rate_by_billing_accuracy.png", dpi=150)
    plt.close(fig)


def plot_dso(ar):
    ar = ar.sort_values("dso_days")
    fig, ax = plt.subplots(figsize=(8, 3.2))
    y = np.arange(len(ar))
    ax.barh(y, ar.dso_days, color=BLUE, height=0.55)
    for yi, (dso, pd_pct) in enumerate(zip(ar.dso_days, ar.pct_past_due)):
        ax.text(dso + 1, yi, f"{dso:.0f} days  ·  {pd_pct:.0f}% of open AR past due", va="center", fontsize=10)
    ax.set_yticks(y)
    ax.set_yticklabels(ar.channel, fontsize=10, color=INK_SECONDARY)
    ax.set_xlim(0, ar.dso_days.max() * 1.6)
    ax.set_xlabel("DSO (open AR ÷ trailing-91-day billings × 91)")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    style_axes(ax)
    ax.set_title("Reseller channel carries the longest cash cycle", loc="left", fontsize=13, pad=12)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "dso_by_channel.png", dpi=150)
    plt.close(fig)


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    accounts, usage, lines, invoices = load()
    expected = expected_billing(accounts, usage)
    df = find_exceptions(expected, lines, invoices)

    exc = df[df.exception != ""].copy()
    worklist = exc.assign(abs_variance=exc.variance.abs()).sort_values("abs_variance", ascending=False)[
        ["invoice_id", "account_id", "channel", "service_month", "exception", "amount", "expected_amount", "variance", "action", "status", "ever_disputed"]]
    worklist.rename(columns={"amount": "billed_amount"}).to_csv(DATA_DIR / "billing_exceptions.csv", index=False, date_format="%Y-%m-%d")

    summary = exc.assign(abs_variance=exc.variance.abs()).pivot_table(
        index="service_month", columns="exception", values="abs_variance", aggfunc="sum").fillna(0.0)
    summary.to_csv(DATA_DIR / "exception_summary_by_month.csv", date_format="%Y-%m-%d")

    ar = ar_by_channel(df)
    ar.to_csv(DATA_DIR / "ar_by_channel.csv", index=False)
    controls = control_tests(df)
    controls.to_csv(DATA_DIR / "control_tests.csv", index=False)

    plot_exceptions_by_month(summary)
    plot_dispute_rate(df)
    plot_dso(ar)

    # --- console summary used in the README ---
    under = exc.loc[exc.variance < 0, "variance"].sum()
    over = exc.loc[exc.variance > 0, "variance"].sum()
    total_billed = df.amount.sum()
    pre = exc[exc.service_month < PRICE_CHANGE]
    post = exc[exc.service_month >= PRICE_CHANGE]
    n_pre = (df.service_month < PRICE_CHANGE).sum()
    n_post = (df.service_month >= PRICE_CHANGE).sum()
    print(f"Invoices audited: {len(df):,}   billed: ${total_billed/1e6:,.1f}M")
    print(f"Exceptions: {len(exc):,} ({len(exc)/len(df)*100:.1f}%)")
    print(f"  under-billed (revenue leakage): ${-under:,.0f}")
    print(f"  over-billed  (credit exposure): ${over:,.0f}")
    print(f"  exception rate pre-change: {len(pre)/n_pre*100:.1f}%   post-change: {len(post)/n_post*100:.1f}%")
    print(exc.groupby("exception").variance.agg(["count", "sum"]).round(0))
    vis = df.exception.isin(CUSTOMER_VISIBLE)
    silent = (df.exception != "") & ~vis
    clean = df.exception == ""
    for name, mask in [("clean", clean), ("silent", silent), ("visible", vis)]:
        print(f"  dispute rate {name}: {df.loc[mask, 'ever_disputed'].mean()*100:.1f}%  (n={mask.sum()})")
    print(ar.to_string(index=False))
    print(controls.to_string(index=False))


if __name__ == "__main__":
    main()
