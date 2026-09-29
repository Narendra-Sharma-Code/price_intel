import pytest
from decimal import Decimal
from scrapers.normalize import parse_inr


def test_parse_croma_format():
    """Test parsing Croma format: ₹1,28,490"""
    result = parse_inr("₹1,28,490")
    assert result == Decimal("128490")
    assert isinstance(result, Decimal)


def test_parse_vijaysales_format():
    """Test parsing Vijay Sales format: ₹ 119900"""
    result = parse_inr("₹ 119900")
    assert result == Decimal("119900")
    assert isinstance(result, Decimal)


def test_parse_reliance_format():
    """Test parsing Reliance format: ₹3,14,900.00"""
    result = parse_inr("₹3,14,900.00")
    assert result == Decimal("314900")
    assert isinstance(result, Decimal)


def test_parse_empty_string():
    """Test parsing empty string"""
    result = parse_inr("")
    assert result is None


def test_parse_none():
    """Test parsing None"""
    result = parse_inr(None)
    assert result is None


def test_parse_invalid_format():
    """Test parsing invalid format"""
    result = parse_inr("invalid price")
    assert result is None


def test_parse_whitespace_variations():
    """Test parsing with various whitespace"""
    result1 = parse_inr("₹ 1,28,490")
    result2 = parse_inr("₹1,28,490")
    assert result1 == result2 == Decimal("128490")


def test_parse_without_rupee_symbol():
    """Test parsing without ₹ symbol (should still work)"""
    result = parse_inr("1,28,490")
    assert result == Decimal("128490")


def test_parse_large_amount():
    """Test parsing large amount"""
    result = parse_inr("₹9,99,999.00")
    assert result == Decimal("999999")
