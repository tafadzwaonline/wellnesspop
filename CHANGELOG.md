# Changelog

Weekly status format: done / blocked / next.

## 2026-10-29: UI refresh

**Done**
- Light and dark themes (teal brand, system font stack, no remote fonts), logo and favicon.
- Grouped sidebar navigation with icons (Overview, Plan, Finances, Project, Share) and a current-plan card.
- Consistent page headers; KPI cards with worded status pills; bordered metrics; tabs on long pages.
- Welcome panel for new plans; numeric, sortable tables; emoji removed from statuses.
- Verified in Chrome at desktop and phone widths, light and dark (no console errors, no horizontal scroll).

## 2026-10-29: MVP build

**Done**
- Input schema with defaults, units and provenance for every field; validation with field-level errors.
- Shared vectorized financial evaluator; budget; break-even (hand fixture matches to the cent).
- WBS templates, backward scheduler, editable tasks with tombstones, Gantt with today marker.
- Monte Carlo (PERT, scaled beta, triangular, Bernoulli weather), cancellation accounting, tornado, explainer.
- Risk register, staffing coverage and credentials, marketing schedule with compression.
- Dashboard, CSV/XLSX import with security limits, eight-sheet workbook, one-page PDF, marketing CSV.
- Three demos; Streamlit UI with 10 outputs plus inputs; 85 automated tests passing.
- Docs: decisions, assumptions, schema, user guide, explainer, deployment, project plan.

**Blocked / needs owner**
- Owner approval of proposed model decisions; research of illustrative defaults.
- Community Cloud usage-statistics decision (D24).
- User tests, Excel/Google Sheets manual checks, deployment, demo video, case study.

**Next**
- Rebaseline gate dates with the project owner; book two usability testers.
