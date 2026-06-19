"""Compatibility wrapper for the World Cup trader CLI."""

from kalshi_auto_trader.world_cup.trader import main as world_cup_main


def main() -> None:
    """Run the World Cup strategy through the legacy script path."""
    world_cup_main()


if __name__ == "__main__":
    main()
