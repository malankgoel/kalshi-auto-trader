"""Resolve a pending bet to a concrete, live Kalshi market ticker + side.

A tally row tells us the fixture (matchup, date), the line (winner / over_under
/ btts), the side (YES/NO) and, for winners, the team. It does NOT carry the
exact market ticker -- tickers are only knowable live -- so this module re-finds
the open market for the fixture and maps the bet onto the right contract.

The team-code / alias / event-token logic mirrors the recommender's matcher so
the two agree on which market a bet refers to. This file is intentionally a
standalone copy: the trader repo never imports the model repo.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import unicodedata
from typing import Optional

from kalshi_auto_trader.world_cup import config


logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# normalisation + team naming                                                 #
# --------------------------------------------------------------------------- #
def _norm(s: str) -> str:
    """Lowercase + strip accents so 'Curaçao' == 'Curacao', 'Türkiye' matches."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


TEAM_ALIASES = {
    "Turkey": ["turkiye"],
    "Czech Republic": ["czechia"],
    "Cape Verde": ["cabo verde"],
    "Ivory Coast": ["cote d'ivoire", "cote divoire"],
    "United States": ["usa", "united states of america"],
    "South Korea": ["korea republic", "korea"],
    "DR Congo": ["dr congo", "democratic republic of the congo", "congo dr"],
    "Iran": ["ir iran"],
    "Bosnia and Herzegovina": ["bosnia"],
}

TEAM_CODES = {
    "Mexico": "MEX", "South Africa": "RSA", "South Korea": "KOR",
    "Czech Republic": "CZE", "Canada": "CAN", "Bosnia and Herzegovina": "BIH",
    "United States": "USA", "Paraguay": "PAR", "Qatar": "QAT",
    "Switzerland": "SUI", "Brazil": "BRA", "Morocco": "MAR", "Haiti": "HTI",
    "Scotland": "SCO", "Australia": "AUS", "Turkey": "TUR", "Germany": "GER",
    "Curaçao": "CUW", "Netherlands": "NED", "Japan": "JPN", "Ivory Coast": "CIV",
    "Ecuador": "ECU", "Sweden": "SWE", "Tunisia": "TUN", "Spain": "ESP",
    "Cape Verde": "CPV", "Belgium": "BEL", "Egypt": "EGY", "Iran": "IRI",
    "New Zealand": "NZL", "Saudi Arabia": "KSA", "Uruguay": "URU",
    "Argentina": "ARG", "France": "FRA", "England": "ENG", "Portugal": "POR",
    "Croatia": "CRO", "Colombia": "COL", "Senegal": "SEN", "Norway": "NOR",
    "Austria": "AUT", "Jordan": "JOR", "Algeria": "ALG", "DR Congo": "COD",
    "Uzbekistan": "UZB", "Panama": "PAN", "Ghana": "GHA", "Iraq": "IRQ",
}


def _team_aliases(team: str) -> list[str]:
    return [_norm(team)] + [_norm(a) for a in TEAM_ALIASES.get(team, [])]


# --------------------------------------------------------------------------- #
# event-ticker parsing                                                        #
# --------------------------------------------------------------------------- #
def _event_codes(event_ticker: str) -> tuple[str, str]:
    m = re.search(r"\d{2}[A-Z]{3}\d{2}([A-Z]{3})([A-Z]{3})",
                  (event_ticker or "").upper())
    return (m.group(1), m.group(2)) if m else ("", "")


def _event_token(event_ticker: str) -> str:
    """Shared date+teams token, identical across the winner/total/BTTS series for
    one game, e.g. 'KXWCGAME-26JUN16ARGALG-ARG' -> '26JUN16ARGALG'."""
    m = re.search(r"\d{2}[A-Z]{3}\d{2}[A-Z]{6}", (event_ticker or "").upper())
    return m.group(0) if m else ""


_MONTHS = {"JAN": "01", "FEB": "02", "MAR": "03", "APR": "04", "MAY": "05",
           "JUN": "06", "JUL": "07", "AUG": "08", "SEP": "09", "OCT": "10",
           "NOV": "11", "DEC": "12"}


