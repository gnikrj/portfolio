"""
Generate a synthetic order-to-cash dataset: customer accounts + invoices,
with realistic-but-fake payment behavior patterns (chronic-late payers,
segment-driven payment speed, seasonal volume, occasional disputes).

This data is 100% synthetic (Faker-generated names, randomly generated
amounts/dates/behaviors) — it does not represent any real company,
customer, or employer data.

Usage:
    python 01_generate_synthetic_data.py
"""
import numpy as np
import pandas as pd
from faker import Faker

RNG = np.random.default_rng(seed=42)
fake = Faker()
Faker.seed(42)

DATA_DIR = __import__("pathlib").Path(__file__).resolve().parent.parent / "data"

SEGMENTS = ["Enterprise", "Mid-Market", "SMB"]
SEGMENT_WEIGHTS = [0.15, 0.35, 0.50]
TERMS_BY_SEGMENT = {"Enterprise": 60, "Mid-Market": 45, "SMB": 30}
REGIONS = ["Northeast", "Southeast", "Midwest", "West", "International"]

N_CUSTOMERS = 160
ANALYSIS_END = pd.Timestamp("2026-06-30")
ANALYSIS_START = pd.Timestamp("2024-09-01")


def make_customers(n):
    rows = []
    for i in range(n):
        segment = RNG.choice(SEGMENTS, p=SEGMENT_WEIGHTS)
        # Each customer has a latent "payment discipline" score (0=always late, 1=always on time)
        # Enterprise/Mid-Market skew slightly better on average, with wide spread everywhere.
        base = {"Enterprise": 0.62, "Mid-Market": 0.55, "SMB": 0.48}[segment]
        discipline = float(np.clip(RNG.normal(base, 0.22), 0.02, 0.98))
        rows.append({
            "customer_id": f"C{i+1:04d}",
            "customer_name": fake.company(),
            "segment": segment,
            "region": RNG.choice(REGIONS),
            "payment_terms_days": TERMS_BY_SEGMENT[segment],
            "payment_discipline": round(discipline, 3),  # latent, not in "real" reporting - used to drive simulation
        })
    return pd.DataFrame(rows)


def make_invoices(customers: pd.DataFrame):
    rows = []
    invoice_seq = 1
    for _, cust in customers.iterrows():
        # number of invoices scales loosely with segment size
        n_invoices = {"Enterprise": RNG.integers(18, 40), "Mid-Market": RNG.integers(8, 22), "SMB": RNG.integers(2, 12)}[cust.segment]
        amount_range = {"Enterprise": (15_000, 180_000), "Mid-Market": (3_000, 40_000), "SMB": (300, 8_000)}[cust.segment]

        issue_dates = pd.to_datetime(
            RNG.integers(ANALYSIS_START.value // 10**9, (ANALYSIS_END - pd.Timedelta(days=30)).value // 10**9, n_invoices),
            unit="s",
        ).normalize()

        for issue_date in sorted(issue_dates):
            amount = round(float(RNG.uniform(*amount_range)), 2)
            due_date = issue_date + pd.Timedelta(days=int(cust.payment_terms_days))

            # simulate payment delay: on-time payers pay near due_date; low-discipline payers
            # pay progressively later, with a chance of disputes / write-offs.
            discipline = cust.payment_discipline
            delay_days = RNG.normal(loc=(1 - discipline) * 45 - 10, scale=15 + (1 - discipline) * 20)
            delay_days = float(delay_days)

            roll = RNG.random()
            if roll < 0.02 + (1 - discipline) * 0.04:
                status = "Written Off"
                payment_date = pd.NaT
            elif roll < 0.05 + (1 - discipline) * 0.08:
                status = "Disputed"
                payment_date = pd.NaT
            else:
                payment_date = due_date + pd.Timedelta(days=round(delay_days))
                if payment_date > ANALYSIS_END:
                    status = "Open"
                    payment_date = pd.NaT
                else:
                    status = "Paid"

            rows.append({
                "invoice_id": f"INV{invoice_seq:06d}",
                "customer_id": cust.customer_id,
                "issue_date": issue_date.date().isoformat(),
                "due_date": due_date.date().isoformat(),
                "amount": amount,
                "status": status,
                "payment_date": payment_date.date().isoformat() if pd.notna(payment_date) else "",
            })
            invoice_seq += 1
    return pd.DataFrame(rows)


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    customers = make_customers(N_CUSTOMERS)
    invoices = make_invoices(customers)

    # payment_discipline is a simulation-only latent variable; drop before "publishing"
    # the dataset, same as you wouldn't have it in a real AR system.
    customers_public = customers.drop(columns=["payment_discipline"])

    customers_public.to_csv(DATA_DIR / "customers.csv", index=False)
    invoices.to_csv(DATA_DIR / "invoices.csv", index=False)

    print(f"Generated {len(customers_public)} synthetic customers and {len(invoices)} synthetic invoices.")
    print(invoices["status"].value_counts())


if __name__ == "__main__":
    main()
