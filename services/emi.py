from decimal import Decimal, ROUND_HALF_UP
from typing import Dict
from dataclasses import dataclass


@dataclass
class EMIResult:
    """Result of EMI calculation"""
    emi_monthly: Decimal
    total_repayment: Decimal
    total_interest: Decimal


def calculate_emi(
    principal: Decimal,
    annual_rate: Decimal,
    tenure_months: int
) -> EMIResult:
    """
    Calculate EMI using the standard reducing-balance formula.
    
    Formula: EMI = P * r * (1 + r)^n / ((1 + r)^n - 1)
    Where:
    - P = principal (loan amount)
    - r = monthly interest rate (annual_rate / 12 / 100)
    - n = tenure in months
    
    If annual_rate == 0, EMI = P / n (no-cost EMI).
    
    All calculations use Decimal for precision.
    Results are rounded to nearest rupee.
    """
    if principal <= 0:
        return EMIResult(
            emi_monthly=Decimal('0'),
            total_repayment=Decimal('0'),
            total_interest=Decimal('0')
        )
    
    if tenure_months <= 0:
        return EMIResult(
            emi_monthly=principal,
            total_repayment=principal,
            total_interest=Decimal('0')
        )
    
    # Handle zero interest rate (no-cost EMI)
    if annual_rate == 0:
        emi_monthly = (principal / Decimal(tenure_months)).quantize(
            Decimal('1'), rounding=ROUND_HALF_UP
        )
        total_repayment = emi_monthly * Decimal(tenure_months)
        total_interest = Decimal('0')
        
        return EMIResult(
            emi_monthly=emi_monthly,
            total_repayment=total_repayment,
            total_interest=total_interest
        )
    
    # Calculate monthly interest rate
    monthly_rate = annual_rate / Decimal('12') / Decimal('100')
    
    # Calculate (1 + r)^n
    one_plus_r = Decimal('1') + monthly_rate
    one_plus_r_n = one_plus_r ** tenure_months
    
    # Calculate EMI using the formula
    numerator = principal * monthly_rate * one_plus_r_n
    denominator = one_plus_r_n - Decimal('1')
    
    emi_monthly = (numerator / denominator).quantize(
        Decimal('1'), rounding=ROUND_HALF_UP
    )
    
    # Calculate total repayment and interest
    total_repayment = emi_monthly * Decimal(tenure_months)
    total_interest = total_repayment - principal
    
    return EMIResult(
        emi_monthly=emi_monthly,
        total_repayment=total_repayment,
        total_interest=total_interest
    )
