import pytest
from decimal import Decimal
from datetime import datetime, timezone

from services.offers import parse_offer_text, compute_effective_price
from scrapers.types import RawListing, RawOffer


def test_parse_offer_text_with_bank():
    """Test parsing offer text with bank name"""
    result = parse_offer_text("Get 10% off on HDFC Credit Cards")
    
    assert result.bank == "HDFC"
    assert result.discount == Decimal("10")
    assert result.has_emi is False
    assert result.raw_text == "Get 10% off on HDFC Credit Cards"


def test_parse_offer_text_with_amount():
    """Test parsing offer text with discount amount"""
    result = parse_offer_text("Bank Discount of Rs. 4000")
    
    assert result.bank is None  # Pattern doesn't match bank name
    assert result.discount == Decimal("4000")
    assert result.has_emi is False


def test_parse_offer_text_with_emi():
    """Test parsing offer text with EMI mention"""
    result = parse_offer_text("No Cost EMI available")
    
    assert result.bank is None
    assert result.discount is None
    assert result.has_emi is True


def test_parse_offer_text_empty():
    """Test parsing empty offer text"""
    result = parse_offer_text("")
    
    assert result.bank is None
    assert result.discount is None
    assert result.has_emi is False
    assert result.raw_text == ""


def test_compute_effective_price_no_restriction():
    """Test that offer with no bank restriction gets applied"""
    listing = RawListing(
        variant_id="1",
        source="croma",
        product_name="Test Product",
        brand="Test",
        model="Test",
        storage="256GB",
        colour="Silver",
        sku="123",
        product_url="http://example.com",
        currency="INR",
        selling_price=Decimal("10000"),
        mrp=Decimal("12000"),
        discount=Decimal("2000"),
        availability="In Stock",
        rating=None,
        review_count=None,
        scraped_at=datetime.now(timezone.utc)
    )
    
    offer = RawOffer(
        offer_text="Flat Rs. 500 off",
        offer_type="discount",
        bank=None,  # No bank restriction
        offer_discount=Decimal("500"),
        min_purchase=None,
        max_cap=None,
        emi_available=False,
        emi_tenure=None,
        emi_rate=None,
        validity=None
    )
    
    result = compute_effective_price(listing, [offer])
    
    assert result.effective_price == Decimal("9500")
    assert result.applied_offer == offer
    assert len(result.conditional_offers) == 0


def test_compute_effective_price_with_bank_match():
    """Test that offer with bank restriction gets applied when bank matches"""
    listing = RawListing(
        variant_id="1",
        source="croma",
        product_name="Test Product",
        brand="Test",
        model="Test",
        storage="256GB",
        colour="Silver",
        sku="123",
        product_url="http://example.com",
        currency="INR",
        selling_price=Decimal("10000"),
        mrp=Decimal("12000"),
        discount=Decimal("2000"),
        availability="In Stock",
        rating=None,
        review_count=None,
        scraped_at=datetime.now(timezone.utc)
    )
    
    offer = RawOffer(
        offer_text="10% off on HDFC cards",
        offer_type="discount",
        bank="HDFC",
        offer_discount=None,
        min_purchase=None,
        max_cap=None,
        emi_available=False,
        emi_tenure=None,
        emi_rate=None,
        validity=None
    )
    
    result = compute_effective_price(listing, [offer], selected_bank="HDFC")
    
    # Should apply 10% discount
    assert result.effective_price == Decimal("9000")
    assert result.applied_offer == offer
    assert len(result.conditional_offers) == 0


def test_compute_effective_price_with_bank_mismatch():
    """Test that offer with bank restriction is marked conditional when bank doesn't match"""
    listing = RawListing(
        variant_id="1",
        source="croma",
        product_name="Test Product",
        brand="Test",
        model="Test",
        storage="256GB",
        colour="Silver",
        sku="123",
        product_url="http://example.com",
        currency="INR",
        selling_price=Decimal("10000"),
        mrp=Decimal("12000"),
        discount=Decimal("2000"),
        availability="In Stock",
        rating=None,
        review_count=None,
        scraped_at=datetime.now(timezone.utc)
    )
    
    offer = RawOffer(
        offer_text="10% off on HDFC cards",
        offer_type="discount",
        bank="HDFC",
        offer_discount=None,
        min_purchase=None,
        max_cap=None,
        emi_available=False,
        emi_tenure=None,
        emi_rate=None,
        validity=None
    )
    
    result = compute_effective_price(listing, [offer], selected_bank="ICICI")
    
    # Should not apply, marked as conditional
    assert result.effective_price == Decimal("10000")
    assert result.applied_offer is None
    assert len(result.conditional_offers) == 1
    assert result.conditional_offers[0] == offer


def test_compute_effective_price_no_selected_bank():
    """Test that offer with bank restriction is marked conditional when no bank selected"""
    listing = RawListing(
        variant_id="1",
        source="croma",
        product_name="Test Product",
        brand="Test",
        model="Test",
        storage="256GB",
        colour="Silver",
        sku="123",
        product_url="http://example.com",
        currency="INR",
        selling_price=Decimal("10000"),
        mrp=Decimal("12000"),
        discount=Decimal("2000"),
        availability="In Stock",
        rating=None,
        review_count=None,
        scraped_at=datetime.now(timezone.utc)
    )
    
    offer = RawOffer(
        offer_text="10% off on HDFC cards",
        offer_type="discount",
        bank="HDFC",
        offer_discount=None,
        min_purchase=None,
        max_cap=None,
        emi_available=False,
        emi_tenure=None,
        emi_rate=None,
        validity=None
    )
    
    result = compute_effective_price(listing, [offer], selected_bank=None)
    
    # Should not apply, marked as conditional
    assert result.effective_price == Decimal("10000")
    assert result.applied_offer is None
    assert len(result.conditional_offers) == 1
