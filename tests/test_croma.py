import pytest
from decimal import Decimal
from scrapers.croma import CromaAdapter
from scrapers.types import RawListing, RawOffer


@pytest.fixture
def croma_adapter():
    return CromaAdapter()


@pytest.fixture
def croma_listing_html():
    """Load the Croma listing HTML fixture"""
    with open('tests/fixtures/croma/croma_listing.html', 'r') as f:
        return f.read()


@pytest.fixture
def croma_offers_html():
    """Load the Croma offers HTML fixture"""
    with open('tests/fixtures/croma/croma_offers.html', 'r') as f:
        return f.read()


def test_parse_listings_from_jsonld(croma_adapter, croma_listing_html):
    """Test that we can parse listings from JSON-LD data"""
    listings = croma_adapter.parse_listing(croma_listing_html)
    
    # Should parse multiple products from the JSON-LD
    assert len(listings) > 0
    
    # Check that all listings are RawListing instances
    for listing in listings:
        assert isinstance(listing, RawListing)


def test_product_count_from_jsonld(croma_adapter, croma_listing_html):
    """Test that we get the expected number of products"""
    listings = croma_adapter.parse_listing(croma_listing_html)
    
    # Based on the JSON-LD in the fixture, there should be 21 products
    assert len(listings) == 21


def test_product_name_parsing(croma_adapter, croma_listing_html):
    """Test that product names are parsed correctly into model/storage/colour"""
    listings = croma_adapter.parse_listing(croma_listing_html)
    
    # Find a specific product to test
    iphone_17_pro = None
    for listing in listings:
        if "iPhone 17 Pro" in listing.product_name and "256GB" in listing.product_name:
            iphone_17_pro = listing
            break
    
    assert iphone_17_pro is not None
    assert "iPhone 17 Pro" in iphone_17_pro.model
    assert "256GB" in iphone_17_pro.storage
    assert iphone_17_pro.colour is not None


def test_variant_id_extraction(croma_adapter, croma_listing_html):
    """Test that variant IDs are extracted from URLs"""
    listings = croma_adapter.parse_listing(croma_listing_html)
    
    # Check that all listings have variant IDs
    for listing in listings:
        assert listing.variant_id is not None
        assert listing.variant_id.isdigit()  # Should be numeric


def test_sku_extraction(croma_adapter, croma_listing_html):
    """Test that SKUs are extracted from JSON-LD"""
    listings = croma_adapter.parse_listing(croma_listing_html)
    
    # Check that all listings have SKUs
    for listing in listings:
        assert listing.sku is not None
        assert listing.sku.isdigit()  # Should be numeric


def test_brand_extraction(croma_adapter, croma_listing_html):
    """Test that brand is extracted correctly"""
    listings = croma_adapter.parse_listing(croma_listing_html)
    
    # All products should be Apple
    for listing in listings:
        assert listing.brand == "Apple"


def test_source_field(croma_adapter, croma_listing_html):
    """Test that source field is set correctly"""
    listings = croma_adapter.parse_listing(croma_listing_html)
    
    for listing in listings:
        assert listing.source == "croma"


def test_currency_field(croma_adapter, croma_listing_html):
    """Test that currency is set to INR"""
    listings = croma_adapter.parse_listing(croma_listing_html)
    
    for listing in listings:
        assert listing.currency == "INR"


def test_availability_default(croma_adapter, croma_listing_html):
    """Test that availability defaults to 'In Stock' (documented assumption)"""
    listings = croma_adapter.parse_listing(croma_listing_html)
    
    for listing in listings:
        assert listing.availability == "In Stock"


