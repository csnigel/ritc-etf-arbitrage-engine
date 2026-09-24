"""Offline regression tests for execution and risk safety invariants."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "etf_arbitrage_engine.py"


def load_engine() -> ModuleType:
    spec = importlib.util.spec_from_file_location("etf_arbitrage_engine", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves annotations through sys.modules during import.
    import sys

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


engine = load_engine()


def result(
    *,
    filled: int,
    vwap: float,
    requested: int | None = None,
) -> object:
    return engine.OrderResult(
        ticker=engine.RITC,
        action="BUY",
        requested=filled if requested is None else requested,
        filled=filled,
        vwap=vwap,
        status="FILLED",
    )


def usd_book(bid: float = 1.24, ask: float = 1.25) -> object:
    return engine.Book(
        ticker=engine.USD,
        bids=[engine.Level(price=bid, quantity=5_000_000)],
        asks=[engine.Level(price=ask, quantity=5_000_000)],
    )


def market_state(*, usd_position: int = 0) -> object:
    return engine.MarketState(
        period=1,
        tick=100,
        ticks_per_period=300,
        status="ACTIVE",
        seconds_remaining=200,
        books={engine.USD: usd_book()},
        positions={engine.USD: usd_position, engine.RITC: 0},
        security_rows=[],
    )


def test_import_is_safe_and_live_trading_defaults_off() -> None:
    assert engine.LIVE_TRADING is False
    assert not (SOURCE.parent / "ritcx_logs").exists()


def test_aggregate_fill_vwap_returns_none_for_zero_quantity() -> None:
    assert engine.aggregate_fill_vwap([], engine.RITC, "BUY", 0) is None


def test_aggregate_fill_vwap_exact_fills() -> None:
    fills = [result(filled=400, vwap=24.90), result(filled=600, vwap=25.10)]
    assert engine.aggregate_fill_vwap(fills, engine.RITC, "BUY", 1_000) == pytest.approx(25.02)


def test_partial_fills_do_not_create_fake_reconciled_vwap() -> None:
    fills = [result(filled=400, vwap=24.90), result(filled=500, vwap=25.10)]
    assert engine.aggregate_fill_vwap(fills, engine.RITC, "BUY", 1_000) is None


def test_weighted_gross_calculation() -> None:
    gross, _ = engine.weighted_risk(
        {engine.BULL: 10_000, engine.BEAR: -5_000, engine.RITC: 2_000}
    )
    assert gross == 19_000


def test_weighted_net_calculation() -> None:
    _, net = engine.weighted_risk(
        {engine.BULL: 10_000, engine.BEAR: -5_000, engine.RITC: 2_000}
    )
    assert net == 9_000


def test_oversized_trade_is_rejected_by_local_limits() -> None:
    assert not engine.risk_allows(
        {},
        {engine.BULL: engine.MAX_WEIGHTED_GROSS + 1},
    )


def test_inventory_reducing_trade_can_remain_above_gross_cap() -> None:
    positions = {engine.BULL: 130_000, engine.BEAR: -130_000, engine.RITC: 0}
    deltas = {engine.BULL: -10_000, engine.BEAR: 10_000}
    assert not engine.risk_allows(positions, deltas)
    assert engine.risk_allows_or_reduces(positions, deltas)


def test_converter_rejects_non_lot_quantity() -> None:
    basket = engine.Candidate(
        kind="TENDER_BASKET",
        label="test",
        quantity=15_000,
        total_pnl_cad=100_000.0,
        average_edge_cad=1.0,
        score_cad=100_000.0,
    )
    assert engine.converter_candidate(market_state(), basket, "BUY") is None


def test_converter_cost_is_included_in_route_profitability() -> None:
    basket = engine.Candidate(
        kind="TENDER_BASKET",
        label="test",
        quantity=20_000,
        total_pnl_cad=100_000.0,
        average_edge_cad=5.0,
        score_cad=100_000.0,
    )
    candidate = engine.converter_candidate(market_state(), basket, "BUY")
    assert candidate is not None
    expected_cost = 2 * engine.CONVERTER_COST_USD_PER_USE * 1.25
    assert candidate.converter_quantity % engine.CONVERTER_LOT == 0
    assert candidate.converter_uses == 2
    assert candidate.converter_cost_cad == pytest.approx(expected_cost)
    assert candidate.total_pnl_cad == pytest.approx(100_000.0 - expected_cost)


@pytest.mark.parametrize(
    ("usd_position", "expected_action"),
    [(6_000, "SELL"), (-6_000, "BUY")],
)
def test_fx_target_has_correct_direction(
    monkeypatch: pytest.MonkeyPatch,
    usd_position: int,
    expected_action: str,
) -> None:
    calls: list[tuple[str, str, int]] = []

    class Audit:
        def action(self, **_: object) -> None:
            return None

    class Client:
        audit = Audit()

        def set_state_context(self, _: object) -> None:
            return None

    def fake_submit(
        _client: object,
        ticker: str,
        action: str,
        quantity: int,
        **_: object,
    ) -> int:
        calls.append((ticker, action, quantity))
        return quantity

    monkeypatch.setattr(engine, "submit_in_chunks", fake_submit)
    filled = engine.hedge_fx_to_target(Client(), market_state(usd_position=usd_position))

    assert filled == 6_000
    assert calls == [(engine.USD, expected_action, 6_000)]


def test_case_state_resets_only_on_new_active_transition() -> None:
    has_been_active = False
    reset_events = 0
    for status in ["STOPPED", "ACTIVE", "ACTIVE", "ACTIVE", "STOPPED", "ACTIVE"]:
        if engine.is_new_active_case(has_been_active, status):
            reset_events += 1
            has_been_active = True
        elif status != "ACTIVE":
            has_been_active = False

    assert reset_events == 2
