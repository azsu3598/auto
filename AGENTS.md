# AGENTS.md — Korean Stock Recommendation Rules

## Repository-local Markdown and folder organization

* For work in this repository, create all new Markdown files inside the current
  repository. This project-specific user instruction overrides the global default
  of writing documents under `D:/Dev/2026/SKR/docs`.
* Keep `AGENTS.md`, `README.md`, `PC-C_단독진행_전체인수인계.md`, and
  `Codex_세션간_공동_인수인계.md` at the repository root. Keep existing execution
  guides there unless their references are migrated together.
* Use `docs/` and its strategy/operations subdirectories for project documents,
  `Sabu/` for chart education, and `Sabu/교재/` for textbook editions.
* Store dashboard screenshots in `docs/assets/dashboard/` and update current
  references when moving them. Do not rewrite historical handoff records.
  Verbatim archiving under rule 4 of "Before every push" is allowed.
* `archives/` contains local recovery backups and retired artifacts and is ignored
  by Git. Do not stage archives, credentials, runtime data, or raw logs.
* The user removed `GorapaduckPet` from this workspace. Do not recreate its project
  or build artifacts as part of stock-automation work.

## PC-D / PC-C Git handoff rules

These instructions apply to every Codex session working anywhere under this
repository. They are mandatory after every Git pull and before every Git push.

### PC identity

* Treat `D:/Test` as `PC-D`: code, review, documentation, and handoff.
* Treat `C:/Test` as `PC-C`: execution, Docker, Kiwoom simulation, DynamoDB, and
  AWS integration verification.
* Never hardcode either absolute path in application code.

### At session start and after every pull

Before changing code, read these files in order:

1. `AGENTS.md`
2. `PC-C_단독진행_전체인수인계.md`
3. `Codex_세션간_공동_인수인계.md`

Section `10. 세션 전달 기록` keeps only the five most recent records. Open
`docs/운영 검증/공동_인수인계_세션기록_보관.md` only when a recent record refers
to older work, when verifying a past claim, or when the user asks for history.

Then compare the handoff claims with the actual Git status, source code, and tests.
Do not assume that a document or a previous chat is current. Preserve uncommitted
work and never overwrite another PC's changes to resolve a conflict.

On PC-C, explicitly acknowledge this review before starting work with a concise
status equivalent to:

> PC-C 인수인계와 실제 코드를 확인했습니다. 기존 안전장치를 유지하고 실거래를
> 활성화하지 않은 상태에서 실행·통합검증을 진행합니다.

If a pull was completed during an active session, reread all three files and repeat
the acknowledgment before continuing. If the worktree is dirty or the pull has a
conflict, stop and report the exact files instead of discarding changes.

### Safety boundary on both PCs

* Never remove or weaken an existing order, account, position, or kill-switch
  safeguard merely to make a test pass.
* Never set `LIVE_ORDER_ENABLED=1`, turn the kill switch off, connect a real-account
  secret, submit a real order, or activate an AWS live schedule without a separate
  explicit user request and approval.
* Do not commit account numbers, fingerprints, API keys, AWS credentials, tokens,
  raw CloudWatch exports, or other secrets and personal information.
* Keep closing-bet, medium-term, day-trade, paper, and live state separated.
* Any strategy or safety change requires an appropriate test and a full regression
  test run.

### Before every push

1. Review `git status` and stage only the files belonging to the current task. Do
   not use `git add .` when unrelated workspace changes exist.
2. Run the relevant focused tests and the complete `stock-automation` test suite.
3. Run syntax or fixture validation required by the changed file types and run
   `git diff --check` on the intended changes.
4. Add a new record at the top of section `10. 세션 전달 기록` in
   `Codex_세션간_공동_인수인계.md`. Keep only the five most recent records
   (by position) there; move any older record verbatim to the top of the
   `보관 기록` section in `docs/운영 검증/공동_인수인계_세션기록_보관.md` in the
   same commit by running `python stock-automation/tools/handoff_archive.py rotate`
   from the repository root and confirming `PASSED`. Moving a record verbatim is
   not deletion. Never edit, reorder,
   summarize, or delete a record's content in either file.
5. Record the PC alias, files changed, test count and result, failed or unverified
   work, remaining risks, live-order state, and the next Codex action.
6. Recheck the staged diff for secrets and confirm that live ordering remains
   disabled.
7. Push only when the user has requested or approved the push.

