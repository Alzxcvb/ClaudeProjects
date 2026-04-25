# Cross-Crisis Regression Analysis: Asset Performance by Crisis Type
## Quantitative Findings from 24 Historical Scenarios

**Date:** April 2026  
**Methodology:** Scenario-weighted portfolio optimization across 5 crisis types, 24 historical events, 19 asset classes  
**Run with:** `analysis/portfolio-optimizer.py`

---

## 1. Overall Asset Rankings by Crisis Type

Ranking assets from BEST to WORST expected return within each crisis type, based on historical return data. All figures are holding-period returns (not annualized unless noted) sourced from primary data files in `data/crises/`.

### Type 1: Inflationary / Stagflationary Crises
*Scenarios: 1970s Stagflation, 1973 OPEC Shock, Post-WWI UK, Volcker Shock, 2022 Inflation*

| Rank | Asset | Typical Return | Key Evidence |
|------|-------|---------------|--------------|
| 1 | Energy Stocks | +65% to +250% | 2022: +65%; 1973-74 OPEC stocks: +200%+ |
| 2 | Commodity Producers | +80% to +120% | 1970s decade: +80-120% for mining/energy |
| 3 | Gold (Physical) | +73% to +2000% | 1973-74: +73%; 1970s full decade: +2000% |
| 4 | Farmland | +15% to +80% | Appreciated with commodity prices in all inflationary periods |
| 5 | Non-USD Hard Currency | +20% to +40% | CHF appreciated ~40% vs USD in 1970s |
| 6 | Defense / A&D | +5% to +15% | Defense budgets rise in geopolitical tension |
| 7 | Consumer Staples | -5% to +7% | Modest; pricing power but multiple compression |
| 8 | Healthcare | -10% to +8% | Mixed; depends on government price controls |
| 9 | TIPS | +3% to +8% | Inflation linkage helps; real yield still matters |
| 10 | Short Treasuries | -3% to +2% | Small negative real; but preserves nominal vs. alternatives |
| 11 | USD Cash | -15% to -2% | Purchasing power erosion in inflation |
| 12 | US Broad Equities | -48% to -2% | 1973-74: -48% despite "good" economy |
| 13 | International Equities | -25% to -15% | Fall with US; some currency benefit |
| 14 | Investment Grade Bonds | -30% to -8% | Duration-sensitive; destroyed in 1970s |
| 15 | Long-Duration Treasuries | -25% to -10% | Worst fixed-income asset in inflation |

**Key finding:** In inflation, energy and commodity producers are the primary alpha generators. Gold is the safe store of value but with lower operating leverage than producers.

---

### Type 2: Deflationary Panic Crises
*Scenarios: Great Depression, 2008 GFC, 1907 Panic, COVID Acute, 1997 Asian Crisis*

| Rank | Asset | Typical Return | Key Evidence |
|------|-------|---------------|--------------|
| 1 | USD Cash | +0% nominal, +30% real (1929) | Deflation increases purchasing power |
| 2 | Long-Duration Treasuries | +10% to +25% | 2008: flight to safety; 1929: nominal preservation |
| 3 | Short-Duration Treasuries | +8% to +30% | 2008: +6-8%; Great Depression: +30% real |
| 4 | Investment Grade Bonds | +5% to +10% | 2008: +6%; safe-haven bid |
| 5 | Gold | -5% to +25% | Mixed: initial panic selling (2008: -5%), then recovery (+25% during recession) |
| 6 | Consumer Staples | -15% to -10% | Falls but less than market; "defensive" |
| 7 | Healthcare | -22% to -10% | Better than market; lower beta |
| 8 | Defense / A&D | -20% to -5% | Government contractor stability |
| 9 | Farmland | -2% to +30% | 2008: +30%; Depression: -40% (varies by era) |
| 10 | Non-USD Hard Currency | +5% to +15% | Safe-haven currencies appreciate in panic |
| 11 | Non-US Developed Equities | -55% to -25% | Correlated to global deleveraging |
| 12 | US Broad Equities | -57% to -34% | 2008: -57%; COVID acute: -34% |
| 13 | Energy Stocks | -53% to -15% | Pro-cyclical; 2008: -53% |
| 14 | Commodity Producers | -45% to -20% | Demand destruction hits first |
| 15 | High-Yield Bonds | -26% to -15% | Credit risk materializes |
| 16 | Emerging Markets | -54% to -25% | Maximum drawdown in risk-off events |