def _event_date(event_ticker: str) -> str:
    m = re.search(r"(\d{2})([A-Z]{3})(\d{2})[A-Z]{6}", (event_ticker or "").upper())
    if not m:
        return ""
    mm = _MONTHS.get(m.group(2))
    return f"20{m.group(1)}-{mm}-{m.group(3)}" if mm else ""


def _date_diff_days(d1: str, d2: str) -> Optional[int]:
    fmt = "%Y-%m-%d"
    try:
        return (dt.datetime.strptime(d1, fmt) - dt.datetime.strptime(d2, fmt)).days
    except ValueError:
        return None


def _market_blob(market: dict) -> str:
    return " ".join(
        _norm(str(market.get(f, ""))) for f in
        ("title", "subtitle", "yes_sub_title", "no_sub_title",
         "ticker", "event_ticker")
    )


def _match_teams(market: dict, home: str, away: str, game_date: str = "") -> bool:
    """True if the market belongs to this fixture (date-aware, alias-tolerant)."""
    ev = market.get("event_ticker", "")
    ev_date = _event_date(ev)
    if game_date and ev_date:
        date_diff = _date_diff_days(game_date, ev_date)
        if date_diff is None or abs(date_diff) > 1:
            return False  # +/-1 day: ticker uses UTC date, game date is local
    hc, ac = _event_codes(ev)
    home_code, away_code = TEAM_CODES.get(home), TEAM_CODES.get(away)
    if hc and home_code and away_code and {hc, ac} == {home_code, away_code}:
        return True
    blob = _market_blob(market)
    return (any(a in blob for a in _team_aliases(home))
            and any(a in blob for a in _team_aliases(away)))


def _is_2_5_line(market: dict) -> bool:
    for k in ("cap_strike", "floor_strike", "strike", "subtitle",
              "yes_sub_title", "title"):
        v = market.get(k)
        if v is not None and "2.5" in str(v):
            return True
    return False


# --------------------------------------------------------------------------- #
# price reading                                                               #
# --------------------------------------------------------------------------- #
def _cents(market: dict, *keys) -> Optional[float]:
    """First present price key, in CENTS. Tries dollar-string keys (*_dollars)
    and plain integer-cent keys."""
    for k in keys:
        v = market.get(k)
        if v in (None, ""):
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        return v * 100.0 if k.endswith("_dollars") else v
    return None


def yes_price_cents(market: dict) -> Optional[float]:
    """A YES price (cents, 0-100) for de-vigging: mid of the live yes book if
    both sides quote, else the last traded price."""
    yb = _cents(market, "yes_bid_dollars", "yes_bid")
    ya = _cents(market, "yes_ask_dollars", "yes_ask")
    if yb is not None and ya is not None and ya >= yb and (yb + ya) > 0:
        return max(0.0, min(100.0, (yb + ya) / 2.0))
    for k in ("last_price_dollars", "last_price",
              "previous_price_dollars", "previous_price"):
        v = _cents(market, k)
        if v is not None:
            return max(0.0, min(100.0, v))
    return None


def build_odds_row(idx: dict, home: str, away: str) -> dict:
    """Collapse a market index into the YES-price-per-outcome row (cents) that
    model.flag_bets consumes. Under/BTTS-No are left to the model's binary
    complement unless an explicit market is indexed."""
    row: dict = {}

    def put(key, market):
        if market is not None:
            p = yes_price_cents(market)
            if p is not None:
                row[key] = round(p, 1)

    put("winner_home_price", idx["winner"].get(_norm(home)))
    put("winner_away_price", idx["winner"].get(_norm(away)))
    put("winner_draw_price", idx.get("draw"))
    put("over_2_5_price", idx.get("over"))
    put("btts_yes_price", idx.get("btts"))
    return row


def side_ask_cents(market: dict, side: str) -> Optional[float]:
    """Cost (cents/contract) to BUY ``side`` now: the ask for that side. Falls
    back to 100 - opposite bid when an explicit ask isn't quoted."""
    if side not in ("yes", "no"):
        raise ValueError("side must be 'yes' or 'no'")
    if side == "yes":
        v = _cents(market, "yes_ask_dollars", "yes_ask")
        if v is None:
            nb = _cents(market, "no_bid_dollars", "no_bid")
            v = 100.0 - nb if nb is not None else None
    else:  # no
        v = _cents(market, "no_ask_dollars", "no_ask")
        if v is None:
            yb = _cents(market, "yes_bid_dollars", "yes_bid")
            v = 100.0 - yb if yb is not None else None
    if v is None:
        return None
    return max(0.0, min(100.0, v))


