"""The model side of the trader: bundled pre-tournament forecast + the exact
mispricing rules the backtest uses.

Self-contained -- reads only the CSVs in ``data/`` (no parent repo). Given a
fixture and a row of current Kalshi YES prices (in cents), it de-vigs the market
and returns the >=10% mispricings as bets, each already sized with half-Kelly.
"""

from __future__ import annotations

import csv
import datetime as dt
import math
from dataclasses import dataclass
from os import PathLike
from typing import Optional

from kalshi_auto_trader import probability, settings
from kalshi_auto_trader.text import normalize_optional_text
from kalshi_auto_trader.world_cup import config, markets


__all__ = [
    "Bet",
    "AWAY_TEAM_KEY",
    "BTTS_LINE",
    "BTTS_NO_SELECTION",
    "BTTS_YES_SELECTION",
    "DATE_KEY",
    "DRAW_SELECTION",
    "GROUP_KEY",
    "HOME_TEAM_KEY",
    "KICKOFF_UTC_KEY",
    "MATCH_ID_KEY",
    "MODEL_BTTS_KEY",
    "MODEL_AWAY_WIN_KEY",
    "MODEL_DRAW_KEY",
    "MODEL_HOME_WIN_KEY",
    "MODEL_OVER_2_5_KEY",
    "NO_SELECTION_PREFIX",
    "PRED_AWAY_TEAM_KEY",
    "PRED_AWAY_WIN_VALUE_KEY",
    "PRED_AWAY_WIN_KEY",
    "PRED_BTTS_KEY",
    "PRED_BTTS_VALUE_KEY",
    "PRED_DRAW_VALUE_KEY",
    "PRED_DRAW_KEY",
    "PRED_GROUP_VALUE_KEY",
    "PRED_GROUP_KEY",
    "PRED_HOME_TEAM_KEY",
    "PRED_HOME_WIN_VALUE_KEY",
    "PRED_HOME_WIN_KEY",
    "PRED_MATCH_ID_VALUE_KEY",
    "PRED_MATCH_ID_KEY",
    "PRED_OVER_2_5_VALUE_KEY",
    "PRED_OVER_2_5_KEY",
    "PRED_UNDER_2_5_VALUE_KEY",
    "PRED_UNDER_2_5_KEY",
    "SCHEDULE_AWAY_TEAM_KEY",
    "SCHEDULE_DATE_KEY",
    "SCHEDULE_HOME_TEAM_KEY",
    "SCHEDULE_TIME_KEY",
    "SCHEDULE_UTC_OFFSET_KEY",
    "YES_SELECTION_PREFIX",
    "OVER_2_5_SELECTION",
    "OVER_UNDER_LINE",
    "UNDER_2_5_SELECTION",
    "WINNER_LINE",
    "devig_binary",
    "devig_three_way",
    "find_game",
    "flag_bets",
    "fixture_identity",
    "fixture_selector_matches",
    "fixture_selector_supplied",
    "fixture_team_keys",
    "fixture_team_selector_complete",
    "fixture_metadata_keys",
    "game_row_identity",
    "game_row_identity_keys",
    "game_row_fixture_key",
    "game_row_has_required_keys",
    "game_row_keys",
    "game_row_kickoff_utc",
    "game_row_match_id",
    "game_row_missing_keys",
    "game_row_model_keys",
    "game_row_model_values",
    "game_row_sort_key",
    "game_row_team_values",
    "game_key",
    "kelly_fraction",
    "matches_fixture",
    "kickoff_utc",
    "load_predictions",
    "load_schedule",
    "meets_edge_threshold",
    "model_probability_keys",
    "next_game",
    "normalize_fixture_selector",
    "parse_kickoff_utc",
    "prediction_loaded_metadata_keys",
    "prediction_loaded_row_keys",
    "btts_selection_labels",
    "build_game_row",
    "prediction_fixture_teams",
    "prediction_loaded_value_keys",
    "prediction_metadata_keys",
    "prediction_game_metadata",
    "prediction_matches_id",
    "prediction_metadata_key_map",
    "prediction_model_values",
    "prediction_probability_keys",
    "prediction_row_metadata",
    "prediction_row_key",
    "prediction_source_row_keys",
    "prediction_team_keys",
    "prediction_to_game_metadata_key_map",
    "prediction_to_model_key_map",
    "prediction_value_key_map",
    "prediction_value_keys",
    "prediction_row_values",
    "schedule_row_date",
    "schedule_row_key",
    "schedule_row_kickoff_utc",
    "schedule_metadata_keys",
    "schedule_fixture_teams",
    "schedule_game_metadata",
    "schedule_source_row_keys",
    "schedule_team_keys",
    "schedule_timing_values",
    "schedule_to_game_metadata_key_map",
    "staked_fraction",
    "strategy_line_names",
    "totals_selection_labels",
    "upcoming_games",
    "winner_model_keys",
    "winner_selection_labels",
]


