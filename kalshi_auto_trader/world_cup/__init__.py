"""World Cup strategy app."""

from kalshi_auto_trader.strategy import StrategyMetadata

STRATEGY_NAME = "world_cup"
STRATEGY = StrategyMetadata(
    name=STRATEGY_NAME,
    package=__name__,
    description="World Cup fixture prediction strategy",
)

__all__ = ["STRATEGY", "STRATEGY_NAME"]
