import re
from decimal import Decimal
from typing import Dict, Optional, List
from dataclasses import dataclass

from scrapers.types import RawListing, RawOffer


@dataclass
class OfferParseResult:
    """Result of parsing offer text"""
    bank: Optional[str]
    discount: Optional[Decimal]
    has_emi: bool
    raw_text: str


@dataclass
class EffectivePriceResult:
    """Result of computing effective price with offers"""
    effective_price: Decimal
    applied_offer: Optional[RawOffer]
    conditional_offers: List[RawOffer]


def parse_offer_text(raw_text: str) -> OfferParseResult:
    """
    Extract structured fields from offer text using simple keyword/regex rules.
    
    Always keeps raw_text as the reliable field.
    """
    if not raw_text:
        return OfferParseResult(
            bank=None,
            discount=None,
            has_emi=False,
            raw_text=raw_text
        )
    
    bank = None
    discount = None
    has_emi = False
    
    # Extract bank name (common Indian banks)
    bank_patterns = [
        r'(HDFC|ICICI|SBI|Axis|Kotak|HSBC|Citibank|Standard Chartered)',
        r'([A-Z][a-z]+\s+[Bb]ank)'
    ]
    
    for pattern in bank_patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            bank = match.group(1).strip()
            break
    
    # Extract discount amount (e.g., "Rs. 4000", "₹4000", "10%")
    # First try for percentage
    discount_match = re.search(r'(\d+)%\s*(?:off|discount)', raw_text, re.IGNORECASE)
    if discount_match:
        # Store as percentage for now - would need base price to calculate
        discount = Decimal(discount_match.group(1))
    else:
        # Try for absolute amount
        amount_match = re.search(r'(?:Rs\.?|₹)\s*(\d+(?:,\d+)*)', raw_text)
        if amount_match:
            # Remove commas and parse
            amount_str = amount_match.group(1).replace(',', '')
            try:
                discount = Decimal(amount_str)
            except:
                discount = None
    
    # Check for EMI mention
    has_emi = bool(re.search(r'EMI|emi', raw_text, re.IGNORECASE))
    
    return OfferParseResult(
        bank=bank,
        discount=discount,
        has_emi=has_emi,
        raw_text=raw_text
    )


def compute_effective_price(
    listing: RawListing,
    offers: List[RawOffer],
    selected_bank: Optional[str] = None
) -> EffectivePriceResult:
    """
    Apply offers to listing price to compute effective price.
    
    Only applies offers that:
    - Have no bank restriction, OR
    - Match the selected_bank
    
    Other offers are marked as conditional.
    """
    if not listing.selling_price:
        return EffectivePriceResult(
            effective_price=Decimal('0'),
            applied_offer=None,
            conditional_offers=offers
        )
    
    effective_price = listing.selling_price
    applied_offer = None
    conditional_offers = []
    
    for offer in offers:
        # Check if offer can be applied
        can_apply = False
        
        if not offer.bank:
            # No bank restriction - can apply
            can_apply = True
        elif selected_bank and offer.bank.lower() == selected_bank.lower():
            # Bank restriction matches selected bank
            can_apply = True
        
        if can_apply:
            # Try to apply the offer
            if offer.offer_discount:
                # Direct discount amount
                effective_price = max(Decimal('0'), effective_price - offer.offer_discount)
                applied_offer = offer
            else:
                # Try to parse discount from offer text
                parsed = parse_offer_text(offer.offer_text)
                if parsed.discount:
                    # Check if it's a percentage or absolute
                    if isinstance(parsed.discount, Decimal) and parsed.discount < 100:
                        # Assume percentage
                        discount_amount = listing.selling_price * (parsed.discount / Decimal('100'))
                        effective_price = max(Decimal('0'), effective_price - discount_amount)
                        applied_offer = offer
                    else:
                        # Assume absolute amount
                        effective_price = max(Decimal('0'), effective_price - parsed.discount)
                        applied_offer = offer
        else:
            # Mark as conditional
            conditional_offers.append(offer)
    
    return EffectivePriceResult(
        effective_price=effective_price,
        applied_offer=applied_offer,
        conditional_offers=conditional_offers
    )
