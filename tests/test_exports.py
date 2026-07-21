"""Tests for shared public module surfaces."""

import kalshi_auto_trader
from kalshi_auto_trader import ledger, orders, probability, risk, settings, strategy, text
from kalshi_auto_trader.kalshi import client
from kalshi_auto_trader.world_cup import markets, model, trader


def test_shared_modules_export_expected_entry_points():
    expected = {
        orders: {
            "build_order_params",
            "contracts_for_order_cap",
            "contracts_for_stake",
            "estimated_order_cost",
            "finite_price_cents",
            "limit_price_field",
            "limit_risk_cost",
            "limit_order_price",
            "market_buy_max_cost",
            "market_risk_cost",
            "max_order_cost_cents",
            "nonnegative_price_cents",
            "normalize_order_action",
            "order_action_is_valid",
            "order_count_is_valid",
            "order_params_template",
            "order_side_is_valid",
            "order_type_is_valid",
            "normalize_order_side",
            "normalize_order_type",
            "stable_client_order_id",
            "tradable_price_cents",
            "valid_buy_max_cost",
            "valid_limit_price_cents",
        },
        probability: {
            "cents_to_probability",
            "clamp_probability",
            "edge_clears_threshold",
            "finite_number",
            "is_probability",
            "probability_complement",
            "probability_edge",
            "probability_to_cents",
        },
        risk: {
            "balance_covers_cost",
            "budget_usage_fraction",
            "cents_to_dollars",
            "cost_to_cents",
            "dollars_to_cents",
            "finite_amount",
            "nonnegative_finite",
            "planned_total_cost",
            "remaining_run_budget",
            "run_budget_allows",
            "run_budget_remaining_after",
        },
        ledger: {
            "append_order",
            "is_pending_status",
            "is_settled_status",
            "market_winner",
            "settlement_status",
            "settlement_profit",
            "settlement_won",
            "settle_pending",
        },
        settings: {"ORDER_TYPE", "MAX_TOTAL_COST"},
        strategy: {"StrategyMetadata"},
        text: {"has_text", "normalize_optional_text", "normalize_required_text"},
        client: {"KalshiClient"},
        model: {"Bet", "flag_bets", "meets_edge_threshold", "parse_kickoff_utc"},
        markets: {
            "build_market_index",
            "event_token",
            "first_price_cents",
            "market_text",
            "resolve_order",
            "team_key",
        },
        trader: {"plan_bets", "parse_args"},
    }
    for module, names in expected.items():
        assert names <= set(module.__all__)


def test_package_exports_text_module():
    assert "text" in kalshi_auto_trader.__all__


def test_package_exports_probability_module():
    assert "probability" in kalshi_auto_trader.__all__
