import pytest
from decimal import Decimal
from scrapers.reliance import RelianceDigitalAdapter
from scrapers.types import RawListing, RawOffer


@pytest.fixture
def reliance_adapter():
    return RelianceDigitalAdapter()


@pytest.fixture
def reliance_listing_html():
    """Load the Reliance Digital listing HTML fixture"""
    with open('tests/fixtures/reliance/reliance_listing.html', 'r') as f:
        return f.read()


@pytest.fixture
def reliance_offers_html():
    """Load the Reliance Digital offers HTML fixture"""
    with open('tests/fixtures/reliance/reliance_offers.html', 'r') as f:
        return f.read()


def test_parse_listings(reliance_adapter, reliance_listing_html):
    """Test that we can parse listings from HTML"""
    listings = reliance_adapter.parse_listing(reliance_listing_html)
    
    # Should parse multiple products
    assert len(listings) > 0
    
    # Check that all listings are RawListing instances
    for listing in listings:
        assert isinstance(listing, RawListing)


def test_product_count(reliance_adapter, reliance_listing_html):
    """Test that we get the expected number of products"""
    listings = reliance_adapter.parse_listing(reliance_listing_html)
    
    # Based on the fixture, there should be 3 products
    assert len(listings) == 3


def test_product_name_parsing(reliance_adapter, reliance_listing_html):
    """Test that product names are parsed correctly (no parentheses format)"""
    listings = reliance_adapter.parse_listing(reliance_listing_html)
    
    # Find iPhone 18 Pro to test
    iphone_18_pro = None
    for listing in listings:
        if "iPhone 18 Pro" in listing.product_name:
            iphone_18_pro = listing
            break
    
    assert iphone_18_pro is not None
    assert "iPhone 18 Pro" in iphone_18_pro.model
    assert "2 TB" in iphone_18_pro.storage
    assert "Glacier" in iphone_18_pro.colour


def test_product_name_without_apple_prefix(reliance_adapter, reliance_listing_html):
    """Test that 'Apple ' prefix is stripped from model"""
    listings = reliance_adapter.parse_listing(reliance_listing_html)
    
    for listing in listings:
        # Model should not start with "Apple "
        if listing.model:
            assert not listing.model.startswith("Apple ")


def test_sku_extraction(reliance_adapter, reliance_listing_html):
    """Test that SKUs are extracted from URLs (trailing numeric id)"""
    listings = reliance_adapter.parse_listing(reliance_listing_html)
    
    # Check that all listings have SKUs
    for listing in listings:
        assert listing.sku is not None
        assert listing.sku.isdigit()  # Should be numeric


def test_price_format_parsing(reliance_adapter, reliance_listing_html):
    """Test that Reliance price format (₹3,14,900.00) is parsed correctly"""
    listings = reliance_adapter.parse_listing(reliance_listing_html)
    
    for listing in listings:
        assert listing.selling_price is not None
        assert isinstance(listing.selling_price, Decimal)


def test_no_mrp_on_listing(reliance_adapter, reliance_listing_html):
    """Test that MRP is None on Reliance listing page"""
    listings = reliance_adapter.parse_listing(reliance_listing_html)
    
    # All items should have mrp=None
    for listing in listings:
        assert listing.mrp is None


def test_no_discount_on_listing(reliance_adapter, reliance_listing_html):
    """Test that discount is None on Reliance listing page"""
    listings = reliance_adapter.parse_listing(reliance_listing_html)
    
    # All items should have discount=None
    for listing in listings:
        assert listing.discount is None


def test_availability_default(reliance_adapter, reliance_listing_html):
    """Test that availability defaults to 'In Stock' (assumption, not scraped)"""
    listings = reliance_adapter.parse_listing(reliance_listing_html)
    
    for listing in listings:
        assert listing.availability == "In Stock"


def test_source_field(reliance_adapter, reliance_listing_html):
    """Test that source field is set correctly"""
    listings = reliance_adapter.parse_listing(reliance_listing_html)
    
    for listing in listings:
        assert listing.source == "reliance"


def test_currency_field(reliance_adapter, reliance_listing_html):
    """Test that currency is set to INR"""
    listings = reliance_adapter.parse_listing(reliance_listing_html)
    
    for listing in listings:
        assert listing.currency == "INR"


def test_offers_parsing(reliance_adapter, reliance_offers_html):
    """Test that offers are parsed from separate offers page"""
    offers = reliance_adapter.parse_offers(reliance_offers_html)
    
    # Should parse at least some offers
    assert len(offers) > 0
    
    # Check that all offers are RawOffer instances
    for offer in offers:
        assert isinstance(offer, RawOffer)


def test_bank_extraction(reliance_adapter, reliance_offers_html):
    """Test that bank names are extracted from offers when present"""
    offers = reliance_adapter.parse_offers(reliance_offers_html)
    
    # Check that offers were parsed
    assert len(offers) > 0
    
    # The fixture should have bank offers (HDFC, Axis)
    # Check that at least some offers have offer_type="bank_offer"
    bank_offers = [o for o in offers if o.offer_type == "bank_offer"]
    assert len(bank_offers) > 0


def test_offer_text_format(reliance_adapter, reliance_offers_html):
    """Test that offer text combines title and description"""
    offers = reliance_adapter.parse_offers(reliance_offers_html)
    
    for offer in offers:
        assert offer.offer_text is not None
        assert len(offer.offer_text) > 0


def test_filter_by_query(reliance_adapter, reliance_listing_html):
    """Test filtering listings by query"""
    listings = reliance_adapter.parse_listing(reliance_listing_html, query="iPhone 18 Pro")
    
    # Should only contain iPhone 18 Pro models
    for listing in listings:
        assert "iPhone 18 Pro" in listing.product_name


def test_adapter_name(reliance_adapter):
    """Test that adapter name is set correctly"""
    assert reliance_adapter.name == "reliance"