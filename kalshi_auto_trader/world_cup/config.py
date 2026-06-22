"""World Cup strategy configuration and bundled data paths."""

from __future__ import annotations

from pathlib import Path

from kalshi_auto_trader import settings

DATA_DIR = Path(settings.REPO_ROOT) / "data" / "world_cup"

# The pre-tournament forecast: trained on data through 2026-06-10, before any
# 2026 World Cup match was played. This is the model the edges are measured
# against; a later hindsight-refit snapshot would inflate the "edge".
PREDICTIONS_FILE = DATA_DIR / "match_predictions.csv"
SCHEDULE_FILE = DATA_DIR / "schedule_2026.csv"

TRADE_LOG_FILE = settings.TRADE_LOG_FILE or DATA_DIR / "trade_log.csv"

# 2026 World Cup per-match series. Must match the wording Kalshi uses.
KALSHI_SERIES = {
    "winner": ("KXWCGAME",),
    "over_under": ("KXWCTOTAL",),
    "btts": ("KXWCBTTS",),
}
