# Results and Lessons

## Competition context

This engine was developed and iterated in an educational RITC × MSCF market-simulation competition. The team-reported outcome was approximately **top 15, or top 10%, among roughly 150 participating teams**. That placement is presented as an approximate simulated-competition result; it is not a claim of audited live-market performance. The local files reviewed for this release did not contain a contradictory ranking record, but they also did not contain an official leaderboard suitable for independent verification.

## Development observations

- **Tender offers became the primary P&L driver.** Their larger size made route quality, settlement timing, and transient capacity more consequential than signal frequency alone.
- **Direct arbitrage added opportunities.** It provided repeatable relative-value entries, but realized edge was more sensitive to quote age, depth, and multi-leg execution.
- **Converter routes were evaluated against fixed cost.** A converter closed matched inventory cleanly only when the route still won after its USD charge, FX rate, exact lot sizing, and execution-risk penalty.
- **Partial fills and execution mismatches mattered.** A profitable forecast could become residual directional exposure if one leg filled less than the others. Protected lead orders, fill-only hedging, rollback, and settlement barriers were therefore core strategy controls rather than cleanup details.
- **Displayed simulator P&L was volatile while inventory remained open.** Mark-to-market movement could dominate the screen before matched inventory, converter state, and USD cash were reconciled.
- **Fill-based and forecast P&L differed.** Forecasts used synchronized visible depth; realized package P&L used exact fill VWAPs. Market movement, latency, partial fills, and FX execution produced legitimate differences.
- **Continuous operation required careful state resets.** Tender IDs, confirmation streaks, pending campaigns, passive orders, and per-case counters had to reset on a new `ACTIVE` transition, but not on every active loop iteration.

## Included P&L artifact

`assets/pnl_curve.png` is derived from the complete P&L column of one recorded continuous simulator session. The chart preserves every recorded P&L observation in order, including case resets and the final post-stop reconciliation point. Only elapsed time and total simulated CAD P&L are plotted; timestamps, account fields, inventory, market books, orders, tender identifiers, and credentials are excluded.

`examples/sample_pnl.csv` is a deterministic, evenly spaced reduction of the same anonymized series with the first and last observations retained. It is included to demonstrate the public data shape, not to substitute for the full private log or to claim a representative return distribution.

The source run ended with a recorded post-stop simulated P&L of approximately CAD 44.5k. That single session should not be interpreted as an expected return, a backtest, or live performance. No observations were rescaled, smoothed, reordered, or selectively removed from the chart.

## What is intentionally not published

Raw action logs, book snapshots, full-depth data, detailed positions, timestamps, run archives, simulator case materials, and account-linked fields remain outside this repository. Those files are unnecessary to understand or test the execution-safety logic and could expose private or competition-specific information.