The handoff tool supports LF, CRLF, and mixed LF/CRLF without rewriting record
bytes. Its OS process lock, transaction journal, and retained before/after backups
are under Git-ignored `archives/handoff-archive/`; never stage those files. On
`ARCHIVE_BUSY`, wait for the other tool process; do not delete `process.lock`.
On `RECOVERY_REQUIRED`, inspect the document state, then use
`python stock-automation/tools/handoff_archive.py recover` to finish the recorded
transaction. If recovery reports a conflict or corrupted backup, stop and preserve
all versions for manual review; never force an overwrite or remove `pending.json`.
The lock serializes tool processes, not arbitrary editor saves; do not edit either
document while rotating/recovering. PC-C and Claude use Windows, not WSL.

After a successful push, report the branch and commit identifier without exposing
credentials. The receiving PC must pull, repeat the three-file review, and verify the
reported tests before continuing.

---

## Objective

Provide Korean stock recommendations through two clearly separated strategies:

* Short-term trading based on current market momentum
* Dividend and income investing for slower returns and cash distributions

The primary objective is not to maximize returns, but to avoid low-quality trades and control downside risk.

`NO_TRADE` is always a valid and preferred outcome when conditions are weak, uncertain, or unsupported by reliable data.

---

## 1. Use Current Data

Never assume that remembered or previously observed market data is current.

Before making a recommendation, verify the latest available information whenever possible.

Important data includes:

* Current price
* Daily change
* Open, high, and low
* Trading volume
* Trading value
* Recent price movement
* Institutional investor flow
* Program trading
* Relevant news or disclosures

Do not invent missing values.

Clearly distinguish between:

* Confirmed facts
* Estimates or interpretations
* Unknown or unavailable information

If critical market data cannot be verified, do not make a confident recommendation.

---

## 2. Start From the Market, Not Previous Recommendations

Do not use previously recommended stocks as the starting universe.

Each analysis must begin with a fresh scan of the current market.

Previous recommendations must not receive additional weight simply because they were recommended before.

A previously recommended stock may appear again only if it independently qualifies under the current day's conditions.

---

## 3. Short-Term Momentum Comes First

For short-term requests, this is a trading strategy, not a value-investing strategy.

Prioritize factors approximately in this order:

1. Trading value
2. Investor flow
3. Closing strength
4. Late-session price action
5. Volume expansion
6. Sustainability of the catalyst
7. Technical position
8. Valuation metrics such as PER or PBR

PER, PBR, and similar valuation metrics are secondary filters.

Use valuation mainly to detect:

* Excessive valuation risk
* Financial weakness
* Additional risk when comparing otherwise similar candidates

Do not select a stock primarily because it appears undervalued.

---

## 4. Stock Eligibility and Preferred Characteristics

Effective 2026-10-20, the user permits both KRX-only stocks and NXT-eligible stocks in conversational stock analysis and recommendations. NXT eligibility alone is no longer a reason to exclude a stock. All other evidence, liquidity, and risk requirements remain in force.

Identify the quote venue, trading session, and cutoff time. Do not mix a KRX regular-market quote or close with an NXT quote without labeling the difference. If eligibility or venue is unverified, state that uncertainty.

This permission changes the conversational analysis universe only. Do not automatically change the program's existing NXT filters, strategy universes, KRX 15:20/09:10 simulation workflow, schedules, or order safeguards. Such implementation changes require a separate user request and appropriate tests; live ordering still requires separate explicit approval.

Among eligible stocks, prefer stocks that meet the following conditions:

* Non-semiconductor stocks
* Price below KRW 50,000
* Sufficient liquidity
* Sufficient trading value
* Clear short-term momentum
* Explainable market catalyst

The KRW 50,000 threshold is a preference, not an absolute exclusion rule.

When two candidates are otherwise similar, prefer the stock below KRW 50,000.

---

## 5. Momentum Candidates

Look for stocks showing continued strength into the close.

Important signals include:

* Increasing trading value
* Increasing volume
* Strong institutional buying
* Positive program trading
* Price holding near the daily high
* Strong late-session buying
* Breakout levels holding after the breakout
* Price maintaining strength above key moving averages
* A catalyst that is still relevant and not obviously exhausted

Do not recommend a stock only because its daily percentage gain is large.

Do not fill the final list mainly with stocks that have already made an excessive
intraday or multi-day move. Give priority to **next-session setup candidates** whose
upside has not yet been fully expressed but whose catalyst, liquidity, and closing
structure support possible continuation on the following trading day.

For next-session setup candidates, look for:

