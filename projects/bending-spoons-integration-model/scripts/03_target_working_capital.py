"""
Pre-acquisition working-capital profile of the US-listed companies Bending
Spoons bought (Vimeo, Eventbrite, Brightcove), from their 10-K XBRL facts.

For each fiscal year-end: revenue, AR (net), allowance, deferred revenue,
DSO, deferred-revenue days, and the customer cash cushion
(deferred revenue minus AR, in days of revenue). Eventbrite also gets
creator funds payable (ticket money owed to organizers).

Outputs: data/target_working_capital.csv
"""
from pathlib import Path
import json

import pandas as pd

HERE = Path(__file__).resolve().parent
RAW = HERE.parent / "raw"
DATA = HERE.parent / "data"

TARGETS = {
    "VMEO": "Vimeo",
    "EB": "Eventbrite",
    "BCOV": "Brightcove",
}
REVENUE_TAGS = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
                "RevenueFromContractWithCustomerIncludingAssessedTax"]
AR_TAGS = ["AccountsReceivableNetCurrent"]
ALLOW_TAGS = ["AllowanceForDoubtfulAccountsReceivableCurrent", "AllowanceForDoubtfulAccountsReceivable"]
DEFREV_TAGS = [["ContractWithCustomerLiabilityCurrent", "ContractWithCustomerLiabilityNoncurrent"],
               ["DeferredRevenueCurrent", "DeferredRevenueNoncurrent"],
               ["ContractWithCustomerLiability"]]
CREATOR_TAGS = ["AccountsPayableUnderwritersPromotersAndEmployeesOtherThanSalariesAndWagesCurrent"]


def annual(facts, tag, duration):
    """Values from 10-K filings keyed by period end; latest filing wins (restatements)."""
    if tag not in facts:
        return {}
    out = {}
    for u in facts[tag]["units"].get("USD", []):
        if not u.get("form", "").startswith("10-K"):
            continue
        if duration:
            if "start" not in u:
                continue
            days = (pd.Timestamp(u["end"]) - pd.Timestamp(u["start"])).days
            if not 350 <= days <= 380:
                continue
        prev = out.get(u["end"])
        if prev is None or u["filed"] > prev[1]:
            out[u["end"]] = (u["val"], u["filed"])
    return {k: v[0] for k, v in out.items()}


def first(facts, tags, duration):
    for t in tags:
        v = annual(facts, t, duration)
        if v:
            return v
    return {}


def main():
    rows = []
    for ticker, name in TARGETS.items():
        facts = json.loads((RAW / f"{ticker}_companyfacts.json").read_text(encoding="utf-8"))["facts"]["us-gaap"]
        rev = first(facts, REVENUE_TAGS, True)
        ar = first(facts, AR_TAGS, False)
        allow = first(facts, ALLOW_TAGS, False)
        creators = first(facts, CREATOR_TAGS, False)
        defrev = {}
        for group in DEFREV_TAGS:
            parts = [annual(facts, t, False) for t in group]
            if parts[0]:
                for end in parts[0]:
                    defrev[end] = sum(p.get(end, 0) for p in parts)
                break
        for end in sorted(set(rev) & set(ar)):
            r = rev[end]
            row = {
                "company": name,
                "fiscal_year_end": end,
                "revenue_musd": r / 1e6,
                "ar_net_musd": ar[end] / 1e6,
                "allowance_musd": allow.get(end, float("nan")) / 1e6,
                "deferred_revenue_musd": defrev.get(end, float("nan")) / 1e6,
                "creator_funds_payable_musd": creators.get(end, float("nan")) / 1e6,
            }
            row["dso_days"] = row["ar_net_musd"] / row["revenue_musd"] * 365
            row["deferred_rev_days"] = row["deferred_revenue_musd"] / row["revenue_musd"] * 365
            row["cushion_days"] = row["deferred_rev_days"] - row["dso_days"]
            row["allowance_pct_gross_ar"] = row["allowance_musd"] / (row["ar_net_musd"] + row["allowance_musd"])
            rows.append(row)
    df = pd.DataFrame(rows).round(2)
    DATA.mkdir(exist_ok=True)
    df.to_csv(DATA / "target_working_capital.csv", index=False)
    pd.set_option("display.width", 200)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
