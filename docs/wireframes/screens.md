# Screen wireframes (implemented layout)

Text wireframes of every screen, including empty, invalid-input, stale-simulation and export states. Screenshots of the implemented Dashboard, Budget, Gantt, Simulation and Inputs pages for Scenario A are in `docs/screenshots/`.

```text
+-------------------+----------------------------------------------------------+
| WellnessPop       |  [flash: success / "Changes were not applied" + fields]  |
| ( ) Inputs        |  <Page title>                                            |
| ( ) Dashboard     |  <caption explaining the page in plain language>         |
| ( ) Budget        |  [metrics row]                                           |
| ( ) Break-even    |  [chart]                    (every chart has a table)    |
| ( ) Simulation    |  [table / editor]  [Apply button]                        |
| ( ) WBS / Gantt   |                                                          |
| ( ) Risks         |                                                          |
| ( ) Staffing      |                                                          |
| ( ) Marketing     |                                                          |
| ( ) Exports       |                                                          |
| ( ) About         |                                                          |
| Demo: [A v]       |                                                          |
| [Load demo]       |                                                          |
| [ ] confirm       |                                                          |
| [Clear plan]      |                                                          |
| privacy notice    |                                                          |
+-------------------+----------------------------------------------------------+
Phone: sidebar collapses behind the top-left arrow; columns stack.
```

| Screen | Normal state | Empty / first-use state | Invalid input state | Stale / export state |
|---|---|---|---|---|
| Inputs (8 tabs) | Forms prefilled with defaults; Apply per tab | Blank-plan defaults (General $15, 25/40/55, $2 supplies) | Red box listing each field and message; plan unchanged; typed values kept | n/a |
| Import tab | Template downloads; uploader | No preview | "Import rejected" with sheet / row / field messages | Preview summary + Apply / Discard |
| Dashboard | 7 KPI cards with status words; supporting table; revision id | KPI 3 shows "Run simulation" | n/a | "Results out of date" banner and KPI |
| Budget | Low/likely/high metrics; budget table; ledger; notes | Zero-cost rows shown | n/a | n/a |
| Break-even | 3 metrics; sentence; curve + table; formula check | "Covers its costs even with no registrations" | n/a | "Not achievable within venue capacity" |
| Simulation | Run button; 4 metrics; explainer; histogram + table; tornado + table | "How to read this" expanded; info banner | n/a | Out-of-date warning; old numbers hidden |
| WBS | Editable task table; Apply; Reset to templates | Template tasks | Error list (cycle, missing dependency, negative duration); not applied | n/a |
| Gantt | Timeline by phase; today and event lines; table; dependency list | n/a | "Fix task errors on the WBS page" | Overdue / conflict warning |
| Risks | Score table; editor | Library risks | Error list (likelihood 1-5 etc.) | n/a |
| Staffing | Metrics; role table with gaps and credentials | "No roles entered" | n/a | n/a |
| Marketing | Metrics; checklist editor; CSV download | Generated activities | n/a | "Before earliest start" error + Compress button |
| Exports | XLSX / PDF / CSV buttons | n/a | n/a | PDF labeled "(incomplete)" without a current simulation |
