import pytest
from decimal import Decimal
from scrapers.vijaysales import VijaySalesAdapter
from scrapers.types import RawListing, RawOffer


@pytest.fixture
def vijaysales_adapter():
    return VijaySalesAdapter()


@pytest.fixture
def vijaysales_listing_html():
    """Load the Vijay Sales listing HTML fixture"""
    with open('tests/fixtures/vijaysales/vijaysales_listing.html', 'r') as f:
        return f.read()


@pytest.fixture
def vijaysales_offers_html():
    """Load the Vijay Sales offers HTML fixture"""
    with open('tests/fixtures/vijaysales/vijaysales_offers.html', 'r') as f:
        return f.read()


def test_parse_listings(vijaysales_adapter, vijaysales_listing_html):
    """Test that we can parse listings from HTML"""
    listings = vijaysales_adapter.parse_listing(vijaysales_listing_html)
    
    # Should parse multiple products
    assert len(listings) > 0
    
    # Check that all listings are RawListing instances
    for listing in listings:
        assert isinstance(listing, RawListing)


def test_product_count(vijaysales_adapter, vijaysales_listing_html):
    """Test that we get the expected number of products"""
    listings = vijaysales_adapter.parse_listing(vijaysales_listing_html)
    
    # Based on the fixture, there should be 27 unique products
    assert len(listings) == 27


def test_product_name_parsing(vijaysales_adapter, vijaysales_listing_html):
    """Test that product names are parsed correctly"""
    listings = vijaysales_adapter.parse_listing(vijaysales_listing_html)
    
    # Find iPhone Air to test (this is in the fixture)
    iphone_air = None
    for listing in listings:
        if "iPhone Air" in listing.product_name:
            iphone_air = listing
            break
    
    assert iphone_air is not None
    assert "iPhone Air" in iphone_air.model
    assert "256 GB" in iphone_air.storage
    assert iphone_air.colour is not None


def test_sku_extraction(vijaysales_adapter, vijaysales_listing_html):
    """Test that SKUs are extracted from URLs"""
    listings = vijaysales_adapter.parse_listing(vijaysales_listing_html)
    
    # Check that all listings have SKUs
    for listing in listings:
        assert listing.sku is not None
        assert listing.sku.isdigit()  # Should be numeric


def test_price_format_parsing(vijaysales_adapter, vijaysales_listing_html):
    """Test that Vijay Sales price format (₹ 119900) is parsed correctly"""
    listings = vijaysales_adapter.parse_listing(vijaysales_listing_html)
    
    for listing in listings:
        assert listing.selling_price is not None
        assert isinstance(listing.selling_price, Decimal)


def test_mrp_always_shown(vijaysales_adapter, vijaysales_listing_html):
    """Test that MRP is always shown on Vijay Sales"""
    listings = vijaysales_adapter.parse_listing(vijaysales_listing_html)
    
    # All items should have MRP
    for listing in listings:
        assert listing.mrp is not None


def test_discount_calculation(vijaysales_adapter, vijaysales_listing_html):
    """Test that discount is calculated correctly (mrp - selling_price)"""
    listings = vijaysales_adapter.parse_listing(vijaysales_listing_html)
    
    for listing in listings:
        if listing.mrp and listing.selling_price:
            expected_discount = listing.mrp - listing.selling_price
            assert listing.discount == expected_discount


def test_zero_discount_handling(vijaysales_adapter, vijaysales_listing_html):
    """Test that items with no discount have discount = 0, not None"""
    listings = vijaysales_adapter.parse_listing(vijaysales_listing_html)
    
    # Find item with no discount (mrp == selling_price)
    no_discount_item = None
    for listing in listings:
        if listing.mrp == listing.selling_price:
            no_discount_item = listing
            break
    
    if no_discount_item:
        assert no_discount_item.discount == Decimal('0')
        assert no_discount_item.discount is not None


def test_stock_status_parsing(vijaysales_adapter, vijaysales_listing_html):
    """Test that stock status is parsed from card"""
    listings = vijaysales_adapter.parse_listing(vijaysales_listing_html)
    
    # Check that availability is parsed
    for listing in listings:
        assert listing.availability is not None
        # Should be either "In Stock" or "Out of Stock"
        assert listing.availability in ["In Stock", "Out of Stock"]


def test_source_field(vijaysales_adapter, vijaysales_listing_html):
    """Test that source field is set correctly"""
    listings = vijaysales_adapter.parse_listing(vijaysales_listing_html)
    
    for listing in listings:
        assert listing.source == "vijaysales"


def test_currency_field(vijaysales_adapter, vijaysales_listing_html):
    """Test that currency is set to INR"""
    listings = vijaysales_adapter.parse_listing(vijaysales_listing_html)
    
    for listing in listings:
        assert listing.currency == "INR"


def test_offers_parsing(vijaysales_adapter, vijaysales_offers_html):
    """Test that offers are parsed from HTML"""
    offers = vijaysales_adapter.parse_offers(vijaysales_offers_html)
    
    # Should parse at least some offers
    assert len(offers) > 0
    
    # Check that all offers are RawOffer instances
    for offer in offers:
        assert isinstance(offer, RawOffer)


def test_bank_extraction(vijaysales_adapter, vijaysales_offers_html):
    """Test that bank names are extracted from offers"""
    offers = vijaysales_adapter.parse_offers(vijaysales_offers_html)
    
    # At least some offers should have bank information
    offers_with_banks = [o for o in offers if o.bank is not None]
    assert len(offers_with_banks) > 0


def test_filter_by_query(vijaysales_adapter, vijaysales_listing_html):
    """Test filtering listings by query"""
    listings = vijaysales_adapter.parse_listing(vijaysales_listing_html, query="iPhone 17 Pro")
    
    # Should only contain iPhone 17 Pro models
    for listing in listings:
        assert "iPhone 17 Pro" in listing.product_name


def test_adapter_name(vijaysales_adapter):
    """Test that adapter name is set correctly"""
    assert vijaysales_adapter.name == "vijaysales"