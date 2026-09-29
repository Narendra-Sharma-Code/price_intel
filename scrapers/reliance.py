import re
import logging
from typing import List, Optional
from decimal import Decimal

from scrapers.base import BaseAdapter, http_client
from scrapers.types import RawListing, RawOffer
from scrapers.normalize import parse_inr

logger = logging.getLogger(__name__)


class RelianceDigitalAdapter(BaseAdapter):
    name = "reliance"
    
    BASE_URL = "https://www.reliancedigital.in"
    CATEGORY_URL = f"{BASE_URL}/collection/ios-phones"
    OFFERS_URL = f"{BASE_URL}/c/all-offers"
    
    def search(self, query: str, storage: Optional[str] = None, colour: Optional[str] = None) -> List[RawListing]:
        """
        Public method to search Reliance Digital with robots.txt check and HTTP fetch.
        For testing/debugging with saved HTML, use parse_listing() directly.
        """
        try:
            # Robots.txt check is handled by http_client.get()
            html = http_client.get(self.CATEGORY_URL)
            if not html:
                logger.error("Failed to fetch Reliance Digital category page")
                return []
            
            return self.parse_listing(html, query, storage, colour)
            
        except Exception as e:
            logger.error(f"Error searching Reliance Digital: {e}")
            return []
    
    def parse_listing(self, html: str, query: Optional[str] = None, storage: Optional[str] = None, colour: Optional[str] = None) -> List[RawListing]:
        """
        Parse Reliance Digital listing HTML and return RawListing objects.
        This method can be called directly with saved HTML for testing/debugging.
        """
        try:
            listings = self._parse_product_cards(html)
            
            # Filter by query/storage/colour if provided
            if query or storage or colour:
                listings = self._filter_listings(listings, query, storage, colour)
            
            logger.info(f"Parsed {len(listings)} listings from Reliance Digital HTML")
            return listings
            
        except Exception as e:
            logger.error(f"Error parsing Reliance Digital listing HTML: {e}")
            return []
    
    def _parse_product_cards(self, html: str) -> List[RawListing]:
        listings = []
        
        # Find all product cards
        card_pattern = r'<div class="product-card"[^>]*>.*?</a>\s*</div>'
        card_matches = re.findall(card_pattern, html, re.DOTALL)
        
        for card_html in card_matches:
            try:
                listing = self._parse_product_card(card_html)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.warning(f"Error parsing product card: {e}")
                continue
        
        return listings
    
    def _parse_product_card(self, card_html: str) -> Optional[RawListing]:
        try:
            # Extract product URL
            url_match = re.search(r'href="([^"]+)"', card_html)
            if not url_match:
                return None
            
            product_url = url_match.group(1)
            # Convert relative URLs to absolute
            if product_url.startswith('/'):
                product_url = f"{self.BASE_URL}{product_url}"
            elif not product_url.startswith('http'):
                product_url = f"{self.BASE_URL}/{product_url}"
            
            # Extract SKU from URL pattern: /product/{slug}-{modelCode}-{numericId}
            sku = self._extract_sku_from_url(product_url)
            if not sku:
                return None
            
            # Extract product name
            name_match = re.search(r'<div class="product-name">([^<]+)</div>', card_html)
            if not name_match:
                return None
            
            product_name = name_match.group(1).strip()
            
            # Parse product name: "Apple iPhone 18 Pro 2 TB, Glacier"
            model, storage, colour = self._parse_product_name(product_name)
            
            # Extract selling price (no MRP on Reliance)
            selling_price = self._extract_price(card_html)
            
            return RawListing(
                variant_id=sku,  # Use SKU as variant_id
                source=self.name,
                product_name=product_name,
                brand="Apple",  # Hardcoded for iOS phones category
                model=model,
                storage=storage,
                colour=colour,
                sku=sku,
                product_url=product_url,
                currency="INR",
                selling_price=selling_price,
                mrp=None,  # No MRP on listing page
                discount=None,  # No discount on listing page
                availability="In Stock",  # No availability marker, default to In Stock
                rating=None,
                review_count=None
            )
            
        except Exception as e:
            logger.warning(f"Error parsing product card: {e}")
            return None
    
    def _extract_sku_from_url(self, url: str) -> Optional[str]:
        """Extract numeric ID from URL pattern: /product/{slug}-{modelCode}-{numericId}"""
        # Pattern: /product/{slug}-{modelCode}-{numericId}
        match = re.search(r'/product/.*-(\d+)$', url)
        if match:
            return match.group(1)
        return None
    
    def _parse_product_name(self, name: str) -> tuple:
        """
        Parse product name format: "Apple iPhone 18 Pro 2 TB, Glacier"
        Returns: (model, storage, colour)
        """
        model = None
        storage = None
        colour = None
        
        try:
            # Strip "Apple " prefix (with space)
            if name.startswith("Apple "):
                name = name[6:]  # Remove "Apple " (6 characters)
            
            # Split on last comma for colour
            if "," in name:
                parts = name.rsplit(",", 1)
                model_storage = parts[0].strip()
                colour = parts[1].strip()
                
                # Extract storage using regex (handles "2 TB", "256 GB", etc.)
                storage_match = re.search(r'(\d+\s*(?:TB|GB))', model_storage, re.IGNORECASE)
                if storage_match:
                    storage = storage_match.group(1)
                    # Remove storage from model string
                    model = model_storage.replace(storage, "").strip()
                else:
                    model = model_storage
            else:
                model = name
                
        except Exception as e:
            logger.warning(f"Error parsing product name '{name}': {e}")
        
        return model, storage, colour
    
    def _extract_price(self, card_html: str) -> Optional[Decimal]:
        """Extract selling price from card HTML"""
        price_match = re.search(r'<div class="price">\s*([^<]+)\s*</div>', card_html)
        if price_match:
            return parse_inr(price_match.group(1).strip())
        return None
    
    def _filter_listings(self, listings: List[RawListing], query: Optional[str], 
                        storage: Optional[str], colour: Optional[str]) -> List[RawListing]:
        filtered = []
        
        for listing in listings:
            match = True
            
            if query:
                query_lower = query.lower()
                if query_lower not in listing.product_name.lower() and \
                   query_lower not in (listing.model or "").lower():
                    match = False
            
            if storage and match:
                if storage.lower() not in (listing.storage or "").lower():
                    match = False
            
            if colour and match:
                if colour.lower() not in (listing.colour or "").lower():
                    match = False
            
            if match:
                filtered.append(listing)
        
        return filtered
    
    def get_offers(self) -> List[RawOffer]:
        """
        Public method to get Reliance Digital offers with robots.txt check and HTTP fetch.
        For testing/debugging with saved HTML, use parse_offers() directly.
        """
        try:
            # Robots.txt check is handled by http_client.get()
            html = http_client.get(self.OFFERS_URL)
            if not html:
                logger.error("Failed to fetch Reliance Digital offers page")
                return []
            
            return self.parse_offers(html)
            
        except Exception as e:
            logger.error(f"Error getting Reliance Digital offers: {e}")
            return []
    
    def parse_offers(self, html: str) -> List[RawOffer]:
        """
        Parse Reliance Digital offers HTML and return RawOffer objects.
        This method can be called directly with saved HTML for testing/debugging.
        """
        try:
            offers = self._parse_offers_from_html(html)
            logger.info(f"Parsed {len(offers)} offers from Reliance Digital HTML")
            return offers
            
        except Exception as e:
            logger.error(f"Error parsing Reliance Digital offers HTML: {e}")
            return []
    
    def _parse_offers_from_html(self, html: str) -> List[RawOffer]:
        offers = []
        
        # Parse offer items from HTML - more flexible pattern
        offer_pattern = r'<div class="offer-item">\s*<div class="offer-title">([^<]+)</div>\s*<div class="offer-description">([^<]+)</div>'
        offer_matches = re.findall(offer_pattern, html, re.DOTALL)
        
        for title, description in offer_matches:
            try:
                title = title.strip()
                description = description.strip()
                
                # Combine title and description for offer_text
                offer_text = f"{title} - {description}" if title and description else (title or description)
                
                # Extract bank name from description if present (case-insensitive)
                bank_match = re.search(r'(HDFC|ICICI|AXIS|SBI|KOTAK|IDFC)', description, re.IGNORECASE)
                bank = bank_match.group(1).upper() if bank_match else None
                
                # Extract discount percentage if present
                discount_match = re.search(r'(\d+)%', title)
                offer_discount = None
                if discount_match:
                    offer_discount = Decimal(discount_match.group(1))
                
                offers.append(RawOffer(
                    offer_text=offer_text,
                    bank=bank,
                    offer_discount=offer_discount,
                    offer_type="bank_offer" if bank else "general_offer"
                ))
                
            except Exception as e:
                logger.warning(f"Error parsing offer item: {e}")
                continue
        
        return offers