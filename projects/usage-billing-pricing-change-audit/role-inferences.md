# What the Job Description Implies: Reading a Senior Manager, O2C Posting

A job description is a public document, and it tells you a lot about what
the team is dealing with right now. Below, each phrase from Relativity's
public **Senior Manager, Order-to-Cash** posting is paired with a
reasonable inference, my confidence in it, and the question I'd ask to
check it.

> These are **inferences, not facts**. They come only from the public
> posting and public company announcements. They are hypotheses to test in
> conversation, not claims about how the company operates internally.

| # | What the posting says | Reasonable inference | Confidence | Question to verify |
|---|---|---|---|---|
| 1 | Billing across **"multi-currency and multi-entity environments"** | Invoices go out from several legal entities in several currencies. The work includes FX at invoice date, intercompany, local tax/VAT, and a growing list of country e-invoicing mandates. | High | How many billing entities and currencies are there, and are any countries on e-invoicing mandates today? |
| 2 | Billing operations **"across all revenue streams"** | There is more than one billing model: usage/per-GB cloud (RelativityOne), likely legacy on-premises licenses and maintenance, separately priced AI products (aiR for Case Strategy is priced separately), partner/reseller billing, and probably services and events. | Medium–High | Which revenue streams does billing own end to end, and which are the hardest to bill? |
| 3 | **Hands-on** Zuora Billing proficiency required; working knowledge of Salesforce | Zuora is the system of record for subscriptions, usage and bill runs, fed by Salesforce orders. "Hands-on" suggests the team configures the product catalog and runs bill runs itself instead of relying on a systems team. | Medium | Is the Salesforce→Zuora order flow automated, or re-keyed? Who owns Zuora configuration? |
| 4 | Use **AI and automation "to minimize manual intervention"** | There is meaningful manual work today, likely usage uploads, invoice adjustments, pre-bill review, and custom invoice formats for law firms and corporate legal e-billing portals. | High | Where does the team spend the most manual hours each close? |
| 5 | **Manage the SOX control framework** for billing; point of contact for audits; **public-company SOX** experience required | The company is building or hardening billing controls for public-company scrutiny, which fits the confidential S-1 filed in March 2026. Controls that were "reviewed" may now need documented, repeatable evidence. | High | Are billing controls already documented and tested, or is this role building the framework? Who is the external auditor's main contact today? |
| 6 | Partner with **Revenue Accounting, Legal, and Deal Strategy** so contract terms and pricing **"translate accurately"** into systems | Non-standard deal terms (commits, true-ups, caps, bundled AI, partner pricing) sometimes don't make it cleanly from contract to invoice. Usage-based and bundled pricing also creates ASC 606 variable-consideration questions. | High | How often do non-standard terms reach billing, and how are they flagged today? |
| 7 | Make sure **new products and billing models are operationally supportable before launch** | Pricing changes often. AI review tools became part of standard RelativityOne pricing in 2026 while other AI products are priced separately. O2C either now has a seat at launch readiness or needs one. | Medium–High | Is billing part of the product-launch checklist today? How did the 2026 AI pricing change go operationally? |
| 8 | Ensure **"completeness, accuracy, and scalability"** of billing | "Completeness" is the telling word: the risk isn't only wrong invoices but **unbilled usage** (revenue leakage). Scalability means volume is growing faster than headcount. | Medium | Is there a reconciliation today from platform usage to invoiced usage? |
| 9 | **Lead and mentor a global billing team**; 10+ years' experience, 3+ managing people | The team is spread across time zones, and coverage across regions and bill-run timing are part of the job. The level (Senior Manager, not Director) suggests the role reports to a Controller or O2C/Revenue Operations leader. | Medium | How big is the team, where is it, and who does the role report to? |
| 10 | The O2C organization spans **account setup → invoicing → collections → reporting**, but the role's duties center on **billing** | Collections and cash application may sit with a peer team. Billing accuracy upstream still directly drives disputes and DSO downstream. | Medium | Do collections and cash application report to this role or to a peer? How are disputes routed back to billing? |

## What this adds up to

The role appears to be about **three things happening at once**:

1. **IPO readiness.** SOX-grade controls and audit evidence for billing
   (rows 5 and 8)
2. **Pricing-model change.** Bundled AI, separately priced AI, usage and
   partner billing all running at once (rows 2, 6 and 7)
3. **Scale without headcount.** Automating a global, multi-entity process
   on Zuora + Salesforce (rows 1, 3, 4 and 9)

That's the lens for the analysis in this project. The public-filing peer
comparison asks what comparable companies' numbers (DSO, unbilled
receivables, deferred revenue mix, credit-loss reserves) say about the size
of each of these challenges.

## Sources

- Relativity, *Senior Manager, Order-to-Cash* job posting (public, 2026)
- [Relativity: confidential submission of draft S-1 (Mar 2026)](https://www.relativity.com/news-events/press-release-relativity-announces-confidential-submission-of-draft-registration-statement-for-proposed-initial-public-offering/)
- [Relativity Fest 2025: generative AI review included in standard RelativityOne pricing](https://www.prnewswire.com/news-releases/relativity-fest-2025-relativity-announces-generative-ai-solutions-for-legal-review-to-be-standard-in-cloud-offering-302578299.html)
- [Relativity partner program: Distributor and Provider partners](https://www.relativity.com/partners/program-roles-and-benefits/)
