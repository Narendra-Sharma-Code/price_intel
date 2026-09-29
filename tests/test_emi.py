import pytest
from decimal import Decimal

from services.emi import calculate_emi


def test_calculate_emi_zero_rate():
    """Test EMI calculation with zero interest rate (no-cost EMI)"""
    result = calculate_emi(
        principal=Decimal("10000"),
        annual_rate=Decimal("0"),
        tenure_months=12
    )
    
    # No-cost EMI: EMI = principal / months
    assert result.emi_monthly == Decimal("833")  # 10000 / 12 = 833.33 -> 833
    assert result.total_repayment == Decimal("9996")  # 833 * 12
    assert result.total_interest == Decimal("0")


def test_calculate_emi_normal_rate():
    """Test EMI calculation with normal interest rate"""
    result = calculate_emi(
        principal=Decimal("100000"),
        annual_rate=Decimal("12"),  # 12% annual
        tenure_months=12
    )
    
    # Standard EMI calculation
    # Monthly rate = 12% / 12 = 1% = 0.01
    # EMI = 100000 * 0.01 * (1.01)^12 / ((1.01)^12 - 1)
    # EMI ≈ 8884.88 -> 8885
    assert result.emi_monthly == Decimal("8885")
    assert result.total_repayment == Decimal("106620")  # 8885 * 12
    assert result.total_interest == Decimal("6620")  # 106620 - 100000


def test_calculate_emi_longer_tenure():
    """Test EMI calculation with longer tenure"""
    result = calculate_emi(
        principal=Decimal("500000"),
        annual_rate=Decimal("10"),  # 10% annual
        tenure_months=24
    )
    
    assert result.emi_monthly > 0
    assert result.total_repayment > result.emi_monthly
    assert result.total_interest > 0


def test_calculate_emi_zero_principal():
    """Test EMI calculation with zero principal"""
    result = calculate_emi(
        principal=Decimal("0"),
        annual_rate=Decimal("12"),
        tenure_months=12
    )
    
    assert result.emi_monthly == Decimal("0")
    assert result.total_repayment == Decimal("0")
    assert result.total_interest == Decimal("0")


def test_calculate_emi_zero_tenure():
    """Test EMI calculation with zero tenure"""
    result = calculate_emi(
        principal=Decimal("10000"),
        annual_rate=Decimal("12"),
        tenure_months=0
    )
    
    # With zero tenure, should return principal as is
    assert result.emi_monthly == Decimal("10000")
    assert result.total_repayment == Decimal("10000")
    assert result.total_interest == Decimal("0")


def test_calculate_emi_precision():
    """Test that EMI calculations use Decimal precision"""
    result = calculate_emi(
        principal=Decimal("100000"),
        annual_rate=Decimal("12.5"),
        tenure_months=12
    )
    
    # Should return Decimal, not float
    assert isinstance(result.emi_monthly, Decimal)
    assert isinstance(result.total_repayment, Decimal)
    assert isinstance(result.total_interest, Decimal)
