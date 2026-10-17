# Bending Spoons: Acquisition-Integration Model

Bending Spoons (Nasdaq: BSP) grows by buying software companies and
rebuilding them. In 2026 alone it closed Tractive and Airtable and signed
Miro. Organic growth was 3% in Q2 2026 while headline revenue grew 126%,
so the acquisition engine *is* the business. That makes one finance
question unusually important:

**How much does integration speed matter to Bending Spoons' economics, and
what should finance own in each integration?**

This project answers it outside-in, from public sources only, as a working
Excel model plus the integration scorecard and 12-month look-back I'd run on
every deal.

> **On the data:** everything comes from Bending Spoons' Q2 2026 earnings
> release, its deal press releases, SEC EDGAR XBRL filings for the
> previously-listed targets, and two clearly labeled secondary summaries of
> the IPO prospectus. No non-public information about any company appears
> here, and nothing here is investment advice.

## Findings

**1. Leverage stays under the covenant even with zero credit for the new deals.**
Walking net debt from $4.09B (Jun 30, 2026) through the $1.1B IPO
proceeds, ~$300M of retained H2 cash flow, Airtable ($1.29B EV, all cash)
and Miro ($1.355B EV less $295M seller rollover) gives about **$5.04B of
pro forma net debt and ~2.96x leverage** against a 4.0x covenant, without
crediting a dollar of Airtable or Miro EBITDA.

**2. Documented savings are acquisition capacity.** Reported leverage uses
pro forma EBITDA that includes achieved *and certain expected* cost savings.
At a 4.0x limit, **each $100M of savings that finance can evidence adds
roughly $400M of room for the next deal.** Savings documentation is part of
the deal engine, not bookkeeping.

| Airtable + Miro EBITDA credited | Pro forma leverage | Debt capacity to 4.0x |
|---|---|---|
| $0 | 2.96x | $1.78B |
| $200M | 2.65x | $2.58B |
| $400M | 2.40x | $3.38B |

**3. Miro pays back at ~5.5x run-rate operating income in the base case,
and each month of delay costs about $29M.** Base case: 92% revenue retained
after repricing (in line with BSP's reported 91–95% group NRR), 45%
post-integration margin (group adjusted operating margin was 54% in Q2).
That's ~$248M of run-rate operating income on a $1.355B price, an 18% pre-tax
yield. Interest on the incremental debt (~$100M/yr at the cited 9.43%) runs
from day one. A month of delay forgoes ~$20.7M of operating income and
carries ~$8.3M of interest.

| Margin \ Revenue retained | 85% | 92% | 100% |
|---|---|---|---|
| 35% | 7.6x | 7.0x | 6.5x |
| 45% | 5.9x | **5.5x** | 5.0x |
| 55% | 4.8x | 4.5x | 4.1x |

Retention, not margin, is the variable to watch. Brightcove's revenue fell
after its acquisition, according to secondary sources (it no longer files, so
this isn't verifiable from EDGAR). Treat the 92% base case as an assumption to test.

**4. Collections have kept pace so far, but the revenue mix is getting harder.**
AR grew 93% between Dec 2025 and Jun 2026 while quarterly revenue grew 91%,
so DSO held at ~36 days. But advertising (AOL) and invoiced B2B (Vimeo,
Airtable, Miro) carry credit and collection risk that app-store revenue
doesn't. The previously-listed targets also show three different working-capital
shapes that an integration has to handle differently:

| Target (last 10-K) | DSO | Deferred revenue, days | What it means at integration |
|---|---|---|---|
| Vimeo (FY2024) | ~22 | ~142 | Customers pre-fund the business. Repricing that triggers churn unwinds that cushion in cash. |
| Brightcove (FY2023) | ~61 | ~124 | Real invoiced AR. The aging, credit memos and reserve need review in days 1–30. |
| Eventbrite (FY2025) | <1 | n/a | ~$278M of creator funds payable is money owed to organizers. It is not free cash. |

## What finance should own in each integration

The `Scorecard` tab is a one-page template per acquisition. The Miro example
sets targets I'd propose:

- **Day 30:** cash control. Payouts repointed to the group's payment
  infrastructure, target bank accounts swept.
- **Day 60:** first consolidated close on the group chart of accounts.
  The prospectus discloses a material weakness that covers integrating
  acquired companies, so this date carries extra weight.
- **Same day as each exit:** access removed. Segregation of duties breaks
  first in a deep reorganization.
- **Ongoing:** run-rate savings vs. plan, reorganization spend reconciled
  to cost centers (add-backs have to survive audit), NRR vs. pre-deal, and
  a sunset list of every legacy system, entity and reporting pack. Each one
  kept is another control to test.

The `Lookback` tab compares underwritten and actual results 12 months after
close. Those variances become the starting assumptions for the next deal.

## How the model is built

`data/bending_spoons_integration_model.xlsx` follows standard modeling
conventions. Every hardcoded number sits on the `Inputs` tab with its
source. Blue = sourced input, black = formula, green = cross-tab link,
yellow = my assumption (change it and everything recalculates).

| Tab | What it does |
|---|---|
| Inputs | Every sourced figure and assumption |
| Leverage | Net-debt walk to pro forma YE2026 vs. covenant; savings sensitivity |
| Miro_Payback | Price / run-rate operating income grid; cost of delay |
| Working_Capital | Group DSO check, Dec 2025 vs. Jun 2026 |
| Scorecard | Per-deal integration scorecard and sunset list |
| Lookback | 12-month underwritten vs. actual |
| Sources | Links to every document used |

```
scripts/01_build_model.py             # builds the workbook (openpyxl, formulas only off Inputs)
scripts/02_fetch_sec_data.py          # caches EDGAR XBRL facts to raw/ (gitignored)
scripts/03_target_working_capital.py  # -> data/target_working_capital.csv
```

## Caveats

- Covenant level (4.0x) and debt cost (9.43%) come from a secondary summary
  of the prospectus, not the filing. Verify them before relying on them.
- TTM EBITDA is implied from net debt / reported 2.4x, so it carries about
  ±2% rounding error and is held flat (conservative).
- Airtable and Miro EBITDA aren't disclosed. The base case credits zero.
- Excludes Tractive's $115M deferred consideration (May 2027) and deal fees.

*Prepared by Jeff King, Oct 2026. Public sources as of Oct 12, 2026.*