**Key finding:** In deflation, cash and long-duration Treasuries are the only clearly positive assets. Gold and farmland are conditional on the severity and duration.

---

### Type 3: Currency Collapse / Hyperinflation
*Scenarios: Weimar, French Assignat, Zimbabwe, Venezuela, Argentina*

| Rank | Asset | Typical Return (vs. hard currency) | Key Evidence |
|------|-------|-----------------------------------|--------------|
| 1 | Non-USD Hard Currency | +500% to +10,000% in local terms | USD in Soviet collapse: +10,000% vs ruble |
| 2 | Gold (Physical) | +500% to +5,000% in local terms | Universally accepted; 700-year record (Solidus) |
| 3 | Farmland / Productive Land | +200% to +2,000% in local terms | Real utility; French Assignat land buyers |
| 4 | Bitcoin (modern analog) | +200% to +2,000% | Used in Venezuela; "digital gold" in currency crisis |
| 5 | Commodity Producers | +50% to +500% | Revenue in hard goods; less than raw gold |
| 6 | Foreign-Listed Equities | +50% to +200% | Earnings in stable currencies |
| 7 | US/Foreign Treasuries | +∞ vs. collapsed currency | For a USD investor: local crisis is irrelevant |
| 8 | USD Cash (if investor is foreign) | Total preservation | The reference asset that defines "total loss" |
| **WORST** | Any asset in collapsing currency | -99.9% | Cash, bonds, bank deposits, local stocks |

**Key finding:** In currency collapse, everything denominated in the collapsing currency goes to zero. The only protection is getting OUT of the currency BEFORE collapse is obvious. The window is narrow (weeks to months).

---

### Type 4: Speculative Bubble Pop
*Scenarios: Dot-Com, Japan 1989, South Sea, 1973 Nifty Fifty, Black Monday 1987*

| Rank | Asset | Typical Return | Key Evidence |
|------|-------|---------------|--------------|
| 1 | USD Cash | +0% nominal; strong relative performance | Enables buying at trough |
| 2 | Short-Duration Treasuries | +5% to +12% | Flight to safety |
| 3 | Non-USD Hard Currency | +5% to +10% | Modest safe-haven bid |
| 4 | Energy Stocks | -15% to +24% | 2000-02: +24% (counter-cyclical to tech) |
| 5 | Consumer Staples | -3% to +5% | Dot-com: +5%; non-bubble sector rotation |
| 6 | Defense / A&D | -2% to +12% | 2001-02: post-9/11 defense surge |
| 7 | Healthcare | -6% to +5% | Dot-com: -6%; less defensive than expected |
| 8 | Gold | +14% to +73% | 2000-02: +14%; longer recovery needed |
| 9 | Farmland | +5% to +15% | Uncorrelated to tech bubble |
| 10 | Investment Grade Bonds | +10% to +18% | 2000-02: bonds outperformed significantly |
| 11 | Non-US Developed Equities | -48% to -25% | Correlated to global risk-off |
| 12 | US Broad Equities | -49% to -30% | S&P -50% in dot-com, -30% in Japan |
| 13 | Emerging Markets | -43% to -20% | Higher beta to risk sentiment |
| 14 | The Bubble Asset (tech 2000, Japan equities 1989) | -78% to -63% | Maximum drawdown |

**Key finding:** In a pure speculative bubble pop (not accompanied by credit crisis), cash and short-term bonds are best. The critical insight is sector rotation: in dot-com (tech bubble), energy and consumer staples gained while tech lost 78%.

---

### Type 5: Regime / State Collapse
*Scenarios: Roman Empire, Soviet Union, Yugoslavia*

| Rank | Asset | Typical Return | Key Evidence |
|------|-------|---------------|--------------|
| 1 | Gold (Physical, Portable) | +∞ effective | Roman Solidus: 700 years stable; universal acceptance |
| 2 | Non-USD Hard Currency | +500% to +10,000% | Only works if stored OUTSIDE collapsing jurisdiction |
| 3 | Productive Farmland | +100% to +500% | Foundation of feudal wealth post-Rome |
| 4 | Privatized Real Property | +100% to +300% | Soviet privatization beneficiaries preserved wealth |
| 5 | Foreign Assets (any) | Total preservation | Geographic diversification > everything |
| 6 | Physical Skills/Human Capital | Non-financial | Language, technical skills, security relationships |
| **WORST** | Government debt | -100% | Always the first casualty |
| **WORST** | Urban real estate | -67% to -100% | Urban trade networks fail without state |
| **WORST** | Bank deposits | -100% | Banking system collapses with state |

