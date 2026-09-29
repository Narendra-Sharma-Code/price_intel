import re
from decimal import Decimal, InvalidOperation
from typing import Optional


def parse_inr(price_str: str) -> Optional[Decimal]:
    """
    Parse Indian Rupee price strings in various formats:
    - "₹1,28,490" (Croma format)
    - "₹ 119900" (Vijay Sales format: space after ₹, no comma)
    - "₹3,14,900.00" (Reliance format: comma and trailing .00)
    
    Returns Decimal or None if parsing fails.
    """
    if not price_str:
        return None
    
    try:
        # Remove ₹ symbol and any spaces
        cleaned = re.sub(r'[₹\s]', '', price_str)
        
        # Remove commas for numeric parsing
        cleaned = cleaned.replace(',', '')
        
        # Handle trailing .00 (Reliance format)
        if cleaned.endswith('.00'):
            cleaned = cleaned[:-3]
        
        # Parse as Decimal
        return Decimal(cleaned)
        
    except (ValueError, TypeError, InvalidOperation) as e:
        return None
