import pytest
from decimal import Decimal
from datetime import datetime, timezone

from services.ranking import rank_listings, RankedListing
from scrapers.types import RawListing
from services.matcher import MatchResult


def test_rank_listings_by_price():
    """Test that listings are ranked by effective price ascending"""
    # Create mock grouped listings
    listing1 = RawListing(
        variant_id="1",
        source="croma",
        product_name="Product A",
        brand="Test",
        model="Test",
        storage="256GB",
        colour="Silver",
        sku="123",
        product_url="http://example.com/1",
        currency="INR",
        selling_price=Decimal("12000"),
        mrp=Decimal("13000"),
        discount=Decimal("1000"),
        availability="In Stock",
        rating=None,
        review_count=None,
        scraped_at=datetime.now(timezone.utc)
    )
    
    listing2 = RawListing(
        variant_id="2",
        source="vijaysales",
        product_name="Product A",
        brand="Test",
        model="Test",
        storage="256GB",
        colour="Silver",
        sku="456",
        product_url="http://example.com/2",
        currency="INR",
        selling_price=Decimal("10000"),
        mrp=Decimal("11000"),
        discount=Decimal("1000"),
        availability="In Stock",
        rating=None,
        review_count=None,
        scraped_at=datetime.now(timezone.utc)
    )
    
    listing3 = RawListing(
        variant_id="3",
        source="reliance",
        product_name="Product A",
        brand="Test",
        model="Test",
        storage="256GB",
        colour="Silver",
        sku="789",
        product_url="http://example.com/3",
        currency="INR",
        selling_price=Decimal("11000"),
        mrp=Decimal("12000"),
        discount=Decimal("1000"),
        availability="In Stock",
        rating=None,
        review_count=None,
        scraped_at=datetime.now(timezone.utc)
    )
    
    grouped_listings = {
        "test-variant": MatchResult(
            listings=[listing1, listing2, listing3],
            confidence="exact",
            variant_id="test-variant"
        )
    }
    
    effective_prices = {
        "test-variant": Decimal("10000")  # Assuming best effective price
    }
    
    ranked = rank_listings(grouped_listings, effective_prices)
    
    # Should return 3 listings
    assert len(ranked) == 3
    
    # Should be sorted by effective price (all same in this case, so order is stable)
    assert ranked[0].effective_price == Decimal("10000")
    assert ranked[1].effective_price == Decimal("10000")
    assert ranked[2].effective_price == Decimal("10000")
    
    # Ranks should be assigned
    assert ranked[0].rank == 1
    assert ranked[1].rank == 2
    assert ranked[2].rank == 3


def test_rank_listings_empty():
    """Test ranking with empty listings"""
    ranked = rank_listings({}, {})
    
    assert len(ranked) == 0
