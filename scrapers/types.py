from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from datetime import datetime, timezone


@dataclass
class RawListing:
    variant_id: str
    source: str
    product_name: str
    brand: str
    model: Optional[str] = None
    storage: Optional[str] = None
    colour: Optional[str] = None
    sku: Optional[str] = None
    product_url: Optional[str] = None
    image_url: Optional[str] = None
    currency: str = "INR"
    mrp: Optional[Decimal] = None
    selling_price: Optional[Decimal] = None
    discount: Optional[Decimal] = None
    availability: str = "In Stock"
    seller: Optional[str] = None
    rating: Optional[Decimal] = None
    review_count: Optional[int] = None
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    offers: list = field(default_factory=lambda: [])


@dataclass
class RawOffer:
    offer_text: str
    offer_type: Optional[str] = None
    bank: Optional[str] = None
    offer_discount: Optional[Decimal] = None
    min_purchase: Optional[Decimal] = None
    max_cap: Optional[Decimal] = None
    emi_available: bool = False
    emi_tenure: Optional[int] = None
    emi_rate: Optional[Decimal] = None
    validity: Optional[str] = None