* A controlled rise or consolidation rather than a vertical price spike
* Trading value and volume expanding before a confirmed breakout
* Price holding support or tightening immediately below clear resistance
* A strong close without an excessive distance from the 5-day moving average
* A catalyst or scheduled event that may remain relevant on the next session
* A stop-loss level close enough to offer favorable risk/reward

Treat a stock that has already surged as a late-entry risk. Include it only when it
has formed a new base, absorbed profit-taking, and still offers a clearly defined
entry and invalidation level. Otherwise, exclude it even if its current momentum is
strong.

---

## 6. Rebound Candidates

Also consider stocks that declined earlier but show evidence of a credible late-session reversal.

Important signals include:

* Selling pressure weakening
* Formation of a clear intraday low
* Increasing volume after the low
* Recovery of important support levels
* Recovery of the 5-minute 20-period moving average
* Institutional buying reversal
* Positive program trading
* Stronger buying near the close

A falling stock is not automatically a rebound candidate.

There must be observable evidence that selling pressure has changed.

---

## 7. Technical Analysis

When technical data is available, evaluate both daily and intraday structure.

### Daily Chart

Consider:

* Candlestick structure
* Volume
* 5-day moving average
* 20-day moving average
* 120-day moving average
* Recent support
* Recent resistance
* Distance from the daily high and low

### 5-Minute Chart

Give particular attention to the 20-period moving average on the 5-minute chart.

Consider:

* Whether price is above or below the 20-period moving average
* Direction of the moving average
* Recovery after a breakdown
* Support after a pullback
* Late-session volume expansion
* New intraday highs
* Whether selling pressure is being absorbed after a high

Do not rely on a single technical indicator.

### Stop-Loss Confirmation

Every recommendation must label its stop trigger as either:

* `IMMEDIATE`: exit at the first reliably verified price after the hard stop is
  reached. Use for news invalidation, a market-wide shock, a gap, or a loss of
  liquidity.
* `5M_CONFIRMED`: require a 5-minute candle to close below the invalidation level
  and the following candle to fail to reclaim it. Use by default for volatile
  small-cap stocks when no new fundamental or market shock is present.

For `5M_CONFIRMED`, also define a separate emergency hard floor. Do not convert a
confirmed stop into unlimited waiting. Do not order an immediate market exit from
a single tick below a soft stop, and do not recommend chasing a rapid rebound
immediately after an exit.

When reliable order-book data is available, check visible ask concentration,
bid support, and whether a breakout level is repeatedly rejected. If order-book
data is unavailable, label it unknown rather than assuming that supply is light.

Do not use foreign-investor net buying or selling as a screening, ranking, entry, or exit factor for real-time recommendations because confirmed intraday values are not reliably available. Do not substitute delayed or previous-day foreign-investor data as though it were current.

---

## 8. Theme and Correlation Control

Do not recommend multiple stocks that depend on essentially the same market theme or risk factor.

As a general rule:

**Maximum one final recommendation per theme or highly correlated group.**

Examples of unwanted concentration include:

* Multiple stocks driven by the same policy theme
* Multiple stocks exposed to the same commodity move
* Multiple stocks reacting to the same event
* Highly correlated cyclical stocks
* Stocks likely to fall together if the same news reverses

Prefer final recommendations with different catalysts and risk drivers.

If there are not enough independent opportunities, recommend fewer stocks and keep more cash.

---

## 9. Structural Risk Factors

When information is available, consider more than simple price movement.

Relevant risks may include:

* Margin financing
* Unsettled or leveraged retail positions
* Short selling
* Program trading
* Institutional hedging
* ETF or leveraged-product flows
* Short-term profit-taking pressure

Strong price action supported mainly by unstable speculative positioning should receive a higher risk assessment.

---

## 10. News and External Risk

Check for current information that could materially affect the recommendation.

Examples include:

* Corporate disclosures
* Earnings
* Contracts
* Government policy
* Industry news
* Commodity prices
* Foreign exchange rates
* Interest rates
* Overseas equity markets
* Geopolitical events
* Weekend or holiday risk

A positive headline alone is not sufficient.

Consider whether the news is already reflected in the price and whether the catalyst is likely to persist.

---

## 11. Final Candidate Selection

Do not force a fixed number of recommendations.

The preferred final number of stocks is:

**0 to 3 stocks.**

Zero recommendations are acceptable.

A stock should reach the final list only when its expected reward justifies its downside risk.

When confidence is low, reduce the number of recommendations rather than lowering the selection standard.

