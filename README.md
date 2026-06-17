# Kalshi Auto-Trader

Self-contained bot that bets the next World Cup game on Kalshi using the
pre-tournament model's edges.

It carries its own copy of the model: the pre-tournament forecast
(`data/world_cup/match_predictions.csv`) and the schedule
(`data/world_cup/schedule_2026.csv`). It does **not** read the model repo's
`tally.csv` or any other external file — every
run it recomputes from scratch:

```
next game (bundled schedule + forecast)
      └─► settle any logged prior bets from Kalshi results
            └─► pull that game's CURRENT Kalshi odds
                  └─► de-vig, flag every ≥10% mispricing  (same rule as the backtest)
                        └─► size with half-Kelly from the updated ledger bankroll
                              └─► place the orders and append the CSV log
```

So you run it before a game, and it does live what the tally used to do offline —
then places the trades.

---

## Safety first (read this)

- **Dry-run is the default.** With no flags it pulls odds, flags bets, sizes, and
  prints the plan — but sends nothing. Add `--live` to actually place orders.
- **Hard caps** on every live run regardless of model stake: max contracts/order,
  max $/order, max $/run, plus a balance check that aborts before placing if the
  plan exceeds your cash.
- **Idempotent order IDs.** Each order uses a deterministic
  `client_order_id` derived from the game + selection, so re-running before
  kickoff can't double-place — Kalshi rejects the duplicate. (Caveat: if the odds
  move between runs the bet is still placed only once, at the first run's size.)
- **Persistent trade log.** Successful live/demo submissions are appended to
  `data/world_cup/trade_log.csv`. On the next run the bot checks pending logged
  tickers for settlement, writes win/loss/profit, and sizes the next game from
  the updated logged bankroll.
- **Practice with `--demo`** on Kalshi's demo exchange before going live.
- Trading risks real money. With this few bets the results are mostly noise.
  You own every order this places. Start tiny.

---

## Setup

```bash
cd kalshi-auto-trader
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Auth (needed for `--live` and `--demo`; download an RSA API key from your Kalshi
account → Settings → API):

```bash
export KALSHI_API_KEY_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
export KALSHI_PRIVATE_KEY_PATH="/path/to/kalshi_private_key.pem"
```

---

## Usage

```bash
python3 execute_trades.py                      # dry-run, next game, market orders
python3 execute_trades.py --order-type limit   # dry-run, limit pricing
python3 execute_trades.py --demo --live        # place on the demo exchange
python3 execute_trades.py --live               # place for real

