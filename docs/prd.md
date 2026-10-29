# Product requirements (D1 summary)

Source: `WellnessPop_Project_Brief_Lindah.pdf` (via `WELLNESSPOP_IMPLEMENTATION_GUIDE.md`, audited 29 October 2026).

## Problem and users

Independent instructors, small wellness collectives, community organizations and nonprofit program staff need to estimate costs, plan backward from an event date, allocate staff, schedule marketing, and explain the risk of losing money, without paid tools or spreadsheets they have to build themselves.

## MVP scope

Single class or one-day fair; ten outputs; three demos; CSV/XLSX import; ≥10,000 simulation runs with an exposed seed; editable planning tables; responsive UI; documented assumptions; no accounts or database. Success measure from the brief: two practitioners complete a plan unaided in under 20 minutes.

**Excluded:** ticket sales and payments, Eventbrite/Square/Stripe integration, email/SMS, scraping, external data APIs, saved sessions, native apps, critical-path analysis. **Stretch (not built):** multi-week series, ICS export, pricing optimization, Spanish translation.

## Requirements traceability

| ID | Capability | Implementation | Evidence (tests) |
|---|---|---|---|
| R01 | Budget with tiers and low/likely/high | `budget.py` | `test_budget.py` hand fixture to the cent |
| R02 | Editable three-phase WBS | `schedule.py`, `templates/wbs_templates.json` | `test_schedule.py` conditional tasks, add/delete, tombstones |
| R03 | Backward Gantt with today marker | `schedule.py`, `ui/charts.py` | event-date rescheduling, permit lead time, pinned conflicts |
| R04 | Break-even attendance and price | `budget.calculate_break_even` | finite, impossible, zero-cost, all-free, 100% no-show/fees |
| R05 | Probability, P10/P50/P90, histogram, tornado | `simulation.py` | seed reproducibility, deterministic limit, cancellation branches, <5 s |
| R06 | Risk register | `risk.py` | conditions, bands, sorting, edits don't alter model |
| R07 | Staffing and budget linkage | `staffing.py` | costs, ceiling coverage, credentials, budget and simulation update |
| R08 | Marketing schedule and CSV | `marketing.py`, `export.py` | offsets, reminders, early-bird condition, compression, CSV |
| R09 | One-screen dashboard | `dashboard.py` | seven KPIs; stale simulation shown as out of date |
| R10 | Eight-sheet XLSX and one-page PDF | `export.py` | sheet names, reconciliation, injection, one page per demo |
| R11 | Validated forms and imports | `validation.py`, `imports.py` | invalid values, formulas, macros, size limits, atomic failure |
| R12 | Three demos | `data/demo/` | every demo generates every output (unit and UI tests) |
| R13 | Session-only data, no product API calls | `state.py`, config | isolated sessions, clear plan, static no-I/O check |
| R14 | Docs, deployment, portfolio | `docs/`, README | Deployment and portfolio items are owner tasks (not done) |

Full field contract: [input-schema.md](input-schema.md). Model decisions: [decisions.md](decisions.md).
