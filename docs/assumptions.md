# Assumptions and provenance

Every effective input, its unit and its provenance are exported to the **Assumptions** sheet of the workbook. This page summarizes the conventions and lists the values that are not from the brief.

## Provenance kinds

| Kind | Meaning |
|---|---|
| `brief` | Taken from the project brief, Appendix B (issued 25 September 2026) |
| `illustrative` | Invented to make the tool usable or a demo complete. **Not researched.** |
| `derived` | Calculated by the app, or a system/model setting |
| `user` | Changed by the organizer in this session (original provenance kept) |
| `researched` | A documented external source with retrieval date. **No value currently has this status.** |

## Model-shape assumptions (derived)

- Attendance: modified PERT, λ = 4.
- No-shows: scaled beta, concentration 6 by default.
- Variable costs: triangular on summed rows (rows move together).
- Weather: Bernoulli whole-event cancellation; indoor forced to 0.
- Percentiles: `numpy.quantile(..., method="linear")`.
- Sampled dimensions are independent.

## Values from the brief (Appendix B)

Capacities (60 / 40 / 220), registration ranges (25/40/55, 15/25/35, 80/150/220), prices ($15 general, $10 early bird, ten free places; $25 flat; free entry, $10 class passes, six $50 vendor fees), variable costs ($2, $3, $1.50 per attendee), no-show means (20%, 15%, 30%), weather (25%, 0%, 20% outdoor), staffing roles, fixed-cost categories, and the 1-per-30 check-in ratio.

## Illustrative values that must be researched or confirmed before release

| Scenario | Illustrative values |
|---|---|
| All | Permit lead time 30 days; insurance lead time 14 days; outdoor weather 25%, hybrid 20% defaults; no-show ranges (±10 points); variable-cost ranges; concentration 6; ticket fee 3% (A, B, C class passes); refund 100% / fee refund 0%; cost retention fractions |
| A | Ticket mix 60% general / 40% early bird; permit $25; insurance $75; signage $30; speaker $30–$60; instructor $100 flat; check-in volunteer hours; marketing $25; spending limit $600 |
| B | Room rental $150 ($50 advance); deposit $100; insurance rider $60; printing $20–$50; practitioner $200; check-in $18/hour × 2.5 h; marketing $40; target net $100; spending limit $650 |
| C | Venue $250; insurance $150; tents $150–$300; tables/chairs $100; sound $120; printing $60; instructors $75 each; first aid $25/h; setup $20/h; photographer $100; class-pass uptake 60% × 2 passes; marketing $75; target net −$500 (subsidy); spending limit $3,000 |

Demo amounts were set to plausible small-event figures so that the three demos show contrasting outcomes (B is close to break-even, A needs more paid attendees, C relies on a subsidy). They are not Chicago market research.

## Research still to do (owner / builder task)

Suggested sources from the brief: BLS wages, Census ACS, Chicago Park District permits and fees, NWS Chicago climate data, Yoga Alliance, and practitioner interviews. Record source, URL, retrieval date and applicability for each value, then set its provenance to `researched`. Do not treat rainfall frequency as a cancellation probability. The app never fetches these sources at runtime.