**Key finding:** Regime collapse is categorically different from financial crises. Portfolio optimization becomes secondary to physical security, legal residency, and geographic optionality. Gold and farmland are the only financial assets with a consistent track record.

---

## 2. Portfolio Optimizer Output Summary

### Base Case (65% Inflation, 15% Bubble Pop, 10% Deflation, 5% Currency, 5% Regime)

| Portfolio Strategy | E(Return) | Worst Case | Positive Types |
|-------------------|-----------|------------|----------------|
| Gold Heavy (30% gold) | **33.3%** | -14.5% | 4/5 |
| Currency Collapse Hedge | **32.6%** | -9.7% | 4/5 |
| Current Report Recommendation | 25.1% | -9.8% | 4/5 |
| Inflation Tilted | 24.8% | -13.9% | 3/5 |
| Max Coverage (diversified) | 22.6% | -11.5% | 4/5 |
| All Weather Equal | 22.6% | -6.8% | 4/5 |
| Dalio All Weather | 10.9% | -8.6% | 4/5 |
| Deflation Hedged | 10.6% | -14.8% | 4/5 |
| **Traditional 60/40** | **-11.6%** | **-54.3%** | **0/5** |

### Key Quantitative Insight: The 60/40 Collapse

The traditional 60/40 portfolio produces **-11.6% expected return** in the April 2026 base case and **negative returns in ALL 5 crisis types**. This is not a failure mode unique to a specific scenario — it is structurally wrong for the current probability distribution:

- In inflation (65% weight): US equities -2% to -48%, long bonds -10% to -25%
- In deflation (10% weight): Some bond recovery, but insufficient
- In currency collapse (5% weight): Total loss of bond and equity value
- In bubble pop (15% weight): Equity portion falls -30% to -50%
- In regime collapse (5% weight): Complete loss of all financial assets

The only scenario where 60/40 performs is a mild 2020-COVID-style deflation that is quickly reversed by central bank intervention. Assigning more than 10% probability to that specific outcome in the current structural environment is not defensible.

---

## 3. Sensitivity Analysis: How Probability Shifts Change Rankings

The optimizer was run across 7 different probability distributions. Findings:

### Robust Winners (top 3 in most scenarios)
- **Gold Heavy** — #1 or #2 in 5 of 7 probability distributions
- **Currency Collapse Hedge** — #1 or #2 in 4 of 7 distributions

### What Changes the Rankings
- If **deflation becomes dominant** (60%+ probability): Cash and short bonds rise to top; gold drops to 3rd
- If **currency collapse risk rises** to 30%+: Non-USD hard currency becomes the single most important asset
- If **bubble pop risk rises** to 40%: Cash and short bonds rise; energy holds; everything else falls

### Consistent Losers Across All Distributions
- Long-duration US Treasuries: Negative in 6 of 7 scenarios
- US Broad Equities alone: Negative in base case and inflation scenarios
- High-Yield Bonds: Negative in 5 of 7 scenarios

---

## 4. Asset Correlation Matrix: Crisis Performance

Assets that correlate POSITIVELY in crisis (both win or both lose together):
| Asset Pair | Crisis Correlation Pattern |
|------------|--------------------------|
| Gold + Non-USD Currency | Positive in inflation, currency collapse, regime |
| Consumer Staples + Healthcare | Positive in bubble pop and mild deflation |
| Short Bonds + Cash | Positive in deflation and acute panic |
| Energy + Commodity Producers | Positive in inflation and stagflation |
| All equities (incl. defensive) | Positive in acute panic (all fall together, Day 1-30) |

Assets that correlate NEGATIVELY (one wins when other loses):
| Asset Pair | Crisis Type |
|------------|------------|
| Gold vs. Short Bonds | Gold wins inflation; bonds win deflation |
| Energy vs. Bonds | Energy wins inflation; bonds win deflation |
| Gold vs. US Equities | Opposite in stagflation (1970s gold +2000%, equities 0%) |
| Non-USD FX vs. USD Cash | Non-USD wins in currency collapse; USD cash wins in domestic deflation |

---

## 5. The 1973 Nifty Fifty — Direct Precedent for Mag-7 Risk

