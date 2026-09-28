"""
Generate a synthetic order-to-cash dataset for a usage-priced legal-data
SaaS company that changes its price book mid-stream.

The fictional company ("the vendor") sells a cloud platform priced per GB of
data hosted per month, with an annual committed volume and overage above the
commit. Customers buy either directly (corporate legal departments, law
firms) or through reseller partners who re-bill their own end clients.

On 2025-11-01 the vendor changes its price book:
  - v1 (legacy): hosting $/GB-month + a separately metered per-document
    AI-review add-on
  - v2 (bundled): a higher all-in $/GB-month rate, AI review included
Existing contracts move to v2 at their next renewal, NOT on the calendar
date - so for ~12 months the billing system has to rate two price books at
once, account by account.

The "billing system" in this simulation makes the kinds of mistakes that
show up during a transition like that (stale rates, AI lines billed after
the bundle, v2 applied before renewal, overage missed). Those error flags
are simulation-only and are dropped before the data is written, the same way
a real billing export doesn't tell you which of its invoices are wrong.

This data is 100% synthetic. The vendor, customers, partners, rates and
volumes are invented and illustrative; nothing here represents any real
company's pricing, customers, or employer data.

Usage:
    python 01_generate_synthetic_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(seed=7)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

START = pd.Timestamp("2024-09-01")
AS_OF = pd.Timestamp("2026-08-31")
MONTHS = pd.date_range(START, "2026-08-01", freq="MS")
PRICE_CHANGE = pd.Timestamp("2025-11-01")

# Illustrative price book - invented numbers, not any vendor's list price.
V1_HOSTING_RATE = 12.00   # $/GB-month
V1_AI_RATE = 0.08         # $/document reviewed by AI
V2_HOSTING_RATE = 15.00   # $/GB-month, AI included

CHANNELS = ["Direct - Corporate", "Direct - Law Firm", "Partner (Reseller)"]
CHANNEL_WEIGHTS = [0.30, 0.35, 0.35]
TERMS = {"Direct - Corporate": 45, "Direct - Law Firm": 30, "Partner (Reseller)": 60}
# typical committed GB by channel (partners aggregate many end clients)
COMMIT_GB = {"Direct - Corporate": (400, 3_000), "Direct - Law Firm": (150, 1_200), "Partner (Reseller)": (1_500, 12_000)}

N_ACCOUNTS = 120


def make_accounts(n):
    rows = []
    for i in range(n):
        channel = RNG.choice(CHANNELS, p=CHANNEL_WEIGHTS)
        # contract anniversary month drives when the account migrates to v2
        anniversary_month = int(RNG.integers(1, 13))
        commit_gb = int(RNG.integers(*COMMIT_GB[channel]) // 50 * 50)
        v2_effective = next(m for m in pd.date_range(PRICE_CHANGE, periods=12, freq="MS") if m.month == anniversary_month)
        rows.append({
            "account_id": f"A{i+1:04d}",
            "channel": channel,
            "payment_terms_days": TERMS[channel],
            "contract_anniversary_month": anniversary_month,
            "committed_gb_per_month": commit_gb,
            "v2_effective_month": v2_effective.date().isoformat(),
            # latent simulation-only traits
            "_volatility": float(RNG.uniform(0.10, 0.55)) * (1.3 if channel != "Direct - Corporate" else 1.0),
            "_payment_discipline": float(np.clip(RNG.normal(0.6 if channel == "Direct - Corporate" else 0.5, 0.2), 0.05, 0.95)),
        })
    return pd.DataFrame(rows)


def make_usage(accounts):
    """Monthly hosted GB is lumpy: matters arrive, spike, and roll off."""
    rows = []
    for _, a in accounts.iterrows():
        level = a.committed_gb_per_month * RNG.uniform(0.75, 1.15)
        for m in MONTHS:
            # random-walk baseline + occasional big-matter spikes
            level *= float(np.exp(RNG.normal(0.01, a._volatility / 3)))
            spike = 1.0 + (RNG.uniform(0.4, 1.5) if RNG.random() < 0.08 else 0.0)
            gb = max(10.0, level * spike)
            ai_docs = int(gb * RNG.uniform(25, 90) * (1.0 if m >= pd.Timestamp("2025-03-01") else 0.4))
            rows.append({"account_id": a.account_id, "month": m.date().isoformat(), "gb_hosted": round(gb, 1), "ai_docs_reviewed": ai_docs})
    return pd.DataFrame(rows)


def rate_and_bill(accounts, usage):
    """Build billed invoice lines, injecting realistic transition errors."""
    acct = accounts.set_index("account_id")
    lines, headers = [], []
    seq = 1
    for _, u in usage.iterrows():
        a = acct.loc[u.account_id]
        m = pd.Timestamp(u.month)
        v2_eff = pd.Timestamp(a.v2_effective_month)
        on_v2 = m >= v2_eff
        months_since_migration = (m.year - v2_eff.year) * 12 + (m.month - v2_eff.month)
        is_partner = a.channel == "Partner (Reseller)"

        rate = V2_HOSTING_RATE if on_v2 else V1_HOSTING_RATE
        bill_ai = not on_v2
        bill_overage = True
        error = ""

        # --- injected billing-system errors (simulation-only flag) ---
        r = RNG.random()
        if on_v2 and 0 <= months_since_migration <= 2 and r < 0.22:
            error = "Stale v1 rate after renewal"       # under-bill
            rate = V1_HOSTING_RATE
        elif on_v2 and 0 <= months_since_migration <= 3 and r < 0.40:
            error = "AI add-on billed after bundle"     # over-bill
            bill_ai = True
        elif (not on_v2) and m >= PRICE_CHANGE and r < 0.07:
            error = "v2 rate applied before renewal"    # over-bill vs contract
            rate, bill_ai = V2_HOSTING_RATE, False
        elif r > 1 - (0.08 if is_partner else 0.03):
            error = "Overage not billed"                # under-bill
            bill_overage = False

        invoice_id = f"INV{seq:06d}"
        seq += 1
        commit = a.committed_gb_per_month
        overage_gb = max(0.0, u.gb_hosted - commit)
        inv_lines = [("Committed hosting", commit, rate)]
        if overage_gb > 0 and bill_overage:
            inv_lines.append(("Hosting overage", round(overage_gb, 1), rate))
        if bill_ai and u.ai_docs_reviewed > 0:
            inv_lines.append(("AI review add-on", u.ai_docs_reviewed, V1_AI_RATE))
        total = 0.0
        for line_type, qty, unit_rate in inv_lines:
            amt = round(qty * unit_rate, 2)
            total += amt
            lines.append({"invoice_id": invoice_id, "account_id": u.account_id, "service_month": u.month,
                          "line_type": line_type, "quantity": qty, "unit_rate": unit_rate, "amount": amt})

        # invoice issued ~5 days after month end (usage close)
        issue = m + pd.offsets.MonthEnd(0) + pd.Timedelta(days=int(RNG.integers(3, 9)))
        due = issue + pd.Timedelta(days=int(a.payment_terms_days))
        headers.append({"invoice_id": invoice_id, "account_id": u.account_id, "service_month": u.month,
                        "issue_date": issue, "due_date": due, "amount": round(total, 2), "_error": error,
                        "_has_overage": overage_gb > 0})
    return pd.DataFrame(lines), pd.DataFrame(headers)


def simulate_payments(accounts, headers):
    acct = accounts.set_index("account_id")
    over_bill = {"AI add-on billed after bundle", "v2 rate applied before renewal"}
    status, paid, disputed = [], [], []
    for _, h in headers.iterrows():
        a = acct.loc[h.account_id]
        d = a._payment_discipline
        # customers catch over-billing; variable (overage) invoices get more scrutiny;
        # partners wait on their own end-clients before paying
        p_dispute = 0.02 + (0.45 if h._error in over_bill else 0.0) + (0.04 if h._has_overage else 0.0)
        is_disputed = RNG.random() < p_dispute
        delay = RNG.normal((1 - d) * 35 - 8 + (12 if a.channel == "Partner (Reseller)" else 0), 12)
        if is_disputed:
            delay += RNG.uniform(30, 110)  # time to credit/rebill and re-approve
        pay_date = h.due_date + pd.Timedelta(days=round(float(delay)))
        if h.issue_date > AS_OF:
            continue
        if pay_date > AS_OF:
            status.append(("Disputed" if is_disputed else "Open", pd.NaT, is_disputed))
        else:
            status.append(("Paid", pay_date, is_disputed))
    headers = headers[headers.issue_date <= AS_OF].copy()
    headers["status"] = [s[0] for s in status]
    headers["payment_date"] = [s[1] for s in status]
    headers["ever_disputed"] = [s[2] for s in status]
    return headers


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    accounts = make_accounts(N_ACCOUNTS)
    usage = make_usage(accounts)
    lines, headers = rate_and_bill(accounts, usage)
    invoices = simulate_payments(accounts, headers)
    lines = lines[lines.invoice_id.isin(invoices.invoice_id)]

    # Drop simulation-only columns before "publishing" - a real billing export
    # doesn't come with an answer key.
    accounts.drop(columns=[c for c in accounts.columns if c.startswith("_")]).to_csv(DATA_DIR / "accounts.csv", index=False)
    usage.to_csv(DATA_DIR / "usage_monthly.csv", index=False)
    lines.to_csv(DATA_DIR / "invoice_lines.csv", index=False)
    for col in ["issue_date", "due_date", "payment_date"]:
        invoices[col] = pd.to_datetime(invoices[col]).dt.date
    invoices.drop(columns=["_error", "_has_overage"]).to_csv(DATA_DIR / "invoices.csv", index=False)

    print(f"{len(accounts)} accounts, {len(usage)} usage rows, {len(invoices)} invoices, {len(lines)} invoice lines")
    print("Injected errors (answer key, not saved):")
    print(invoices["_error"].replace("", "(clean)").value_counts())


if __name__ == "__main__":
    main()