AWAY_TEAM_KEY = "away_team"
BTTS_LINE = "btts"
BTTS_NO_SELECTION = "BTTS NO"
BTTS_YES_SELECTION = "BTTS YES"
DATE_KEY = "date"
DRAW_SELECTION = "Draw"
GROUP_KEY = "group"
HOME_TEAM_KEY = "home_team"
KICKOFF_UTC_KEY = "kickoff_utc"
MATCH_ID_KEY = "match_id"
MODEL_BTTS_KEY = "model_btts"
MODEL_AWAY_WIN_KEY = "model_away_win"
MODEL_DRAW_KEY = "model_draw"
MODEL_HOME_WIN_KEY = "model_home_win"
MODEL_OVER_2_5_KEY = "model_over_2_5"
NO_SELECTION_PREFIX = "NO"
PRED_AWAY_TEAM_KEY = "away_team"
PRED_AWAY_WIN_VALUE_KEY = "away_win"
PRED_AWAY_WIN_KEY = "away_win"
PRED_BTTS_KEY = "both_teams_to_score"
PRED_BTTS_VALUE_KEY = "btts"
PRED_DRAW_VALUE_KEY = "draw"
PRED_DRAW_KEY = "draw"
PRED_GROUP_VALUE_KEY = "group"
PRED_GROUP_KEY = "group"
PRED_HOME_TEAM_KEY = "home_team"
PRED_HOME_WIN_VALUE_KEY = "home_win"
PRED_HOME_WIN_KEY = "home_win"
PRED_MATCH_ID_VALUE_KEY = "match_id"
PRED_MATCH_ID_KEY = "match_id"
PRED_OVER_2_5_VALUE_KEY = "over_2_5"
PRED_OVER_2_5_KEY = "over_2_5"
PRED_UNDER_2_5_VALUE_KEY = "under_2_5"
PRED_UNDER_2_5_KEY = "under_2_5"
SCHEDULE_AWAY_TEAM_KEY = "away_team"
SCHEDULE_DATE_KEY = "date"
SCHEDULE_HOME_TEAM_KEY = "home_team"
SCHEDULE_TIME_KEY = "time"
SCHEDULE_UTC_OFFSET_KEY = "utc_offset"
YES_SELECTION_PREFIX = "YES"
OVER_2_5_SELECTION = "OVER 2.5"
OVER_UNDER_LINE = "over_under"
UNDER_2_5_SELECTION = "UNDER 2.5"
WINNER_LINE = "winner"


def strategy_line_names() -> tuple[str, ...]:
    """Return strategy line identifiers emitted by this model."""
    return (WINNER_LINE, OVER_UNDER_LINE, BTTS_LINE)


def totals_selection_labels() -> tuple[str, str]:
    """Return the YES/NO-facing labels for the 2.5-goals line."""
    return (OVER_2_5_SELECTION, UNDER_2_5_SELECTION)


def btts_selection_labels() -> tuple[str, str]:
    """Return the YES/NO-facing labels for both-teams-to-score."""
    return (BTTS_YES_SELECTION, BTTS_NO_SELECTION)


def winner_selection_labels(label: str) -> tuple[str, str]:
    """Return the YES/NO-facing labels for one winner outcome label."""
    return (f"{YES_SELECTION_PREFIX} {label}", f"{NO_SELECTION_PREFIX} {label}")


def winner_model_keys() -> tuple[str, str, str]:
    """Return game-row model probability keys for three-way winner outcomes."""
    return (MODEL_HOME_WIN_KEY, MODEL_DRAW_KEY, MODEL_AWAY_WIN_KEY)


