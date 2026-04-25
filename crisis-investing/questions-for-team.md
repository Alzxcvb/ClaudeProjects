# Questions for Collaborators

Discussion prompts for the team review meeting. These are the open questions that need resolution before we can move from research to portfolio construction.

---

## Strategic Questions

### 1. What crisis type are we modeling for?
The entire allocation strategy depends on this. Are we hedging against:
- (a) A 2008-style deflationary recession?
- (b) 1970s-style stagflation?
- (c) A currency/regime crisis?
- (d) All of the above (permanent all-weather hedge)?

The current tariff environment could go either way — tariffs are inflationary (higher import prices) but could also be demand-destructive (trade collapse). This ambiguity is the central challenge.

### 2. Are we building a permanent tail-risk hedge or a tactical crisis portfolio?
- **Permanent hedge:** Fixed allocation across all crisis types, ~2-4% annual opportunity cost vs. equities, always on. Similar to Bridgewater's All Weather approach.
- **Tactical portfolio:** Dynamically shift allocation based on crisis-type probability assessment. Higher potential returns but requires accurate crisis identification in real-time.
- **Hybrid:** Permanent base + tactical overlay. This is our preliminary recommendation.

### 3. What's the liquidity constraint?
Farmland is our #2 ranked crisis asset but is deeply illiquid. Physical gold requires custody infrastructure. If the fund needs daily liquidity, the implementable universe shrinks significantly. Are we constrained to publicly traded instruments?

### 4. What's the time horizon?
- Short-term (months): Tactical positioning for current tariff/trade war
- Medium-term (1-3 years): Recession hedging
- Long-term (decade+): Structural regime-change hedging
- The allocation looks very different at each horizon.

---

## Model Design Questions

### 5. Should the model incorporate regime-change probability scoring?
Our Thesis 3 (government debt is a binary bet) implies we need a way to score the probability that a given government survives. This is inherently political, not just financial. Do we want to go there? If so, what indicators would we use?

### 6. How do we handle the inflation vs. deflation ambiguity?
This is the hardest practical question. The current environment has both inflationary signals (tariffs, supply chain disruption, fiscal deficits) and deflationary signals (demand destruction from trade war, AI-driven productivity gains, potential credit contraction). A portfolio optimized for inflation will get destroyed by deflation and vice versa.

Options:
- (a) Split the difference — equal weight to both scenarios
- (b) Assign probabilities and weight accordingly
- (c) Use options to hedge both tails simultaneously (long OTM puts + long gold)
- (d) Focus on assets that work in both (farmland? gold with caveats?)

### 7. How should we handle crypto?
Bitcoin has been called "digital gold" but its crisis track record is thin and mixed:
- COVID 2020: Fell 50% in March before recovering (correlated with risk assets, not safe haven)
- 2022 crypto winter: Fell 75%+ alongside tech stocks
- Limited correlation data in a true inflation/currency crisis

Do we include it as a speculative position? Ignore it? Wait for more data?

### 8. Should we model the current tariff/trade war as a case study?
We have real-time data: S&P 500 down 4.8% on April 3 tariff announcement, gold up 27.4% YTD. Should we add this as an 11th case study (in progress) to ground the model in the immediate environment?

---

## Implementation Questions

### 9. What's the benchmark?
What should this crisis portfolio be measured against?
- 60/40 portfolio?
- Pure equity (S&P 500)?
- Endowment model?
- "Do nothing" (cash)?

### 10. Rebalancing frequency?
- Calendar-based (monthly, quarterly)?
- Threshold-based (rebalance when allocation drifts >5%)?
- Event-driven (rebalance on crisis indicator triggers)?

### 11. Position sizing methodology?
- Equal risk contribution (risk parity)?
- Maximum drawdown optimization?
- Kelly criterion?
- Fixed percentage allocations?

### 12. Shorting and derivatives?
Should the model include:
- Short positions on identified bubble assets?
- Put options as tail-risk insurance?
- VIX-linked instruments?
- CDS on sovereign debt?

These add complexity but could improve risk-adjusted returns significantly.

---

## Scope Questions

### 13. Geographic focus?
Are we hedging a US-centric portfolio? Global? Does the fund have emerging market exposure that needs specific regime-change hedging?

### 14. Client profile?
Is this for:
- Institutional (pension, endowment) — long horizon, liquidity needs
- UHNW individual — more flexibility, optionality value (geographic diversification, citizenships)
- Hedge fund internal — can use leverage, derivatives, shorting

### 15. Deliverable format?
What does the hedge fund manager want:
- A research paper?
- A quantitative model (Python, R)?
- An allocation recommendation?
- A framework they can use internally?

---

*These questions are ordered by priority. Questions 1-4 must be answered before we can proceed to quantitative modeling. Questions 5-8 shape the model's sophistication. Questions 9-15 determine implementation.*
