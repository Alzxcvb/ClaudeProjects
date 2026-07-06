# Domain: Data Analysis & Statistics

Applies when: analyzing data to answer a question — exploratory analysis, metrics, statistical claims, charts, and the write-ups built on them. Load with `CLAUDE-FABEL.md`.

The defining risk: analysis fails SILENTLY. Broken code crashes; a broken analysis produces a confident number that's wrong, and the number gets used. Every standard here exists to make wrongness loud.

## 1. Failure modes

- **Conclusions before profiling.** Computing on data never inspected: dupes inflating counts, nulls silently dropped by aggregations, a join that fanned out rows 3×. The analysis is precise arithmetic on garbage.
- **The seductive mean.** Reporting averages on skewed data where the mean describes nobody (one whale in the revenue data). No distribution looked at, no median/percentiles reported.
- **Narrative overfitting.** Running cuts until something interesting appears, then presenting it as THE finding without mentioning the twenty cuts that showed nothing. Multiple comparisons dressed as insight.
- **Causal leakage.** "Correlates with" becoming "drives" between the notebook and the summary. Selection effects and confounders unmentioned (the users who adopted the feature were the engaged ones already).
- **Chart crimes.** Truncated bar axes manufacturing drama, dual axes implying correlation, unlabeled units — honest numbers presented dishonestly.
- **Untraceable numbers.** A figure in the report that no code produces; nobody can reproduce or check it, including its author a week later.

## 2. Standards

- **Profile before analyzing, every time**: row count, key uniqueness, null rates per relevant column, ranges/min/max, top values, duplicates. Quote the profile in your notes. This is the domain's ORIENT step and it is not skippable.
- **Every reported number is traceable to code** that a stranger can re-run: raw data → transformations → figure. No hand-computed, hand-pasted numbers in the deliverable.
- Every claim carries its N and its denominator ("23% of the 412 users who completed onboarding," not "23% of users"). Small-N results are labeled as such.
- Distributions before summaries: look at the histogram before trusting any mean; report median/percentiles alongside means on skewed data.
- Correlation and causation are separated EXPLICITLY in the write-up, and the top plausible confounder or selection effect is named, not footnoted.
- Filters and exclusions are documented with counts ("excluded 118 test accounts; 4,294 remain") — exclusions are where analyses get quietly cooked.
- Charts: bar charts start at zero; axes labeled with units; one y-axis unless there's a stated reason; the caption states the takeaway the chart supports.

## 3. Defaults

- The dumbest sufficient method: counts and group-bys before models; a scatter plot before a regression; a regression before anything fancier. Complexity needs a reason the simple version can't answer.
- Sanity anchors first: before computing the target metric, compute one number you already know (total revenue, user count) and confirm the data reproduces it. If the known number is wrong, stop.
- Reproducible medium: script or notebook run top-to-bottom clean before results are shared (stale notebook cell state is a classic silent lie).
- Point estimates get uncertainty when decisions hang on them — a range, a confidence interval, or an honest "n too small to say."

## 4. Verification

- **Recompute the headline number a second, independent way** (different grouping path, raw SQL vs. dataframe, a hand-count on a small filter). Agreement is the strongest check available in this domain.
- Reconcile totals across every join/filter step: rows before, rows after, and WHY. A join that changed the row count unexpectedly is a bug until explained.
- Spot-check 5 individual records against the claim (find one specific user and confirm they really behave as the aggregate says).
- Magnitude test: is the number plausible against known reality? An "average session of 14 hours" fails this test; catch it before the reader does.
- Re-run the whole artifact top to bottom in a fresh session; results identical?

## 5. Edge cases that always matter

- Nulls in aggregation: does the mean ignore them or count them as zero — and which did you intend?
- Duplicates and grain: is the table one-row-per-user or per-event? Every aggregate depends on knowing this; verify with a key-uniqueness check, not assumption.
- Time: timezone of the timestamps vs. the business day; partial current-day/month deflating the last data point of every trend chart (drop or label it).
- Survivorship: today's users look better than cohorts including the churned; the fix is cohorting, not caveating.
- Zeroes vs. missing: a user with no events is absent from the events table — left-join from the population, or your "average events per user" only averages the active.

## 6. Stop signals

- The result is surprisingly strong → hunt for the leak first (a join fan-out, target leakage in a feature, a filter that selected the outcome). Exciting results are usually bugs; treat excitement as a tripwire, not a reward.
- You're on the fifth cut of the data looking for something interesting → you're now guaranteed to find noise; stop, or predeclare the next cut as the last and label the result exploratory.
- The stakeholder's question keeps shifting after each answer → the real question is undefined; get it in writing (the "done means" of analysis) before more computation.
- You can't explain the metric's definition in one sentence → neither can the reader; define it before measuring it.
