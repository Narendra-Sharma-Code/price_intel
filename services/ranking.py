from decimal import Decimal
from typing import List, Dict, Any
from dataclasses import dataclass

from scrapers.types import RawListing


@dataclass
class RankedListing:
    """A listing with its effective price and rank"""
    listing: RawListing
    effective_price: Decimal
    rank: int


def rank_listings(
    grouped_listings: Dict[str, Any],
    effective_prices: Dict[str, Decimal]
) -> List[RankedListing]:
    """
    Rank listings by effective price (ascending).
    
    Args:
        grouped_listings: Dict mapping variant_id to match results (with listings)
        effective_prices: Dict mapping variant_id to effective price
    
    Returns:
        List of RankedListing sorted by effective_price ascending
    """
    ranked = []
    
    for variant_id, match_result in grouped_listings.items():
        for listing in match_result.listings:
            # Get effective price for this listing
            # Use variant_id if available, otherwise skip
            if variant_id in effective_prices:
                ranked.append(RankedListing(
                    listing=listing,
                    effective_price=effective_prices[variant_id],
                    rank=0  # Will be assigned after sorting
                ))
    
    # Sort by effective price ascending
    ranked.sort(key=lambda x: x.effective_price)
    
    # Assign ranks
    for i, item in enumerate(ranked, start=1):
        item.rank = i
    
    return ranked