def model_probability_keys() -> tuple[str, ...]:
    """Return every game-row model probability key consumed by flag_bets."""
    return winner_model_keys() + (MODEL_OVER_2_5_KEY, MODEL_BTTS_KEY)


def fixture_team_keys() -> tuple[str, str]:
    """Return game-row keys identifying the two fixture teams."""
    return (HOME_TEAM_KEY, AWAY_TEAM_KEY)


def fixture_identity(home: str, away: str) -> dict[str, str]:
    """Return game-row team identity fields for one fixture."""
    return {HOME_TEAM_KEY: home, AWAY_TEAM_KEY: away}


def fixture_selector_supplied(match_id: str, home: str, away: str) -> bool:
    """Return whether manual lookup has a match id or complete fixture teams."""
    return bool(match_id or fixture_team_selector_complete(home, away))


def fixture_selector_matches(row_home: str, row_away: str, home: str, away: str) -> bool:
    """Return whether row teams satisfy an optional complete team selector."""
    return not (home and away) or matches_fixture(row_home, row_away, home, away)


def fixture_team_selector_complete(home: str, away: str) -> bool:
    """Return whether both sides of a manual fixture selector are present."""
    return bool(home and away)


def normalize_fixture_selector(match_id: str, home: str, away: str) -> tuple[str, str, str]:
    """Return stripped optional selector values for manual fixture lookup."""
    return (
        normalize_optional_text(match_id) or "",
        normalize_optional_text(home) or "",
        normalize_optional_text(away) or "",
    )


def schedule_team_keys() -> tuple[str, str]:
    """Return source schedule CSV keys identifying the two fixture teams."""
    return (SCHEDULE_HOME_TEAM_KEY, SCHEDULE_AWAY_TEAM_KEY)


def schedule_metadata_keys() -> tuple[str, str, str]:
    """Return source schedule CSV keys needed for kickoff timing."""
    return (SCHEDULE_DATE_KEY, SCHEDULE_TIME_KEY, SCHEDULE_UTC_OFFSET_KEY)


def schedule_to_game_metadata_key_map() -> tuple[tuple[str, str], ...]:
    """Return source schedule metadata keys paired with emitted game keys."""
    return ((SCHEDULE_DATE_KEY, DATE_KEY),)


def schedule_source_row_keys() -> tuple[str, ...]:
    """Return every source schedule CSV key consumed by schedule loading."""
    return schedule_team_keys() + schedule_metadata_keys()


def schedule_fixture_teams(row: dict) -> tuple[str, str]:
    """Return home and away team values from one schedule source row."""
    home_key, away_key = schedule_team_keys()
    return row[home_key], row[away_key]


def fixture_metadata_keys() -> tuple[str, ...]:
    """Return non-team fixture metadata keys emitted on game rows."""
    return (MATCH_ID_KEY, DATE_KEY, KICKOFF_UTC_KEY, GROUP_KEY)


def game_row_keys() -> tuple[str, ...]:
    """Return all non-derived game-row keys emitted by schedule/model joins."""
    return game_row_identity_keys() + game_row_model_keys()


def game_row_identity_keys() -> tuple[str, ...]:
    """Return game-row metadata and team keys that identify one fixture."""
    return fixture_metadata_keys() + fixture_team_keys()


def game_row_identity(row: dict) -> dict[str, str]:
    """Return identity metadata and team fields from one emitted game row."""
    return {key: row[key] for key in game_row_identity_keys()}


def game_row_match_id(row: dict) -> str:
    """Return the match id from one emitted game row."""
    return row[MATCH_ID_KEY]


def game_row_kickoff_utc(row: dict) -> str:
    """Return the kickoff timestamp from one emitted game row."""
    return row[KICKOFF_UTC_KEY]


def game_row_model_keys() -> tuple[str, ...]:
    """Return game-row model probability keys emitted by schedule/model joins."""
    return model_probability_keys()


def game_row_missing_keys(row: dict) -> tuple[str, ...]:
    """Return required emitted game-row keys absent from one row."""
    return tuple(key for key in game_row_keys() if key not in row)


def game_row_has_required_keys(row: dict) -> bool:
    """Return whether a game row contains every required emitted field."""
    return not game_row_missing_keys(row)


def game_row_model_values(row: dict) -> dict[str, float]:
    """Return model probability fields from one emitted game row."""
    return {key: row[key] for key in game_row_model_keys()}


