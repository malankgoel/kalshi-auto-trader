"""Tests for shared text normalization helpers."""

import pytest

from kalshi_auto_trader import text


def test_optional_text_normalizer_strips_and_blanks():
    assert text.normalize_optional_text(None) is None
    assert text.normalize_optional_text("  France ") == "France"
    assert text.normalize_optional_text("   ") is None


def test_required_text_normalizer_rejects_blank_values():
    with pytest.raises(ValueError, match="ticker"):
        text.normalize_required_text(" ", "ticker")