This is the most important historical parallel for the current AI equity concentration risk.

### 1972-74 Data Points (from sourced research)
- S&P 500 P/E at peak (late 1972): ~19× (Shiller CAPE ~20)
- Nifty Fifty stocks average P/E at peak: 41.9× (range: 24× for Emerson Electric to 91× for Polaroid)
- Avon Products: P/E 64× at peak; Polaroid: 91×
- S&P 500 peak to trough 1973-74: -48.2%
- Best estimate for Nifty Fifty basket decline 1972-74: -70% to -80%
- Which Nifty Fifty names recovered? Consumer staples (P&G, Coca-Cola), pharmaceuticals (J&J, Merck); NOT Polaroid, Xerox, Kodak

### Modern Parallel
- Nvidia P/E in 2025: ~50× earnings
- Microsoft P/E: ~32×
- Top 10 S&P 500 stocks' share of index: ~38% (approximate, vs ~30% at dot-com peak)
- Nifty Fifty concentration: ~20% of total S&P market cap

### The Critical Difference
- Nifty Fifty companies were largely non-technology (consumer staples, healthcare)
- Mag-7 are technology companies with genuine, massive earnings (Nvidia: $215B revenue, 53% net margins)
- Nifty Fifty collapse was primarily multiple compression (40× → 12×), not earnings collapse
- Mag-7 collapse, if it occurs, will be similar: earnings remain; multiples compress from ~50× to ~25×
- Implied S&P 500 impact: -15% to -25% purely from Mag-7 re-rating

---

## 6. Dalio All-Weather: Why It Underperforms Now

The Dalio All-Weather portfolio (approximately 30% bonds, 15% stocks, 7.5% gold, 7.5% commodities, 40% mixed) was designed for a world where bonds and stocks are negatively correlated — meaning bonds rise when stocks fall.

**This correlation broke down in 2022.** In 2022:
- S&P 500: -18%
- US Long-Duration Treasuries: -25% to -30%
- Both fell simultaneously — the classic All-Weather protection failed

**Why:** All-Weather is optimized for demand-driven business cycles, not supply-driven inflationary cycles. In a supply shock (1970s, 2022), bonds and stocks fall together because inflation hurts both.

**The optimizer confirms this:** Dalio All-Weather gets +10.9% expected return in the base case — lower than every crisis-focused portfolio. It ranks 7th of 9, ahead only of the pure Deflation Hedge and the destroyed 60/40 Traditional.

**The correction needed:** Reduce bond allocation from ~30% to ~8% (short-duration TIPS only). Increase gold from 7.5% to 17-20%. Add non-USD hard currency (currently 0% in All-Weather).

---

## 7. Summary: The Dominant Portfolio Architecture

Based on 24-scenario regression across 19 asset classes, the dominant crisis-resilient portfolio has:

**Core (50-55% of portfolio):**
- Gold: 20-30% (physical + ETF + miners) — performs in inflation, currency collapse, regime
- Non-USD Hard Currency: 10-15% (CHF, SGD) — performs in all crises; best in currency collapse
- Farmland: 8-12% — performs in inflation, 2008-type deflation, regime collapse

**Tactical (25-30% of portfolio):**
- Short-Duration TIPS: 6-10% — inflation linkage with liquidity
- Commodity Producers: 8-12% — inflation leverage
- Energy Stocks: 5-8% — OPEC/supply-shock specific hedge

**Defensive Equities (10-15% of portfolio):**
- Consumer Staples + Healthcare + Defense: 8-12% total
- Provides equity-like returns in normal environments; -15 to -25% in crisis vs. -48 to -57% for broad market

**Optionality (5% of portfolio):**
- Bitcoin: 2-3% — asymmetric upside in currency collapse; sized for total loss tolerance
- Tail-Risk Instruments (VIX, puts): 2-3% — crisis acceleration insurance

**What to AVOID:**
- Long-Duration US Treasuries (negative expected value in base case)
- US Broad Equity Index at current weights (Mag-7 re-rating risk + inflation drag)
- Traditional 60/40 construction (catastrophically wrong for current probability distribution)
- Private equity with long lockups (illiquidity + leverage + mark-to-model)

---

*Sources: Return estimates derived from primary historical data in `data/crises/`. See also `data/key-numbers.md` for quantitative anchors. All optimizer code and methodology in `portfolio-optimizer.py`.*