python3 execute_trades.py --home France --away Senegal   # a specific fixture
python3 execute_trades.py --match-id 21                  # by schedule id
python3 execute_trades.py --bankroll 200                 # override Kelly bankroll
python3 execute_trades.py --max-total 20                 # tighter run cap
```

The next game is the earliest scheduled fixture that hasn't kicked off and has a
pre-tournament prediction (knockout games with TBD teams are skipped until set).

---

## Market vs. limit — the one switch

Default once via `KALSHI_ORDER_TYPE`, or per run with `--order-type`. Sizing is
identical; only the price field sent to Kalshi changes:

| Type | How it prices | Trade-off |
|---|---|---|
| `market` | Fills now at best available; `buy_max_cost = count × (ask + MARKET_SLIPPAGE_CENTS)` caps spend so a thin book can't fill far above the quote. | Certain fill, some slippage. |
| `limit` | Posts a limit at `ask + LIMIT_BUFFER_CENTS` (clamped 1–99¢) on the side being bought. | Controls price; may not fill if the market moves. |

```bash
export KALSHI_ORDER_TYPE=limit   # make limit the default
```

---

## How a bet becomes an order

The model flags mispricings on three lines and the trader maps each to a contract:

| Line | Rule (vs de-vigged market) | Order |
|---|---|---|
| **Match winner** (3-way) | model − market ≥ 10% → back; ≤ −10% → fade | Buy that team's "to win" market: `YES` to back, `NO` to fade. Draw evaluated the same way. |
| **Over/Under 2.5** | model over% vs market over% | Over-2.5 market: `YES` = over, `NO` = under. |
| **Both teams to score** | model BTTS% vs market BTTS% | BTTS-Yes market: `YES` = both score, `NO` = not both. |

Stake = `bankroll × min(½ × fullKelly, 25%)`; contracts = ⌊ stake ÷ side-ask ⌋,
clamped to the caps. **Bankroll** comes from the CSV ledger after settled prior
trades, starting at the `BANKROLL` config default. `--bankroll` overrides sizing
for that run. Live mode still checks your actual Kalshi cash balance before
placing.

---

## Trade log and bankroll

`data/world_cup/trade_log.csv` is one row per successfully submitted live/demo
order. It records the model probability, de-vigged market fair probability, raw
market price, quoted ask, recommended stake, starting bankroll for the run,
submitted order price, order id, and settlement fields.

Before every run, the bot reads pending rows and calls Kalshi for the logged
market tickers. If Kalshi reports a YES/NO result, the row is marked won/lost,
profit is calculated from the logged placed price and contract count, and
`bankroll_after` becomes the sizing bankroll for later games. Rows stay pending
until Kalshi exposes a settled result.

---

## Configuration

Reusable Kalshi/runtime settings live in `kalshi_auto_trader/settings.py`.
World Cup-specific data paths and market series live in
`kalshi_auto_trader/world_cup/config.py`.

| Env var | Default | Meaning |
|---|---|---|
| `KALSHI_ORDER_TYPE` | `market` | `market` or `limit` |
| `EDGE_THRESHOLD` | `0.10` | min model-vs-market edge to bet |
| `KELLY_FRACTION` | `0.50` | fraction of full Kelly (half-Kelly) |
| `MAX_STAKE_FRACTION` | `0.25` | cap per bet, share of bankroll |
| `BANKROLL` | `50` | starting/fallback ledger bankroll |
| `KALSHI_TRADE_LOG_FILE` | `data/world_cup/trade_log.csv` | CSV ledger used for logging, settlement, and bankroll tracking |
| `MAX_ORDER_COST` | `25` | max $ on a single order |
| `MAX_TOTAL_COST` | `100` | max $ across one run |
| `MAX_CONTRACTS_PER_ORDER` | `500` | hard contract cap per order |
| `LIMIT_BUFFER_CENTS` | `2` | limit price = ask + this |
| `KALSHI_MARKET_SLIPPAGE_CENTS` | `3` | market `buy_max_cost` headroom |

---

## Tests

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest tests/ -q
```

Fully offline (no network, no keys): de-vig, edge flagging, Kelly, sizing/caps,
market+limit params, price extraction, bet→market mapping, and an end-to-end
`plan_bets` check against an injected fake client.

---

## Repository layout

| Path | Role |
|---|---|
| `execute_trades.py` | Backward-compatible CLI wrapper for the World Cup app. |
| `kalshi_auto_trader/kalshi/client.py` | Reusable Kalshi REST client: signed reads/writes, orders, balance. |
| `kalshi_auto_trader/orders.py` | Reusable order sizing, price fields, and idempotent client order IDs. |
| `kalshi_auto_trader/ledger.py` | Reusable CSV order ledger and settlement/bankroll logic. |
| `kalshi_auto_trader/settings.py` | Shared env-overridable runtime, risk, auth, and order settings. |
| `kalshi_auto_trader/world_cup/` | World Cup-specific model, market matching, config, and CLI planning. |
| `data/world_cup/` | Bundled World Cup model snapshot, schedule, and empty trade-log header. |
| `tests/` | Offline unit + integration tests. |

For a future strategy, add a new package under `kalshi_auto_trader/<strategy>/`
with its own config/model/market mapping. Reuse `KalshiClient`, `orders`, and
`ledger` rather than copying Kalshi API or bookkeeping code.

---

## Updating the model data

`data/world_cup/match_predictions.csv` is the **pre-tournament** snapshot
(trained through 2026-06-10) on purpose — edges are measured against a model
that hasn't seen any results, so they aren't inflated by hindsight. Replace it
only if you genuinely want a different model; keep the same columns.
