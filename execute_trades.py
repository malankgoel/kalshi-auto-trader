"""Compatibility wrapper for the World Cup trader CLI.

Prefer the installed ``kalshi-world-cup`` command for new automation.
"""

from kalshi_auto_trader.world_cup.trader import main as world_cup_main


def main() -> None:
    """Run the World Cup strategy through the legacy script path."""
    world_cup_main()


if __name__ == "__main__":
    main()
