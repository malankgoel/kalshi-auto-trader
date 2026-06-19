"""The model side of the trader: bundled pre-tournament forecast + the exact
mispricing rules the backtest uses.

Self-contained -- reads only the CSVs in ``data/`` (no parent repo). Given a
fixture and a row of current Kalshi YES prices (in cents), it de-vigs the market
and returns the >=10% mispricings as bets, each already sized with half-Kelly.
"""

from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from os import PathLike
from typing import Optional

from kalshi_auto_trader import settings
from kalshi_auto_trader.world_cup import config


# --------------------------------------------------------------------------- #
# data loading                                                                #
# --------------------------------------------------------------------------- #
def _read_csv(path: str | PathLike[str]) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_predictions() -> dict[tuple[str, str], dict]:
    """Pre-tournament model probabilities keyed by (home_team, away_team)."""
    out: dict[tuple[str, str], dict] = {}
    for r in _read_csv(config.PREDICTIONS_FILE):
        out[(r["home_team"], r["away_team"])] = {
            "match_id": r.get("match_id", ""),
            "group": r.get("group", ""),
            "home_win": float(r["home_win"]),
            "draw": float(r["draw"]),
            "away_win": float(r["away_win"]),
            "over_2_5": float(r["over_2_5"]),
            "under_2_5": float(r["under_2_5"]),
            "btts": float(r["both_teams_to_score"]),
        }
    return out


def load_schedule() -> dict[tuple[str, str], dict]:
    return {(r["home_team"], r["away_team"]): r
            for r in _read_csv(config.SCHEDULE_FILE)}