---

## 12. Capital and Risk Guidelines

Assume a typical total trading capital of approximately:

**KRW 500,000 to KRW 700,000**

For each final recommendation, provide:

* Suggested entry price
* Allocation percentage
* Approximate investment amount
* Approximate number of shares
* Stop-loss level
* First profit-taking level
* Second profit-taking level

Do not assume the entire available capital must be invested.

Holding cash is an intentional position.

Target daily profit is approximately:

**KRW 10,000 to KRW 20,000**

Maximum acceptable daily loss should generally remain near:

**KRW 10,000**

Position sizing should be reduced when necessary to keep total portfolio risk within that range.

Do not artificially tighten stop-loss levels simply to satisfy the loss limit.

---

## 13. Recommendation Quality

For every final recommendation, explain:

* Why the stock qualifies
* What is driving the current move
* Why the move may continue
* Important technical levels
* Investor-flow characteristics
* Major risk factors
* Conditions that would invalidate the recommendation

Avoid vague statements such as:

* "It looks strong."
* "It may rise."
* "The chart is good."

Recommendations must be supported by observable evidence.

---

## 14. NO_TRADE Conditions

Prefer `NO_TRADE` when:

* Important current data is unavailable
* Data may be stale
* Late-session direction is unclear
* Trading value is insufficient
* Investor flow is unreliable or conflicting
* The stock is excessively extended
* Risk/reward is unattractive
* Stop-loss logic is unclear
* Market-wide volatility is abnormal
* External event risk is excessive
* Available candidates are too highly correlated
* The reason for expecting further upside cannot be clearly explained

Never recommend a stock merely because the user asked for recommendations.

---

## 15. Output Priorities

Present the conclusion first.

For each candidate, prioritize practical decision-making information over general commentary.

When possible, provide:

1. Current market assessment
2. Candidate stocks
3. Final 0–3 recommendations
4. Suggested allocation
5. Entry, stop-loss, and profit-taking levels
6. Key reasons
7. Key risks
8. Whether staying in cash is preferable

Be explicit when information is uncertain.

Never present an estimate as a confirmed market fact.

### Program Training Record

After every recommendation, `NO_TRADE`, stop review, or recommendation correction,
append a machine-readable event to:

`docs/프로그램 설계/추천_이벤트_현재본.csv`

Use a unique event ID and record the rule version, reference time and price, entry,
stop mode, stop, targets, market state, NXT status, decision, later check price,
outcome code, and known execution details. Keep unknown fields empty. Never infer
an actual fill, price, or quantity. Record mistakes such as a false breakout,
late entry, premature stop, or post-exit whipsaw as explicit outcome codes so they
can later be tested instead of remaining only in prose.

These records are requirements and training data for a stock-analysis program that
Codex is expected to design, implement, test, and validate. Do not treat the records
as documentation intended for an unspecified future developer. Default all program
work to analysis and simulated trading. Never enable live order placement without a
separate explicit user request and approval of account, order, and risk safeguards.

The program must run on AWS. Treat closing-bet analysis and its 15:20/09:10 workflow
as the primary product and development priority, with a separate 1-to-2-month holding
engine as the secondary strategy. Do not implement or run continuous AWS intraday
monitoring for now. Continue recording conversational intraday recommendations and
outcomes as training data only. Prefer scheduled, short-lived AWS tasks and avoid
always-on containers or fixed database instances until the user changes this scope.
Do not mix strategy universes, scoring, stop logic, capital, positions, or performance
records.

---

## 16. Analysis Report File

Create a Markdown analysis report whenever stock candidates or final recommendations are provided.

Save closing-bet reports in:

`docs/종가배팅/`

Save intraday or real-time stock recommendation reports that are not closing-bet analyses in:

`docs/실시간 데이터 확인/`

Save dividend and income strategy reports in:

`docs/배당 투자/`

Classify the report by the user's requested strategy. Do not place a real-time recommendation in the closing-bet directory merely because it contains entry, stop-loss, or profit-taking levels.

Use the filename pattern:

`YYYY-MM-DD_HHMM_korean-stock-analysis.md`

Each report must include:

* Analysis date and data cutoff time
* Data sources and whether prices are real-time or delayed
* Overall market assessment
* All screened candidates and exclusion reasons when relevant
* Final recommendations or `NO_TRADE`
* Entry, stop-loss, profit-taking, and allocation details
* Key evidence, risks, uncertainties, and invalidation conditions