def game_row_team_values(row: dict) -> tuple[str, str]:
    """Return home and away team values from one emitted game row."""
    return row[HOME_TEAM_KEY], row[AWAY_TEAM_KEY]


def game_row_fixture_key(row: dict) -> tuple[str, str]:
    """Return the canonical fixture key for one emitted game row."""
    return game_key(*game_row_team_values(row))


def prediction_probability_keys() -> tuple[str, ...]:
    """Return source CSV probability keys consumed by load_predictions."""
    return (
        PRED_HOME_WIN_KEY,
        PRED_DRAW_KEY,
        PRED_AWAY_WIN_KEY,
        PRED_OVER_2_5_KEY,
        PRED_BTTS_KEY,
    )


def prediction_metadata_keys() -> tuple[str, str]:
    """Return source CSV metadata keys consumed by load_predictions."""
    return (PRED_MATCH_ID_KEY, PRED_GROUP_KEY)


def prediction_loaded_metadata_keys() -> tuple[str, str]:
    """Return loaded prediction-row metadata keys."""
    return (PRED_MATCH_ID_VALUE_KEY, PRED_GROUP_VALUE_KEY)


def prediction_metadata_key_map() -> tuple[tuple[str, str], ...]:
    """Return source prediction metadata keys paired with loaded row keys."""
    return (
        (PRED_MATCH_ID_KEY, PRED_MATCH_ID_VALUE_KEY),
        (PRED_GROUP_KEY, PRED_GROUP_VALUE_KEY),
    )


def prediction_team_keys() -> tuple[str, str]:
    """Return source prediction CSV keys identifying the two fixture teams."""
    return (PRED_HOME_TEAM_KEY, PRED_AWAY_TEAM_KEY)


def prediction_fixture_teams(row: dict) -> tuple[str, str]:
    """Return home and away team values from one prediction source row."""
    home_key, away_key = prediction_team_keys()
    return row[home_key], row[away_key]


def prediction_source_row_keys() -> tuple[str, ...]:
    """Return every source prediction CSV key consumed by prediction loading."""
    return prediction_team_keys() + prediction_metadata_keys() + prediction_value_keys()


def prediction_value_keys() -> tuple[str, ...]:
    """Return source prediction CSV keys with numeric model values."""
    return prediction_probability_keys() + (PRED_UNDER_2_5_KEY,)


def prediction_loaded_value_keys() -> tuple[str, ...]:
    """Return loaded prediction-row numeric value keys."""
    return (
        PRED_HOME_WIN_VALUE_KEY,
        PRED_DRAW_VALUE_KEY,
        PRED_AWAY_WIN_VALUE_KEY,
        PRED_OVER_2_5_VALUE_KEY,
        PRED_UNDER_2_5_VALUE_KEY,
        PRED_BTTS_VALUE_KEY,
    )


def prediction_value_key_map() -> tuple[tuple[str, str], ...]:
    """Return source prediction value keys paired with loaded row keys."""
    return (
        (PRED_HOME_WIN_KEY, PRED_HOME_WIN_VALUE_KEY),
        (PRED_DRAW_KEY, PRED_DRAW_VALUE_KEY),
        (PRED_AWAY_WIN_KEY, PRED_AWAY_WIN_VALUE_KEY),
        (PRED_OVER_2_5_KEY, PRED_OVER_2_5_VALUE_KEY),
        (PRED_UNDER_2_5_KEY, PRED_UNDER_2_5_VALUE_KEY),
        (PRED_BTTS_KEY, PRED_BTTS_VALUE_KEY),
    )


def prediction_loaded_row_keys() -> tuple[str, ...]:
    """Return every loaded prediction-row key emitted by load_predictions."""
    return prediction_loaded_metadata_keys() + prediction_loaded_value_keys()


def prediction_row_key(row: dict) -> tuple[str, str]:
    """Return the canonical fixture key for one prediction CSV row."""
    return game_key(*prediction_fixture_teams(row))


def prediction_row_metadata(row: dict) -> dict[str, str]:
    """Return loaded metadata fields for one prediction CSV row."""
    return {
        loaded_key: row.get(source_key, "")
        for source_key, loaded_key in prediction_metadata_key_map()
    }


