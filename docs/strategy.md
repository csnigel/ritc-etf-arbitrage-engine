# Strategy Design

## Pricing relationship

RITC is quoted in USD, while BULL and BEAR are quoted in CAD. The engine treats one RITC share as economically comparable to one BULL share plus one BEAR share:

\[
P_{RITC}^{USD}\,F_{CAD/USD}\approx P_{BULL}^{CAD}+P_{BEAR}^{CAD}.
\]

This identity is only a reference. An executable opportunity must survive bid/ask spreads, equity fees in each instrument's quote currency, available USD/CAD depth, order-size rules, risk limits, and a minimum total-P&L filter.

## Direct arbitrage

### Cheap ETF

The cheap-ETF direction buys RITC at its ask, buys the USD needed for that RITC cash flow at the USD/CAD ask, and sells BULL and BEAR at their bids. For a depth slice, the approximate net edge is

\[
e_{cheap}=BULL_{bid}+BEAR_{bid}-(RITC_{ask}+f)FX_{ask}-2f,
\]

where \(f\) is the per-share market fee in the security's quote currency. The engine enters only when each consumed slice meets the direct edge threshold and the rounded package clears the total-P&L threshold.

### Rich ETF

The rich-ETF direction sells RITC at its bid, converts the resulting USD at the USD/CAD bid, and buys BULL and BEAR at their asks:

\[
e_{rich}=(RITC_{bid}-f)FX_{bid}-BULL_{ask}-BEAR_{ask}-2f.
\]

The two directions use opposite sides of every book; midpoint comparisons are not used for qualification.

### Depth-aware quantity selection

`synchronized_direct_slices()` advances cursors through four books—BULL, BEAR, RITC, and USD. A slice can be no larger than the remaining executable quantity in any required leg. USD depth is translated into the number of RITC shares whose cash flow it can cover. Profitable depth is accumulated up to the stage cap, rounded down to `QTY_STEP`, and then reduced in steps until weighted risk and matched-inventory constraints pass.

### Scaling stages

The source preserves three direct-arbitrage stages. The selected V13 setting is stage 3: 10,000 shares per direct action, a 40,000-share coherent matched-inventory cap, weighted gross 220,000, and absolute weighted net 25,000. Lower stages retain the same logic with smaller quantities and gross capacity. Only `DIRECT_SCALE_STAGE` is intended to choose among these tested bundles.

### Protected-limit and passive execution

The immediate direct path performs a fresh snapshot and breaks larger candidates into independently revalued 2,500-share children. RITC leads each child through a short-lived marketable limit. Its price reserves a minimum realized edge and a basket-slippage allowance; BULL, BEAR, and FX hedge only the confirmed RITC fill. If the basket cannot match that fill, unmatched RITC is reversed.

The separate passive module may rest a capped RITC limit briefly when the resulting hedge still clears its higher edge and total-P&L thresholds. A fill receives the simulated limit rebate in the P&L calculation. Expired orders are cancelled, cancellation races can be inferred from position changes, and only the frozen fill is hedged.

Market orders prioritize completion but expose the strategy to slippage. Protected limits cap the lead price but introduce non-fill, partial-fill, and cancellation risk. V13 uses each where its route economics and recovery design support it.

## Fixed-price tenders

Only fixed-price tenders are automated. Competitive tenders are logged and skipped. A fixed offer is eligible only when a complete route:

- covers the entire tender quantity;
- clears the minimum per-share accounting edge;
- clears the minimum risk-adjusted route score;
- remains inside acceptance and step-by-step transient limits; and
- has enough case time for its route.

The engine compares four executable families:

1. **Direct unwind:** offset all tender RITC through the RITC book.
2. **Basket hedge:** trade equal BULL and BEAR quantities and hold matched ETF/basket inventory.
3. **Hybrid:** use direct RITC depth for one portion and basket hedge the residual. The optimizer searches direct quantities and applies hold/time penalties only to the basket portion.
4. **Mixed converter:** combine direct RITC depth with a basket hedge in exact converter lots, then create or redeem RITC automatically.

The route with the highest eligible `score_cad` is selected. Basket routes subtract holding and late-case penalties from accounting P&L for ranking. Converter routes subtract the fixed converter charge and a per-share execution-risk penalty. These score haircuts guide route choice; accounting P&L remains separately recorded.

## Converter economics

The converter operates only in 10,000-share lots. For \(n\) uses, its CAD cost is

\[
C_{converter}=n\times 1{,}500\;USD\times FX_{ask}.
\]

The mixed-route search iterates feasible lot counts, prices the direct remainder and basket portion from visible depth, and subtracts converter cost before testing profitability. A converter route is unavailable when the quantity is not an exact lot multiple, the correct direction is not armed, the asset/lease cannot be verified, time is too short, or another converter campaign is pending. This prevents conversion from being chosen merely because it closes inventory; it must improve the fully costed route score.

After tender settlement, the chosen route is re-priced. If converter preflight fails, the engine selects the best feasible non-converter fallback or performs an emergency direct risk reduction. Each converter lot is submitted and its expected position transformation is verified before the next lot.

## FX exposure and hedging

RITC trades create or consume USD cash. Because opportunity valuation already prices those cash flows at executable USD/CAD bid or ask, the normal hedge target is zero residual USD:

\[
\Delta USD=0-USD_{current}.
\]

A positive adjustment buys USD; a negative adjustment sells USD. Background hedging waits until the exposure exceeds the configured trigger, while completed direct, passive, tender, and converter workflows can force immediate reconciliation. Before converter execution, excess or deficient USD is converted so that only the known converter funding requirement remains.

## Risk, fills, and case controls

Weighted gross and net are

\[
G=|BULL|+|BEAR|+2|RITC|,\qquad N=BULL+BEAR+2RITC.
\]

The 2× RITC weight matches the two-component basket. Direct actions must satisfy ordinary caps and the coherent matched-inventory cap. Inventory-reducing direct trades may continue above the ordinary gross cap only when gross falls strictly, absolute net does not worsen, and net is already within its cap. Tenders use separate transient caps because the tender settles before its hedge.

Exact-fill P&L is calculated only when aggregated fills equal the intended reconciled quantity. Zero quantity returns `None`; partial fills also return `None`, preventing a partial VWAP from masquerading as a completed package. Concurrent-leg excess is rolled back. Tender legs have direct or basket contingencies, and unresolved residuals are explicitly logged.

Time gates progressively stop new passive quotes, new direct inventory, all direct trades, longer tender routes, direct-only tenders, and finally all new orders. When an active case ends, the loop returns to a waiting state. Per-case decision and pending-execution state is reset once—and only once—when the next case becomes active.