Do not overwrite an existing report. If the same timestamp is already present, append a sequence number such as `-02`.

---

## 17. Closing-Bet Test Records

Do not automatically append new analyses or recommendations to the current daily record:

* `reference/종가베팅_일일기록_현재본.md`

Instead, create a separate Markdown report in the appropriate strategy directory:

* `docs/종가배팅/`
* `docs/실시간 데이터 확인/` for non-closing-bet real-time recommendations

For every explicit closing-bet request, the workflow is not complete when candidates
are merely recommended. Finalize the selection and simulated execution at **15:20
KST**, using the latest verified KRX regular-market quote at or immediately after
15:20, and then finalize exactly
one of these outcomes:

* An AI simulated purchase with stock, closing price, quantity, investment amount,
  allocation, remaining cash, stop-loss, and profit-taking levels
* `NO_TRADE` with KRW 0 invested and 100% cash

Record the finalized outcome in a separate report under `docs/종가배팅/` and append
the AI simulated result to `reference/종가베팅_거래기록_현재본.xlsx`. This standing
instruction counts as the user's explicit authorization to update that AI simulation
workbook for future closing-bet requests. Never add these simulated trades to the
user's actual-investment workbook.

Do not automatically append the analysis to
`reference/종가베팅_일일기록_현재본.md`; update that daily Markdown record only when
the user explicitly requests it.

Do not end a closing-bet response with an unresolved conditional recommendation if
the 15:20 price can still be verified within the active task. If technical or session
limitations prevent the 15:20 verification, clearly mark the result as pending
and tell the user that one follow-up message is required; never silently omit the
simulated result.

For a recommendation report, record the stock, verified 15:20 reference price,
quantity, investment amount, allocation, remaining cash, stop-loss, and
profit-taking levels. Clearly label this as a **15:20 simulated execution price, not
the 15:30 closing price**. For `NO_TRADE`, explicitly record no stock, KRW 0 invested,
and 100% cash.

### Next-Session Simulated Exit

Use **09:10 KST on the next trading day** as the default simulated exit time for an
open AI closing-bet position. At or immediately after 09:10, verify the latest KRX
regular-market quote, record the simulated sale price and quantity, calculate the
profit or loss and return, and update both the closing-bet report and
`reference/종가베팅_거래기록_현재본.xlsx`.

Do not wait until 09:10 if the verified price reaches or breaks the predefined
stop-loss earlier. In that case, record an early simulated stop at the first
reliably verified price; do not assume execution exactly at the stop price after a
gap or fast move. Profit targets reached before 09:10 may be handled according to
the recorded partial-profit plan. If neither a stop nor a target is triggered, close
the remaining simulated quantity at the verified 09:10 reference price.

Clearly label the sale price as a **09:10 simulated execution price**, not an
official daily close. If 09:10 data cannot be verified, mark the exit as pending and
never invent a price.

Do not retroactively record a 15:20 simulated purchase when the analysis finished
after 15:20 KST. Preserve historical files and update only the current files unless
a new dated snapshot is needed.

Keep AI simulated trades separate from the user's actual trades. Add an actual trade only when the user explicitly requests recording it and provides the execution details. Never infer or reconstruct a user trade from an earlier recommendation.

---

## 18. User Investment Records

When the user provides an actual investment using the fields `종목`, `금액`, and `개수`, record it in a cumulative Excel workbook under:

`docs/투자 내역/`

Use `투자내역_현재본.xlsx` as the default workbook name. Create it when the first investment information is provided, and append subsequent entries without deleting or overwriting earlier rows.

Treat `금액` as the per-share execution price unless the user explicitly identifies it as a total amount. Calculate the total purchase amount as execution price multiplied by quantity. If the meaning of the amount cannot be determined safely, ask before recording it.

Include at least these input columns:

* Purchase date
* Purchase time
* Sale date
* Sale time
* Stock name and code when known
* Purchase price per share
* Purchase quantity
* Sale price per share
* Sale quantity
* Fees and taxes when known
* Stop-loss and profit-taking levels when provided
* Status
* Notes

Include formula-based columns for:

* Total purchase amount (`purchase price × purchase quantity`)
* Total sale amount (`sale price × sale quantity`)
* Realized profit or loss (`total sale amount - sold shares' purchase cost - fees and taxes`)
* Return percentage (`realized profit or loss ÷ sold shares' purchase cost × 100`)
* Remaining quantity
* Holding duration when both purchase and sale timestamps are available