# --------------------------------------------------------------------------- #
# build a per-game market index                                               #
# --------------------------------------------------------------------------- #
def _classify_winner(m: dict, home: str, away: str, idx: dict) -> None:
    yes_sub = _norm(str(m.get("yes_sub_title", "")))
    tail = _norm(m.get("ticker", "").rsplit("-", 1)[-1])  # e.g. 'arg', 'tie'
    key = yes_sub + " " + tail
    if "tie" in key or "draw" in key:
        if idx.get("draw") is None:           # first match wins; don't overwrite
            idx["draw"] = m
    elif any(a in key for a in _team_aliases(away)):
        idx["winner"].setdefault(_norm(away), m)
    elif any(a in key for a in _team_aliases(home)):
        idx["winner"].setdefault(_norm(home), m)


def _classify_line(m: dict, line: str, idx: dict) -> None:
    yes_sub = _norm(str(m.get("yes_sub_title", "")))
    if line == "btts":
        if not yes_sub.startswith("no") and idx.get("btts") is None:
            idx["btts"] = m
    elif line == "over_under":
        if _is_2_5_line(m) and "under" not in yes_sub and idx.get("over") is None:
            idx["over"] = m  # YES = OVER side


def build_market_index(client, home: str, away: str, date: str) -> dict:
    """Find the live markets for a fixture and index them by outcome.

    Returns {"winner": {team_norm: market}, "draw": market|None,
             "over": market|None, "btts": market|None}. Winner markets carry the
    team names and reveal the game's event token; totals/BTTS (no team names in
    their titles) are then matched by that exact token. Statuses are swept
    because the three lines can open for trading at different times.
    """
    idx: dict = {"winner": {}, "draw": None, "over": None, "btts": None}
    token = ""
    line_of = {s: ln for ln, lst in config.KALSHI_SERIES.items() for s in lst}
    ou_btts = config.KALSHI_SERIES["over_under"] + config.KALSHI_SERIES["btts"]

    for status in ("open", "unopened", None):
        for s in config.KALSHI_SERIES["winner"]:
            try:
                for m in client.list_markets(series_ticker=s, status=status):
                    if _match_teams(m, home, away, date):
                        _classify_winner(m, home, away, idx)
                        if not token:
                            token = _event_token(m.get("event_ticker", ""))
            except Exception as exc:  # noqa: BLE001
                logger.warning("winner series %s: %s", s, exc)
        if token:
            for s in ou_btts:
                try:
                    for m in client.list_markets(series_ticker=s, status=status):
                        if _event_token(m.get("event_ticker", "")) == token:
                            _classify_line(m, line_of.get(s, ""), idx)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("series %s: %s", s, exc)
        if idx["winner"] and idx["over"] and idx["btts"]:
            break
    return idx


def resolve_order(idx: dict, line: str, side: str, selection: str,
                  selection_team: str) -> tuple[Optional[dict], str]:
    """Map a tally bet onto (market, buy_side). buy_side is 'yes'/'no'.

    winner: market is the selection team's 'to win' contract (or the draw);
            buy YES to back, NO to fade -- the tally already encodes which.
    over_under: the OVER-2.5 market; YES = over, NO = under.
    btts: the BTTS-YES market; YES = both score, NO = not both.
    """
    buy_side = side.strip().lower()
    if buy_side not in ("yes", "no"):
        raise ValueError("side must be 'YES' or 'NO'")
    if line in ("winner", "winner_draw"):
        if "draw" in _norm(selection) or _norm(selection_team) in ("draw", "tie", ""):
            return idx.get("draw"), buy_side
        return idx["winner"].get(_norm(selection_team)), buy_side
    if line == "over_under":
        return idx.get("over"), buy_side
    if line == "btts":
        return idx.get("btts"), buy_side
    return None, buy_side