def kickoff_utc(date_str: str, time_str: str, utc_offset: str) -> str:
    """Local kickoff -> ISO-8601 UTC. utc = local - offset."""
    local = dt.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    utc = local - dt.timedelta(hours=float(utc_offset))
    return utc.replace(tzinfo=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _parse(iso_utc: str) -> Optional[dt.datetime]:
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
    preds = load_predictions()
    sched = load_schedule()
    games = []
    for (home, away), pred in preds.items():
        sc = sched.get((home, away))
        if not sc:
            continue
        ko = kickoff_utc(sc["date"], sc["time"], sc["utc_offset"])
        kt = _parse(ko)
        if kt is None or kt <= now:
            continue
        games.append({
            "match_id": pred["match_id"], "date": sc["date"], "kickoff_utc": ko,
            "group": pred["group"], "home_team": home, "away_team": away,
            "model_home_win": pred["home_win"], "model_draw": pred["draw"],
            "model_away_win": pred["away_win"], "model_over_2_5": pred["over_2_5"],
            "model_btts": pred["btts"],
        })
    games.sort(key=lambda g: (g["kickoff_utc"], g["match_id"]))
    return games


def next_game(now: Optional[dt.datetime] = None) -> Optional[dict]:
    games = upcoming_games(now)
    return games[0] if games else None


def find_game(match_id: str = "", home: str = "", away: str = "") -> Optional[dict]:
    """Look up a specific fixture (ignores the kickoff filter), for manual runs."""
    preds = load_predictions()
    sched = load_schedule()
    for (h, a), pred in preds.items():
        if match_id and str(pred["match_id"]) != str(match_id):
            continue
        if home and away and (h.lower() != home.lower() or a.lower() != away.lower()):
            continue
        if not match_id and not (home and away):
            continue
        sc = sched.get((h, a), {})
        ko = kickoff_utc(sc["date"], sc["time"], sc["utc_offset"]) if sc else ""
        return {
            "match_id": pred["match_id"], "date": sc.get("date", ""),
            "kickoff_utc": ko, "group": pred["group"], "home_team": h, "away_team": a,
            "model_home_win": pred["home_win"], "model_draw": pred["draw"],
            "model_away_win": pred["away_win"], "model_over_2_5": pred["over_2_5"],
            "model_btts": pred["btts"],
        }
    return None


# --------------------------------------------------------------------------- #
# probability math (de-vig + Kelly)                                           #
# --------------------------------------------------------------------------- #
def devig_three_way(home: float, draw: float, away: float) -> tuple[float, float, float]:
    s = home + draw + away
    return (home / s, draw / s, away / s) if s > 0 else (0.0, 0.0, 0.0)


def devig_binary(yes: float, no: Optional[float]) -> float:
    if no is None:
        return yes
    s = yes + no
    return yes / s if s > 0 else yes


def kelly_fraction(model_prob: float, entry_price: float) -> float:
    """Full-Kelly fraction for a YES-style contract bought at ``entry_price``
    (probability). f* = (p - price) / (1 - price); 0 when no positive edge."""
    if entry_price <= 0 or entry_price >= 1:
        return 0.0
    return max(0.0, (model_prob - entry_price) / (1.0 - entry_price))


def staked_fraction(kelly_full: float) -> float:
    """Half-Kelly, capped -- the share of bankroll actually risked."""
    return min(settings.KELLY_FRACTION * kelly_full, settings.MAX_STAKE_FRACTION)


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
    eps = 1e-9
    diff = model_yes - fair_yes
    if diff >= settings.EDGE_THRESHOLD - eps:
        side, label = "YES", yes_label
        model_win, fair_win, price = model_yes, fair_yes, yes_price
    elif -diff >= settings.EDGE_THRESHOLD - eps:
        side, label = "NO", no_label
        model_win, fair_win = 1.0 - model_yes, 1.0 - fair_yes
        price = no_price if no_price is not None else (1.0 - yes_price)
    else:
        return None
    return Bet(line=name, selection=label, side=side, selection_team=selection_team,
               model_prob=model_win, fair_prob=fair_win, market_price=price,
               edge=model_win - fair_win, kelly_full=kelly_fraction(model_win, price))


def _c2p(v) -> Optional[float]:
    """Cents (0-100) -> probability (0-1). '' / None -> None."""
    if v is None or v == "":
        return None
    return float(v) / 100.0


def flag_bets(game: dict, odds: dict) -> list[Bet]:
    """Apply the >=10% mispricing rule to one game's live odds.

    ``odds`` carries YES prices in cents per outcome: winner_home_price,
    winner_draw_price, winner_away_price, over_2_5_price, under_2_5_price,
    btts_yes_price, btts_no_price (any may be absent).
    """
    bets: list[Bet] = []

    hp, dp, ap = (_c2p(odds.get("winner_home_price")),
                  _c2p(odds.get("winner_draw_price")),
                  _c2p(odds.get("winner_away_price")))
    if None not in (hp, dp, ap):
        fh, fd, fa = devig_three_way(hp, dp, ap)
        for model_p, fair_p, raw_p, team, label in (
            (game["model_home_win"], fh, hp, game["home_team"], game["home_team"]),
            (game["model_draw"], fd, dp, "", "Draw"),
            (game["model_away_win"], fa, ap, game["away_team"], game["away_team"]),
        ):
            b = _evaluate("winner", f"YES {label}", f"NO {label}", team,
                          model_p, fair_p, raw_p, 1.0 - raw_p)
            if b:
                bets.append(b)

    op, up = _c2p(odds.get("over_2_5_price")), _c2p(odds.get("under_2_5_price"))
    if op is not None:
        b = _evaluate("over_under", "OVER 2.5", "UNDER 2.5", "",
                      game["model_over_2_5"], devig_binary(op, up), op,
                      up if up is not None else (1.0 - op))
        if b:
            bets.append(b)

    by, bn = _c2p(odds.get("btts_yes_price")), _c2p(odds.get("btts_no_price"))
    if by is not None:
        b = _evaluate("btts", "BTTS YES", "BTTS NO", "",
                      game["model_btts"], devig_binary(by, bn), by,
                      bn if bn is not None else (1.0 - by))
        if b:
            bets.append(b)

    return bets