def prediction_row_values(row: dict) -> dict[str, float]:
    """Return loaded numeric model fields for one prediction CSV row."""
    return {
        loaded_key: float(row[source_key])
        for source_key, loaded_key in prediction_value_key_map()
    }


def prediction_model_values(row: dict) -> dict[str, float]:
    """Return game-row model value fields for one loaded prediction row."""
    return {
        model_key: row[prediction_key]
        for prediction_key, model_key in prediction_to_model_key_map()
    }


def prediction_to_model_key_map() -> tuple[tuple[str, str], ...]:
    """Return loaded prediction keys paired with emitted game-row model keys."""
    return (
        (PRED_HOME_WIN_VALUE_KEY, MODEL_HOME_WIN_KEY),
        (PRED_DRAW_VALUE_KEY, MODEL_DRAW_KEY),
        (PRED_AWAY_WIN_VALUE_KEY, MODEL_AWAY_WIN_KEY),
        (PRED_OVER_2_5_VALUE_KEY, MODEL_OVER_2_5_KEY),
        (PRED_BTTS_VALUE_KEY, MODEL_BTTS_KEY),
    )


def prediction_game_metadata(row: dict) -> dict[str, str]:
    """Return game-row metadata fields for one loaded prediction row."""
    return {
        game_key_value: row[prediction_key]
        for prediction_key, game_key_value in prediction_to_game_metadata_key_map()
    }


def prediction_to_game_metadata_key_map() -> tuple[tuple[str, str], ...]:
    """Return loaded prediction metadata keys paired with emitted game keys."""
    return (
        (PRED_MATCH_ID_VALUE_KEY, MATCH_ID_KEY),
        (PRED_GROUP_VALUE_KEY, GROUP_KEY),
    )


def prediction_matches_id(row: dict, match_id: str) -> bool:
    """Return whether a loaded prediction row matches an optional match id."""
    return not match_id or str(row[PRED_MATCH_ID_VALUE_KEY]) == str(match_id)


# --------------------------------------------------------------------------- #
# data loading                                                                #
# --------------------------------------------------------------------------- #
def game_key(home: str, away: str) -> tuple[str, str]:
    """Canonical key for fixture-indexed model and schedule rows."""
    return home, away


def _read_csv(path: str | PathLike[str]) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_predictions() -> dict[tuple[str, str], dict]:
    """Pre-tournament model probabilities keyed by (home_team, away_team)."""
    out: dict[tuple[str, str], dict] = {}
    for r in _read_csv(config.PREDICTIONS_FILE):
        out[prediction_row_key(r)] = {
            **prediction_row_metadata(r),
            **prediction_row_values(r),
        }
    return out


def load_schedule() -> dict[tuple[str, str], dict]:
    return {schedule_row_key(r): r for r in _read_csv(config.SCHEDULE_FILE)}