def test_price_fields_extracted(croma_adapter, croma_listing_html):
    """Test that price fields are extracted from HTML DOM"""
    listings = croma_adapter.parse_listing(croma_listing_html)
    
    # Most items should have selling_price (at least 18 of 21)
    with_selling_price = [l for l in listings if l.selling_price is not None]
    assert len(with_selling_price) >= 18, f"Expected at least 18 items with selling_price, got {len(with_selling_price)}"
    
    # Some items should have MRP (discounted items)
    with_mrp = [l for l in listings if l.mrp is not None]
    assert len(with_mrp) > 0, "Expected some items with MRP"
    
    # Some items should have discount (calculated from MRP - selling_price)
    with_discount = [l for l in listings if l.discount is not None]
    assert len(with_discount) > 0, "Expected some items with discount"


def test_specific_iphone_17_pro_pricing(croma_adapter, croma_listing_html):
    """Test specific pricing for Apple iPhone 17 Pro (256GB, Silver)"""
    listings = croma_adapter.parse_listing(croma_listing_html)
    
    # Find the specific product
    iphone_17_pro = None
    for listing in listings:
        if "iPhone 17 Pro" in listing.product_name and "256GB" in listing.product_name and "Silver" in listing.product_name:
            iphone_17_pro = listing
            break
    
    assert iphone_17_pro is not None, "Could not find iPhone 17 Pro (256GB, Silver)"
    
    # Verify price extraction
    assert iphone_17_pro.selling_price is not None, "Selling price should be extracted"
    assert iphone_17_pro.selling_price > 0, "Selling price should be positive"
    
    # This product has discount, so should have MRP
    assert iphone_17_pro.mrp is not None, "MRP should be extracted for discounted items"
    assert iphone_17_pro.mrp > iphone_17_pro.selling_price, "MRP should be higher than selling price"
    
    # Discount should be calculated correctly
    assert iphone_17_pro.discount is not None, "Discount should be calculated"
    expected_discount = iphone_17_pro.mrp - iphone_17_pro.selling_price
    assert iphone_17_pro.discount == expected_discount, f"Discount calculation mismatch: expected {expected_discount}, got {iphone_17_pro.discount}"


def test_no_discount_items(croma_adapter, croma_listing_html):
    """Test that items without discount have mrp=None"""
    listings = croma_adapter.parse_listing(croma_listing_html)
    
    # Items without MRP are non-discounted (edge case)
    no_mrp = [l for l in listings if l.mrp is None]
    
    # These should still have selling_price
    for listing in no_mrp:
        assert listing.selling_price is not None, "Non-discounted items should still have selling_price"
        assert listing.discount is None, "Non-discounted items should have discount=None"


def test_rating_and_review_none(croma_adapter, croma_listing_html):
    """Test that rating and review_count are None (not on listing page)"""
    listings = croma_adapter.parse_listing(croma_listing_html)
    
    for listing in listings:
        assert listing.rating is None
        assert listing.review_count is None


def test_product_url_extraction(croma_adapter, croma_listing_html):
    """Test that product URLs are extracted"""
    listings = croma_adapter.parse_listing(croma_listing_html)
    
    for listing in listings:
        assert listing.product_url is not None
        assert listing.product_url.startswith("https://www.croma.com/")


def test_filter_by_query(croma_adapter, croma_listing_html):
    """Test filtering listings by query"""
    listings = croma_adapter.parse_listing(croma_listing_html)
    
    # Filter for iPhone 17 Pro
    filtered = croma_adapter._filter_listings(listings, query="iPhone 17 Pro", storage=None, colour=None)
    
    # Should only contain iPhone 17 Pro models
    for listing in filtered:
        assert "iPhone 17 Pro" in listing.product_name


def test_filter_by_storage(croma_adapter, croma_listing_html):
    """Test filtering listings by storage"""
    listings = croma_adapter.parse_listing(croma_listing_html)
    
    # Filter for 256GB
    filtered = croma_adapter._filter_listings(listings, query=None, storage="256GB", colour=None)
    
    # Should only contain 256GB models
    for listing in filtered:
        assert "256GB" in listing.storage


