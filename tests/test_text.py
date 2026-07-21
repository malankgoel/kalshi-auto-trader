"""Tests for shared text normalization helpers."""

import pytest

from kalshi_auto_trader import text


def test_has_text_predicate_checks_stripped_values():
    assert text.has_text("  ticker ")
    assert text.has_text(123)
    assert not text.has_text(None)
    assert not text.has_text("   ")


def test_optional_text_normalizer_strips_and_blanks():
    assert text.normalize_optional_text(None) is None
    assert text.normalize_optional_text("  France ") == "France"
    assert text.normalize_optional_text("   ") is None


def test_optional_text_normalizer_stringifies_values():
    assert text.normalize_optional_text(123) == "123"


def test_required_text_normalizer_rejects_blank_values():
    with pytest.raises(ValueError, match="ticker"):
        text.normalize_required_text(" ", "ticker")