def kickoff_utc(date_str: str, time_str: str, utc_offset: str) -> str:
    """Local kickoff -> ISO-8601 UTC. utc = local - offset."""
    local = dt.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    utc = local - dt.timedelta(hours=float(utc_offset))
    return utc.replace(tzinfo=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def schedule_row_kickoff_utc(row: dict) -> str:
    """Return a schedule row's kickoff timestamp normalized to UTC."""
    return kickoff_utc(*schedule_timing_values(row))


def schedule_timing_values(row: dict) -> tuple[str, str, str]:
    """Return date, time, and UTC offset values from one schedule row."""
    return row[SCHEDULE_DATE_KEY], row[SCHEDULE_TIME_KEY], row[SCHEDULE_UTC_OFFSET_KEY]


def schedule_row_date(row: dict) -> str:
    """Return the source schedule date for one schedule CSV row."""
    return row[SCHEDULE_DATE_KEY]


def schedule_row_key(row: dict) -> tuple[str, str]:
    """Return the canonical fixture key for one schedule CSV row."""
    return game_key(*schedule_fixture_teams(row))


def schedule_game_metadata(row: dict, kickoff_utc_value: str) -> dict[str, str]:
    """Return game-row schedule metadata fields for one schedule row."""
    metadata = {
        game_key_value: row[source_key] if row else ""
        for source_key, game_key_value in schedule_to_game_metadata_key_map()
    }
    metadata[KICKOFF_UTC_KEY] = kickoff_utc_value
    return metadata


def build_game_row(
    home: str,
    away: str,
    prediction_row: dict,
    schedule_row: dict,
    kickoff_utc_value: str,
) -> dict:
    """Return the canonical game row emitted by prediction/schedule joins."""
    return {
        **prediction_game_metadata(prediction_row),
        **schedule_game_metadata(schedule_row, kickoff_utc_value),
        **fixture_identity(home, away),
        **prediction_model_values(prediction_row),
    }


def game_row_sort_key(row: dict) -> tuple[str, str]:
    """Return the stable chronological sort key for emitted game rows."""
    return (game_row_kickoff_utc(row), game_row_match_id(row))


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _parse(iso_utc: str) -> Optional[dt.datetime]:
    return parse_kickoff_utc(iso_utc)


def parse_kickoff_utc(iso_utc: str) -> Optional[dt.datetime]:
    try:
        return dt.datetime.strptime(iso_utc, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def upcoming_games(now: Optional[dt.datetime] = None) -> list[dict]:
    """Scheduled fixtures that (a) have a pre-tournament model prediction and
    (b) have not kicked off yet, earliest first. Knockout fixtures (TBD teams)
    have no prediction and are naturally excluded."""
    now = now or _now()
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(dt.timezone.utc)
    preds = load_predictions()
    sched = load_schedule()
    games = []
    for (home, away), pred in preds.items():
        sc = sched.get((home, away))
        if not sc:
            continue
        ko = schedule_row_kickoff_utc(sc)
        kt = _parse(ko)
        if kt is None or kt <= now:
            continue
        games.append(build_game_row(home, away, pred, sc, ko))
    games.sort(key=game_row_sort_key)
    return games


def next_game(now: Optional[dt.datetime] = None) -> Optional[dict]:
    games = upcoming_games(now)
    return games[0] if games else None


def find_game(match_id: str = "", home: str = "", away: str = "") -> Optional[dict]:
    """Look up a specific fixture (ignores the kickoff filter), for manual runs."""
    match_id, home, away = normalize_fixture_selector(match_id, home, away)
    preds = load_predictions()
    sched = load_schedule()
    for (h, a), pred in preds.items():
        if not prediction_matches_id(pred, match_id):
            continue
        if not fixture_selector_matches(h, a, home, away):
            continue
        if not fixture_selector_supplied(match_id, home, away):
            continue
        sc = sched.get((h, a), {})
        ko = schedule_row_kickoff_utc(sc) if sc else ""
        return build_game_row(h, a, pred, sc, ko)
    return None


def matches_fixture(row_home: str, row_away: str, home: str, away: str) -> bool:
    """Case-insensitive comparison for manual fixture selection."""
    return row_home.lower() == home.lower() and row_away.lower() == away.lower()


# --------------------------------------------------------------------------- #
# probability math (de-vig + Kelly)                                           #
# --------------------------------------------------------------------------- #
def devig_three_way(home: float, draw: float, away: float) -> tuple[float, float, float]:
    if not all(probability.is_probability(v) for v in (home, draw, away)):
        return 0.0, 0.0, 0.0
    s = home + draw + away
    return (home / s, draw / s, away / s) if s > 0 else (0.0, 0.0, 0.0)


def devig_binary(yes: float, no: Optional[float]) -> float:
    if not probability.is_probability(yes):
        return 0.0
    if no is not None and not probability.is_probability(no):
        return yes
    if no is None:
        return yes
    s = yes + no
    return yes / s if s > 0 else yes


def kelly_fraction(model_prob: float, entry_price: float) -> float:
    """Full-Kelly fraction for a YES-style contract bought at ``entry_price``
    (probability). f* = (p - price) / (1 - price); 0 when no positive edge."""
    if not probability.is_probability(model_prob):
        return 0.0
    if not probability.is_probability(entry_price) or entry_price in (0.0, 1.0):
        return 0.0
    return max(0.0, (model_prob - entry_price) / (1.0 - entry_price))


def staked_fraction(kelly_full: float) -> float:
    """Half-Kelly, capped -- the share of bankroll actually risked."""
    if not math.isfinite(kelly_full):
        return 0.0
    return min(settings.KELLY_FRACTION * max(kelly_full, 0.0),
               settings.MAX_STAKE_FRACTION)


def meets_edge_threshold(edge: float) -> bool:
    """Return True when an edge clears the configured strategy threshold."""
    return probability.edge_clears_threshold(edge, settings.EDGE_THRESHOLD - 1e-9)


# --------------------------------------------------------------------------- #
# bet flagging                                                                #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Bet:
    line: str            # "winner" | "over_under" | "btts"
    selection: str       # e.g. "NO Brazil", "OVER 2.5", "BTTS YES"
    side: str            # "YES" | "NO" relative to the contract
    selection_team: str  # team name for winner bets, else ""
    model_prob: float    # model P(bet wins)
    fair_prob: float     # de-vigged market P(bet wins)
    market_price: float  # price paid, probability terms (vig included)
    edge: float
    kelly_full: float


def _evaluate(name: str, yes_label: str, no_label: str, selection_team: str,
              model_yes: float, fair_yes: float, yes_price: float,
              no_price: Optional[float]) -> Optional[Bet]:
    diff = probability.probability_edge(model_yes, fair_yes)
    if meets_edge_threshold(diff):
        side, label = "YES", yes_label
        model_win, fair_win, price = model_yes, fair_yes, yes_price
    elif meets_edge_threshold(-diff):
        side, label = "NO", no_label
        model_win = probability.probability_complement(model_yes)
        fair_win = probability.probability_complement(fair_yes)
        price = no_price if no_price is not None else probability.probability_complement(yes_price)
    else:
        return None
    return Bet(line=name, selection=label, side=side, selection_team=selection_team,
               model_prob=model_win, fair_prob=fair_win, market_price=price,
               edge=probability.probability_edge(model_win, fair_win),
               kelly_full=kelly_fraction(model_win, price))


def _c2p(v) -> Optional[float]:
    """Cents (0-100) -> probability (0-1). '' / None -> None."""
    return probability.cents_to_probability(v)


def flag_bets(game: dict, odds: dict) -> list[Bet]:
    """Apply the >=10% mispricing rule to one game's live odds.

    ``odds`` carries cents prices under the keys returned by
    ``markets.complete_odds_price_keys()``; any key may be absent.
    """
    bets: list[Bet] = []

    hp, dp, ap = (_c2p(odds.get(markets.WINNER_HOME_PRICE_KEY)),
                  _c2p(odds.get(markets.WINNER_DRAW_PRICE_KEY)),
                  _c2p(odds.get(markets.WINNER_AWAY_PRICE_KEY)))
    if None not in (hp, dp, ap):
        fh, fd, fa = devig_three_way(hp, dp, ap)
        for model_p, fair_p, raw_p, team, label in (
            (game[MODEL_HOME_WIN_KEY], fh, hp, game[HOME_TEAM_KEY], game[HOME_TEAM_KEY]),
            (game[MODEL_DRAW_KEY], fd, dp, "", DRAW_SELECTION),
            (game[MODEL_AWAY_WIN_KEY], fa, ap, game[AWAY_TEAM_KEY], game[AWAY_TEAM_KEY]),
        ):
            yes_label, no_label = winner_selection_labels(label)
            b = _evaluate(
                WINNER_LINE, yes_label, no_label, team,
                model_p, fair_p, raw_p, probability.probability_complement(raw_p),
            )
            if b:
                bets.append(b)

    op, up = (
        _c2p(odds.get(markets.OVER_2_5_PRICE_KEY)),
        _c2p(odds.get(markets.UNDER_2_5_PRICE_KEY)),
    )
    if op is not None:
        b = _evaluate(OVER_UNDER_LINE, OVER_2_5_SELECTION, UNDER_2_5_SELECTION, "",
                      game[MODEL_OVER_2_5_KEY], devig_binary(op, up), op,
                      up if up is not None else probability.probability_complement(op))
        if b:
            bets.append(b)

    by, bn = (
        _c2p(odds.get(markets.BTTS_YES_PRICE_KEY)),
        _c2p(odds.get(markets.BTTS_NO_PRICE_KEY)),
    )
    if by is not None:
        b = _evaluate(BTTS_LINE, BTTS_YES_SELECTION, BTTS_NO_SELECTION, "",
                      game[MODEL_BTTS_KEY], devig_binary(by, bn), by,
                      bn if bn is not None else probability.probability_complement(by))
        if b:
            bets.append(b)

    return bets