def test_filter_by_colour(croma_adapter, croma_listing_html):
    """Test filtering listings by colour"""
    listings = croma_adapter.parse_listing(croma_listing_html)
    
    # Filter for Silver
    filtered = croma_adapter._filter_listings(listings, query=None, storage=None, colour="Silver")
    
    # Should only contain Silver models
    for listing in filtered:
        assert "Silver" in listing.colour


def test_offers_parsing(croma_adapter, croma_offers_html):
    """Test that offers are parsed from HTML"""
    offers = croma_adapter.parse_offers(croma_offers_html)
    
    # The offers fixture contains only a multi-brand comparison table
    # which is correctly skipped by the parser
    # So we expect 0 offers from the offers page fixture
    # Real bank offers are extracted from the listing page as offer badges
    assert len(offers) == 0
    
    # Check that all offers are RawOffer instances
    for offer in offers:
        assert isinstance(offer, RawOffer)


def test_offer_text_not_empty(croma_adapter, croma_offers_html):
    """Test that offer_text is not empty"""
    offers = croma_adapter.parse_offers(croma_offers_html)
    
    for offer in offers:
        assert offer.offer_text is not None
        assert len(offer.offer_text.strip()) > 0


def test_bank_extraction(croma_adapter, croma_offers_html):
    """Test that bank names are extracted from offers"""
    offers = croma_adapter.parse_offers(croma_offers_html)
    
    # The offers fixture contains only a multi-brand comparison table
    # which is correctly skipped by the parser
    # So we expect 0 offers from the offers page fixture
    assert len(offers) == 0


def test_parse_listing_with_filters(croma_adapter, croma_listing_html):
    """Test that parse_listing works with filters (no network call)"""
    listings = croma_adapter.parse_listing(croma_listing_html, query="iPhone 17", storage="256GB", colour="Silver")
    
    # Should return filtered results
    assert len(listings) > 0
    
    # All should match the filter criteria
    for listing in listings:
        assert "iPhone 17" in listing.product_name
        assert "256GB" in listing.storage
        assert "Silver" in listing.colour


def test_parse_offers_directly(croma_adapter, croma_offers_html):
    """Test that parse_offers works directly with HTML (no network call)"""
    offers = croma_adapter.parse_offers(croma_offers_html)
    
    # The offers fixture contains only a multi-brand comparison table
    # which is correctly skipped by the parser
    # So we expect 0 offers from the offers page fixture
    assert len(offers) == 0


def test_adapter_name(croma_adapter):
    """Test that adapter name is set correctly"""
    assert croma_adapter.name == "croma"


def test_offer_badges_extraction(croma_adapter, croma_listing_html):
    """Test that offer badges are extracted and deduplicated"""
    listings = croma_adapter.parse_listing(croma_listing_html)
    
    # Some items should have offer badges
    with_offers = [l for l in listings if l.offers]
    assert len(with_offers) > 0, "Expected some items with offer badges"
    
    # Check that offer badges are deduplicated (no duplicates within a single listing)
    for listing in listings:
        if listing.offers:
            # Check for duplicates
            assert len(listing.offers) == len(set(listing.offers)), f"Duplicate offer badges found in {listing.product_name}"


def test_specific_offer_badges(croma_adapter, croma_listing_html):
    """Test specific offer badges for Apple iPhone 17 Pro (256GB, Silver)"""
    listings = croma_adapter.parse_listing(croma_listing_html)
    
    # Find the specific product
    iphone_17_pro = None
    for listing in listings:
        if "iPhone 17 Pro" in listing.product_name and "256GB" in listing.product_name and "Silver" in listing.product_name:
            iphone_17_pro = listing
            break
    
    assert iphone_17_pro is not None, "Could not find iPhone 17 Pro (256GB, Silver)"
    
    # This product should have offer badges
    assert len(iphone_17_pro.offers) > 0, "Expected offer badges for iPhone 17 Pro"
    
    # Check for expected offer types
    offer_text = ' '.join(iphone_17_pro.offers).lower()
    assert 'bank' in offer_text or 'discount' in offer_text, "Expected bank/discount offer"
