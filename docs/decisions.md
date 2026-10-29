# Decision log

Status key: **Proposed default (implemented)** means the guide's proposed decision was implemented and is awaiting project-owner approval. None of these decisions has been approved by the project owner yet.

| # | Topic | Decision implemented | Status | Where |
|---|---|---|---|---|
| D01 | Attendance terminology | Low/likely/high are **registrations before no-shows**. Expected on-site attendance = registrations × (1 − no-show rate) and is shown separately everywhere. | Proposed default (implemented) | `budget.py`, Budget and Break-even pages |
| D02 | Revenue and no-shows | Default `billing_basis = attended`: only attendees generate ticket revenue (the brief's model). A tier may be set to `registered` (prepaid): no-shows still pay but do not incur variable cost. Forecasting only; no payment processing. | Proposed default (implemented) | `budget.evaluate` |
| D03 | Free places | Two mechanisms: weighted free tiers (price 0, a share of registrations) and fixed free quotas (`allocation = free_quota`), filled first. If registrations are below the quota, they are split across quota tiers in proportion to their quotas. The quota is a simplified reservation, not observed sales; the UI says so. | Proposed default (implemented) | `budget.evaluate` |
| D04 | Fair revenue | Free entry, class passes and vendor fees are modeled separately: a free weighted tier plus `additional_revenue` rows (per-attendee passes; fixed, prepaid vendor fees). | Proposed default (implemented) | Scenario C |
| D05 | Hybrid weather | `hybrid` uses a **whole-event** cancellation approximation (default 20%, illustrative), clearly labeled in the UI, workbook and explainer. Partial-session cancellation is deferred. | Proposed default (implemented) | `simulation.py`, `docs/later.md` |
| D06 | Unspecified defaults | Every invented value is labeled `illustrative` in provenance. No default is presented as a researched Chicago rate. | Proposed default (implemented) | `schema.py`, demos, Assumptions sheet |
| D07 | Deposit | `rental_total` is the expense (including any advance). `rental_advance` is a cash-timing note only. `security_deposit` is refundable cash, not an expense, unless `security_deposit_forfeit_fraction` > 0, in which case that share is a ledger expense. | Proposed default (implemented) | `budget.build_ledger` |
| D08 | Beta distribution | No-show rates use a scaled beta with an explicit concentration parameter (default 6): α = z·k, β = (1−z)·k, z = (mean − low)/(high − low). This is a model-shape assumption, not a fit. Endpoint means with non-zero ranges are rejected. | Proposed default (implemented) | `simulation.py`, `validation.py` |
| D09 | Triangular distribution | Stored as low/mode/high; the mean (low+mode+high)/3 is calculated and displayed. Mean entry is not offered in MVP. | Proposed default (implemented) | Costs inputs |
| D10 | Dashboard budget comparison | Compares the optional organizer spending limit with projected total cost (fixed + variable) at likely registrations. No actual-expenditure tracking. A missing limit shows "not supplied". | Proposed default (implemented) | `dashboard.py` |
| D11 | Session lifetime | Session memory only, plus an explicit **Clear plan** action. The privacy text does not promise instant deletion when a tab closes; disconnection cleanup is framework-managed. | Proposed default (implemented) | `state.py`, About page |
| D12 | Calendar | Calendar days in the event's timezone (default `America/Chicago`); `tzdata` is pinned so this works on Windows. | Proposed default (implemented) | `schedule.py`, `dashboard.py` |
| D13 | Total cost definition | Total cost = fixed + variable. Processing fees are deducted from revenue and reported separately (matches the guide's fixture table). | Implementation choice | Budget page |
| D14 | Variable-cost aggregation | Variable rows are summed into one triangular distribution (shared movement, disclosed). Cancellation retention is a mean-weighted average of row retentions. | Guide rule + implementation detail | `budget.build_model` |
| D15 | Staffing peak | Coverage uses the high registration estimate unless the organizer supplies `attendance.planned_peak`. Staff counts are committed costs in every trial. | Guide rule | `staffing.py` |
| D16 | Break-even search | Integer registrations 0…capacity are evaluated with the shared evaluator; on-site attendance needed comes from linear interpolation of the continuous crossing, rounded up. Net equal to zero (within 1e-9 USD) counts as breaking even. | Guide rule + implementation detail | `budget.calculate_break_even` |
| D17 | Break-even price target | One common price for paid tiers (price > 0); if there are no paid tiers, the first per-attendee additional revenue line (Scenario C: class pass) becomes the target. | Guide rule | `budget.calculate_break_even` |
| D18 | Tornado baseline | Baseline = likely registrations, mean rates/costs; the expected net combines ordinary and cancelled outcomes at the baseline weather probability. The weather row swings probability 0→1 and is labeled separately. | Proposed extension (guide) | `simulation.tornado_rows` |
| D19 | Marketing reminders | Weekly reminders every 7 days after registration opens (−28) and before the final 48-hour reminder (−2): −21, −14, −7. Rows are deduplicated by activity/channel/date. Activities before the earliest start are flagged; compression to the earliest start date is an explicit action. | Guide rule | `marketing.py` |
| D20 | Imported marketing activities | An imported Marketing sheet replaces the generated activity list; an empty Marketing sheet keeps the generated schedule. | Implementation choice | `imports.py` |
| D21 | Event-day dependencies | Finish-to-start rules are not enforced between two event-day tasks (same-day sequencing is below calendar-day resolution). | Implementation choice | `schedule.py` |
| D22 | Gate 5 benchmark | The literal Gate 5 benchmark ("every tab") is preserved. All tabs were built before this gate record; no benchmark change was proposed. | Preserved | `docs/project-plan/gate-reviews.md` |
| D23 | Stretch scope | No stretch features (multi-week series, ICS export, pricing optimization, Spanish) were implemented. | Brief / guide | `docs/later.md` |
| D24 | Hosting telemetry | Community Cloud forces `gatherUsageStats = true`. The repository sets it to false and documents the platform behavior; the owner must accept and disclose this or self-host. | **Owner decision required** | `docs/deployment.md` |
| D25 | Startup IP lookup | Streamlit looks up the server's public IP (`checkip.amazonaws.com`) when running headless without an address. `browser.serverAddress = "localhost"` is set to prevent it. | Implementation choice | `.streamlit/config.toml` |

## Decisions still needed from the project owner

1. Approve or change D01–D05 (attendance terminology, prepaid billing, free places, fair revenue, hybrid weather).
2. Approve refund and retained-cost defaults (ticket refunds 100%, fee refunds 0%, fixed costs 100% retained, variable costs 0%).
3. Replace or approve every illustrative demo amount (see `docs/assumptions.md`).
4. Rebaseline gate dates (the original window ends 20 November 2026) and decide on D24.
