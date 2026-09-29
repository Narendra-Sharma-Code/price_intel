import pytest
from decimal import Decimal
from datetime import datetime, timezone

from services.matcher import build_variant_id, group_listings, normalize_storage, normalize_colour
from scrapers.types import RawListing


def test_normalize_storage():
    """Test storage normalization"""
    assert normalize_storage("256GB") == "256gb"
    assert normalize_storage("256 GB") == "256gb"
    assert normalize_storage("256  GB") == "256gb"
    assert normalize_storage("") == ""
    assert normalize_storage(None) == ""


def test_normalize_colour():
    """Test colour normalization"""
    assert normalize_colour("Silver") == "silver"
    assert normalize_colour("Space Black") == "spaceblack"
    assert normalize_colour("") == ""
    assert normalize_colour(None) == ""


def test_build_variant_id():
    """Test variant ID construction"""
    # Basic case
    vid = build_variant_id("Apple", "iPhone 17 Pro", "256GB", "Silver")
    assert vid == "apple-iphone-17-pro-256gb-silver"
    
    # With spaces in storage
    vid = build_variant_id("Apple", "iPhone 17 Pro", "256 GB", "Silver")
    assert vid == "apple-iphone-17-pro-256gb-silver"
    
    # Missing optional fields
    vid = build_variant_id("Apple", "iPhone 17 Pro", "256GB", None)
    assert vid == "apple-iphone-17-pro-256gb"
    
    vid = build_variant_id("Apple", "iPhone 17 Pro", None, None)
    assert vid == "apple-iphone-17-pro"


def test_group_listings_exact_match():
    """Test grouping listings with exact matches"""
    listings = [
        RawListing(
            variant_id="1",
            source="croma",
            product_name="Apple iPhone 17 Pro (256GB, Silver)",
            brand="Apple",
            model="iPhone 17 Pro",
            storage="256GB",
            colour="Silver",
            sku="123",
            product_url="http://example.com/1",
            currency="INR",
            selling_price=Decimal("128490"),
            mrp=Decimal("134900"),
            discount=Decimal("6410"),
            availability="In Stock",
            rating=None,
            review_count=None,
            scraped_at=datetime.now(timezone.utc)
        ),
        RawListing(
            variant_id="2",
            source="vijaysales",
            product_name="Apple iPhone 17 Pro (256 GB Storage, Silver)",
            brand="Apple",
            model="iPhone 17 Pro",
            storage="256 GB",
            colour="Silver",
            sku="456",
            product_url="http://example.com/2",
            currency="INR",
            selling_price=Decimal("119900"),
            mrp=Decimal("129900"),
            discount=Decimal("10000"),
            availability="In Stock",
            rating=None,
            review_count=None,
            scraped_at=datetime.now(timezone.utc)
        )
    ]
    
    groups = group_listings(listings)
    
    # Should group together despite storage format difference
    assert len(groups) == 1
    variant_id = list(groups.keys())[0]
    assert len(groups[variant_id].listings) == 2
    assert groups[variant_id].confidence == "exact"


def test_group_listings_cross_source():
    """Test that same phone named differently across sources still groups together"""
    listings = [
        # Croma format
        RawListing(
            variant_id="1",
            source="croma",
            product_name="Apple iPhone 17 Pro (256GB, Silver)",
            brand="Apple",
            model="iPhone 17 Pro",
            storage="256GB",
            colour="Silver",
            sku="123",
            product_url="http://example.com/1",
            currency="INR",
            selling_price=Decimal("128490"),
            mrp=Decimal("134900"),
            discount=Decimal("6410"),
            availability="In Stock",
            rating=None,
            review_count=None,
            scraped_at=datetime.now(timezone.utc)
        ),
        # Vijay Sales format (with "Storage" word and space)
        RawListing(
            variant_id="2",
            source="vijaysales",
            product_name="Apple iPhone 17 Pro (256 GB Storage, Silver)",
            brand="Apple",
            model="iPhone 17 Pro",
            storage="256 GB",
            colour="Silver",
            sku="456",
            product_url="http://example.com/2",
            currency="INR",
            selling_price=Decimal("119900"),
            mrp=Decimal("129900"),
            discount=Decimal("10000"),
            availability="In Stock",
            rating=None,
            review_count=None,
            scraped_at=datetime.now(timezone.utc)
        ),
        # Reliance format (no parentheses)
        RawListing(
            variant_id="3",
            source="reliance",
            product_name="Apple iPhone 17 Pro 256GB, Silver",
            brand="Apple",
            model="iPhone 17 Pro",
            storage="256GB",
            colour="Silver",
            sku="789",
            product_url="http://example.com/3",
            currency="INR",
            selling_price=Decimal("130000"),
            mrp=None,
            discount=None,
            availability="In Stock",
            rating=None,
            review_count=None,
            scraped_at=datetime.now(timezone.utc)
        )
    ]
    
    groups = group_listings(listings)
    
    # All three should group together under same variant_id
    assert len(groups) == 1
    variant_id = list(groups.keys())[0]
    assert len(groups[variant_id].listings) == 3
    assert groups[variant_id].confidence == "exact"
    
    # Check sources are represented
    sources = {lst.source for lst in groups[variant_id].listings}
    assert sources == {"croma", "vijaysales", "reliance"}


def test_group_listings_different_products():
    """Test that different products don't group together"""
    listings = [
        RawListing(
            variant_id="1",
            source="croma",
            product_name="Apple iPhone 17 Pro (256GB, Silver)",
            brand="Apple",
            model="iPhone 17 Pro",
            storage="256GB",
            colour="Silver",
            sku="123",
            product_url="http://example.com/1",
            currency="INR",
            selling_price=Decimal("128490"),
            mrp=Decimal("134900"),
            discount=Decimal("6410"),
            availability="In Stock",
            rating=None,
            review_count=None,
            scraped_at=datetime.now(timezone.utc)
        ),
        RawListing(
            variant_id="2",
            source="croma",
            product_name="Apple iPhone 17 (256GB, Silver)",
            brand="Apple",
            model="iPhone 17",
            storage="256GB",
            colour="Silver",
            sku="456",
            product_url="http://example.com/2",
            currency="INR",
            selling_price=Decimal("99900"),
            mrp=Decimal("104900"),
            discount=Decimal("5000"),
            availability="In Stock",
            rating=None,
            review_count=None,
            scraped_at=datetime.now(timezone.utc)
        )
    ]
    
    groups = group_listings(listings)
    
    # Should create two separate groups
    assert len(groups) == 2
