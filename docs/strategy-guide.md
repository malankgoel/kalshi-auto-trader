# Strategy Guide

Use this layout when adding another prediction app, such as a new tournament,
sport, or event category.

## Keep Shared Kalshi Logic Shared

Reuse these modules instead of copying API or bookkeeping code:

| Module | Use |
|---|---|
| `kalshi_auto_trader.kalshi` | Public market discovery, authenticated account reads, and order submission. |
| `kalshi_auto_trader.orders` | Contract sizing, market/limit order parameters, and stable client order IDs. |
| `kalshi_auto_trader.probability` | Shared probability validation and quote conversion helpers. |
| `kalshi_auto_trader.ledger` | CSV trade logging, settlement updates, and bankroll recovery. |
| `kalshi_auto_trader.risk` | Run-level spend cap accounting. |
| `kalshi_auto_trader.settings` | Environment-backed runtime, auth, order, and risk settings. |
| `kalshi_auto_trader.text` | Shared text normalization for identifiers, paths, and optional CLI values. |

Shared client helpers validate API paths, market tickers, order tickers, and
client order IDs before making requests. Strategy packages should pass trimmed,
non-empty identifiers into those helpers rather than preparing raw URL paths.
Order pricing helpers centralize limit buffers, market spend caps, and estimated
cost math. Model helpers also treat nonfinite numeric inputs as invalid, so
strategy code should normalize raw feeds before planning bets.
Ledger helpers expose settlement result parsing, pending-status checks, and
profit math so strategy packages do not need to duplicate bankroll accounting.

## Keep Strategy Logic Isolated

Create a strategy package under `kalshi_auto_trader/<strategy_name>/` for:

- a `STRATEGY` metadata object declared with `StrategyMetadata`
- model input files and path config
- market-series identifiers and matching rules
- model probability normalization and edge detection
- CLI options specific to that strategy
- printed plan formatting specific to the strategy's bet types

The World Cup app in `kalshi_auto_trader/world_cup/` is the current reference.
When adding a CLI, keep argument normalization, environment selection, and auth
checks in small helpers so they can be tested without placing orders.
