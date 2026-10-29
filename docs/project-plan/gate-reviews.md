# Gate reviews

Evidence recorded by the builder. A gate is **passed** only after project-owner review; none has been signed off yet.

## Evidence collected on 29 October 2026 (local Windows 11 machine, Python 3.12.10)

| Gate | Pass condition (literal) | Evidence | Outstanding |
|---|---|---|---|
| 1 | Reviewed PRD/wireframes; runnable navigation; build WBS, Gantt, risk register | `docs/prd.md`, `docs/input-schema.md`, `docs/wireframes/`, app navigation runs, `docs/project-plan/*.csv` | Owner review; discovery interviews and competitor comparison |
| 2 | Cent-accurate fixture; tests pass; Scenario A budget works | `tests/test_budget.py` (−$52.00 / $156.80 / $365.60; 29 registrations; $14.95); Scenario A budget renders | Owner review |
| 3 | Three scenarios render; event-date rescheduling; permit/rain tasks correct | `tests/test_schedule.py`; UI test renders Gantt for all demos | Owner review |
| 4 | Deterministic limit; seed reproducibility; understandable explainer | `tests/test_simulation.py`; in-app "How to read this" | Owner/tester judgment of "understandable" |
| 5 | Scenario C across working modules; staffing changes propagate automatically | `test_staffing_change_updates_budget_and_simulation`; all tabs built | Owner review |
| 6 | Two unaided sub-20-minute plans; XLSX compatibility; five top issues fixed | Workbook validated with openpyxl; one-page PDF inspected visually | **User tests not done**; Excel and Google Sheets manual checks not done |
| 7 | Live URL, public repo, demo, case study, owner sign-off | `docs/deployment.md` | **Not deployed** (owner action); video and case study not done |

Test run: `85 passed` (pytest 9.2.0). Simulation timing (local, not deployed): 0.01–0.04 s for 10,000 runs per demo.