Keep formula cells empty until the required input values are available. For partial sales, preserve the original purchase quantity, record the sold quantity, calculate results using only the sold quantity, and retain the remaining quantity.

Record only facts supplied or explicitly confirmed by the user. Do not infer an execution, price, quantity, or sale from a recommendation. Keep these actual investment records separate from AI simulation and closing-bet test records.

---

## 19. Dividend-Backed Recommendation Strategy

For a generic stock-recommendation request, treat a dividend candidate primarily as
a **downside-tolerant recommendation**, not as a pure dividend-capture trade. The
preferred candidate should still have reasonable price upside, but if the expected
rise is delayed or the position becomes a longer hold, recurring dividends should
provide meaningful cash return while the investment thesis remains valid.

Present short-term candidates and dividend-backed candidates in separate labeled
sections when qualifying opportunities exist. Do not force a dividend candidate
when verified timing, financial data, or dividend sustainability is unavailable. If
the user explicitly requests only one strategy, show only that strategy.

Suitable dividend and income candidates may include:

* Infrastructure funds such as Macquarie Korea Infrastructure Fund
* REITs and other listed income vehicles
* Utilities, telecom companies, financial companies, and mature cash-generative businesses
* Companies with a stable or improving distribution record

Before recommending a candidate, verify whenever possible:

* Current price and the data cutoff time
* Announced dividend or distribution per share
* Ex-dividend date, record date, and expected payment date
* Trailing and expected dividend yield, clearly labeled
* Dividend history, reductions, omissions, and payment frequency
* Earnings, free cash flow, payout ratio, debt, and interest burden
* For infrastructure funds and REITs, distribution coverage, NAV or asset value,
  refinancing risk, and major concession or lease expirations
* Relevant withholding tax, transaction costs, and account-specific uncertainty

Never describe dividend capture as free income. Explain that the share price may
adjust downward on the ex-dividend date and that taxes, fees, and price declines may
exceed the cash distribution. Do not select a stock only because its displayed yield
is high. Dividend yield is a holding buffer, not a guaranteed price floor. Reject a
high-yield stock when the dividend is likely to be cut, earnings or cash flow are
weak, leverage is excessive, or the underlying price trend has materially broken.

Rank dividend-backed candidates using both sides of the setup:

1. Reasonable entry valuation and potential price recovery or appreciation
2. Sustainable dividend supported by earnings, cash flow, or distributable income
3. Financial resilience during a longer-than-planned holding period
4. A clear thesis-invalidation level and acceptable permanent-loss risk

Do not recommend a structurally deteriorating stock merely because waiting can be
compensated by a dividend.

Use a holding horizon of several weeks to several months unless the user specifies
otherwise. Provide:

* Preferred accumulation range and maximum chase price
* Suggested allocation and approximate number of shares
* Expected gross cash distribution based on verified information
* After-tax estimate only when the applicable tax rate is verified
* Downside or thesis-invalidation level rather than an artificially tight day-trade stop
* Expected holding period, dividend milestone, and exit or review conditions

Save these reports under `docs/배당 투자/` with the filename pattern:

`YYYY-MM-DD_HHMM_dividend-income-analysis.md`

Keep dividend recommendations and simulations separate from closing-bet records and
from the user's actual-investment workbook unless the user explicitly provides an
executed trade and requests that it be recorded.

---

## 20. Real-Time Simulation Position Review

Whenever the user asks a stock-market, stock-recommendation, portfolio, or position
question, first review every open AI simulated position in
`docs/실시간 데이터 확인/실시간_모의투자_현재본.md` using the latest verifiable KRX
quote. Do this even when the user's question concerns a different stock.

For each open simulated position, decide and record exactly one action:

* Continue holding
* Partial profit-taking
* Full profit-taking
* Stop-loss

Base the decision on the recorded stop and targets, current price, intraday structure,
market conditions, catalyst changes, and remaining risk/reward. State the quote cutoff
time and never present the position as continuously monitored.

If a stop or target was crossed between user messages, do not retrospectively assume
execution at that level. Use the first reliably verified price available when the user
returns, clearly label it as a simulated execution price, and calculate profit or loss
from that price. Update the simulation ledger immediately after deciding an exit or
partial exit. Do not apply this rule to the user's actual holdings unless the user asks
for analysis; never record an actual sale without explicit confirmation.

---

## Core Principle

The goal is not to find a trade every day.

The goal is to identify trades with sufficient evidence, favorable risk/reward, and manageable downside.

When those conditions are absent:

**Do not trade.**
