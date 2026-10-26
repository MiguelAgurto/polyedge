# Weather trader research watchlist

Snapshot: **2026-10-12, approximately 16:20 UTC**. This is a research shortlist, not a copy-trading signal.

## How this was checked

I read the public [Polymarket weather P&L leaderboard](https://polymarket.com/leaderboard/weather/all/profit) for all time, month, and week using the [Data API v2 leaderboard](https://data-api.polymarket.com/v2/leaderboard?time_period=all&category=weather&sort_by=PNL&limit=100). The API defines **all-time P&L as realized** and finite windows as changes in marked equity, so the columns are not directly interchangeable. I also checked each wallet's public profile statistics and **latest 200 fills** with the [v2 trades API](https://data-api.polymarket.com/v2/trades). Recent-fill counts below are a sample, not a full strategy backtest. Public [wallet activity](https://docs.polymarket.com/trading/wallet-activity) distinguishes closed, realized positions from open positions and exposes fill price, side, size, and timestamp.

## Traders worth studying

| Trader | Weather P&L rank: all / month / week | Recent 200 fills | Why study them | Main obstacle to copying |
| --- | --- | --- | --- | --- |
| [TunSahur](https://polymarket.com/profile/0x95d381e71dba6f1c3199fd9bc040383d6fae6eff) | 77 / 7 / 9 | 182 highest-temperature fills across 85 markets in 0.6 days | Best **paper-copy candidate** here: positive across all three windows, active in our contract type, and recent BUYs include both YES and NO without buying both sides of the same market in this sample. | The pace is high; a follower must compare their own ask and available size, not assume the trader's fill is still available. |
| [badatmath.](https://polymarket.com/profile/0x8fbd7cf5f806f563080864694415829f7229a959) | 14 / 3 / 2 | 200 highest-temperature fills across 58 markets over 2.4 days | Strong **strategy-study candidate**: recent and longer-run weather results, clearly focused on daily temperature contracts. | Roughly 299,000 lifetime fills plus maker rebates and rewards. Recent BUYs included both YES and NO in nine markets, so copying one visible leg may miss the full strategy. |
| [HighTempTation](https://polymarket.com/profile/0x6011655c4afb76f36dd1b08a137a1ba73466b31e) | 7 / 6 / 17 | 110 highest-temperature fills across a 200-fill sample; 93 distinct markets | Stronger all-time record, recent activity, and very little maker-rebate income. Study the timing of its high-confidence weather entries. | Of 93 sampled BUYs, 91 were NO and 82 cost at least **90¢**; median BUY was **97.4¢**. Even a small delay or fee can remove the remaining upside. Many fills are lowest-temperature markets outside PolyEdge's model. |
| [OutOfMemory](https://polymarket.com/profile/0x5bae7577f470244ce8e678d20693eee2b8ffed25) | outside top 100 / 11 / 7 | 200 highest-temperature fills across 78 markets in 0.5 days; 190 BUY fills | Active, concentrated temperature strategy with no reported maker rebates or reward income in the wallet profile snapshot. | Recent BUYs included both outcomes in 13 markets, suggesting portfolio context matters. Its strong leaderboard showing is recent, and the fast pace makes follower fill prices uncertain. |

### Secondary checks

- [WrongBy1Degree](https://polymarket.com/profile/0x0a0c42f6b1da5a633ec1a4d45ba76eb486c1a853): month #25 and week #13, with 200 recent sampled fills all BUYs in highest-temperature markets. Worth tracking for market selection, but outside the all-time weather top 100 and not yet a strong copy candidate.
- [Bilberry](https://polymarket.com/profile/0xbf13934a1fec7d3211fc15c138d84ac2a691b91a): all-time #39 and month #1, but outside the weekly top 100 at this snapshot. Review whether the monthly gain came from a small number of positions before drawing a conclusion.

### A concrete disagreement to track

At **16:21 UTC on October 12**, TunSahur's public feed showed a BUY of YES at **45¢** on [Seoul (Incheon) reaching 22°C on October 13](https://polymarket.com/event/highest-temperature-in-seoul-on-october-13-2026). PolyEdge's independent check at 16:23 UTC estimated a **17.9%** nominal YES chance but issued **NO BUY** after uncertainty and price checks. This is a useful paper-trading case: record the first price a follower could actually get, then compare both views with the official settled result. The disagreement is not proof that either trader or model is right.

### Headline leaders I would set aside for this test

- [gopfan2](https://polymarket.com/profile/0xf2f6af4f27ec2dcf4072095ab804016e14cd5817) is #1 on the all-time weather board, but none of the latest 200 sampled fills were highest-temperature contracts; the sample included political markets. The old result is not enough to copy a current weather strategy.
- [erghr](https://polymarket.com/profile/0xe8381d4226f67bdd6fdc447c2406e4c0f5082b52) is #1 weekly, but the profile shows only **three distinct markets** traded. That sample is too small to judge repeatability.

## What would make a trader followable

For a paper test, record each newly observed BUY with its publication time, the trader's fill price, **our** first available ask and size, fee, and eventual resolution. Count a copy only if it could have filled at our quoted price. Separate first entries from later adds, sells, and near-resolution buys. Compare paper results over many settled markets, and measure how often the trader's chosen side agrees with PolyEdge's independent weather estimate. A leaderboard rank alone cannot answer whether a delayed follower has an edge.
