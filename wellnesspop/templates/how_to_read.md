### How to read the simulation

**What it does.** Your event has things you cannot know in advance: how many people register, how many of them don't show up, what supplies end up costing, any cost you marked as uncertain, and (for outdoor or hybrid events) whether weather cancels the day. The simulation plays out your event thousands of times (at least 10,000). Each time it picks a plausible value for every uncertain input from the ranges you entered, then calculates net income with exactly the same rules as the Budget page.

**Probability of breaking even.** The share of those simulated events where income covered all costs (net income of $0 or more). 60% means "in about 6 of every 10 versions of this event, we did not lose money" — it also means 4 in 10 did.

**P10, P50 and P90.** Sort all the simulated results from worst to best.
- **P10** is the "bad case": only 1 in 10 results were worse than this.
- **P50** is the "typical" result: half were worse, half were better.
- **P90** is the "good case": only 1 in 10 results were better.

The gap between P10 and P90 shows how uncertain the outcome is. A wide gap means your assumptions leave a lot of room for surprise.

**The histogram.** Each bar counts how many simulated events landed in a net-income range. The solid line marks $0. Bars to the left of it are losing outcomes. A tall cluster far left of $0 is a warning; a cluster that straddles $0 means the result could go either way.

**The tornado chart.** It answers "which assumption matters most?" Starting from your likely plan, it moves one input at a time to the low end (P10) and the high end (P90) of its range while holding everything else steady, and shows how expected net income changes. Longer bars matter more. Weather is shown separately: its bar swings the cancellation probability from 0 (never cancelled) to 1 (always cancelled), so it is not a percentile.

**How the inputs are modeled.**
- Registrations follow a PERT curve shaped by your low, likely and high estimates.
- No-show rates follow a beta curve centered on your mean; the *concentration* setting (default 6) controls how tightly results cluster around it.
- Variable costs per attendee follow a triangular curve; all supply rows are added together and move as one.
- A cost marked *uncertain* follows a triangular curve between its low, most likely and high values.
- A weather cancellation removes pay-at-the-door income. Prepaid income is kept only where you said refunds are not given, and costs are lost only to the extent you marked them as retained if cancelled.

**Limits.** Sampled inputs are treated as independent of each other (for example, a rainy forecast is not assumed to raise no-shows). Hybrid events use a whole-event cancellation approximation. Results are only as good as your ranges; the same inputs and seed always give the same results.

**This is a forecast, not a guarantee.** Use it to compare options (a lower price, a smaller venue, a sponsor) and to decide what to monitor, not as a promise of what will happen.
