import re
import json
import logging
from typing import List, Optional
from decimal import Decimal
from urllib.parse import urlparse

from scrapers.base import BaseAdapter, http_client
from scrapers.types import RawListing, RawOffer
from scrapers.normalize import parse_inr

logger = logging.getLogger(__name__)


class CromaAdapter(BaseAdapter):
    name = "croma"
    
    BASE_URL = "https://www.croma.com"
    CATEGORY_URL = f"{BASE_URL}/phones-wearables/mobile-phones/apple-iphones/c/97"
    OFFERS_URL = f"{BASE_URL}/lp-bank-offers"
    
    def search(self, query: str, storage: Optional[str] = None, colour: Optional[str] = None) -> List[RawListing]:
        """
        Public method to search Croma with robots.txt check and HTTP fetch.
        For testing/debugging with saved HTML, use parse_listing() directly.
        """
        try:
            # Robots.txt check is handled by http_client.get()
            html = http_client.get(self.CATEGORY_URL)
            if not html:
                logger.error("Failed to fetch Croma category page")
                return []
            
            return self.parse_listing(html, query, storage, colour)
            
        except Exception as e:
            logger.error(f"Error searching Croma: {e}")
            return []
    
    def parse_listing(self, html: str, query: Optional[str] = None, storage: Optional[str] = None, colour: Optional[str] = None) -> List[RawListing]:
        """
        Parse Croma listing HTML and return RawListing objects.
        This method can be called directly with saved HTML for testing/debugging.
        """
        try:
            listings = self._parse_listings_from_jsonld(html)
            
            # Filter by query/storage/colour if provided
            if query or storage or colour:
                listings = self._filter_listings(listings, query, storage, colour)
            
            logger.info(f"Parsed {len(listings)} listings from Croma HTML")
            return listings
            
        except Exception as e:
            logger.error(f"Error parsing Croma listing HTML: {e}")
            return []
    
    def _parse_listings_from_jsonld(self, html: str) -> List[RawListing]:
        listings = []
        
        # Extract JSON-LD from HTML
        json_ld_pattern = r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>'
        matches = re.findall(json_ld_pattern, html, re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match)
                
                # Look for OfferCatalog type
                if data.get("@type") == "OfferCatalog":
                    items = data.get("itemListElement", [])
                    for item in items:
                        product = item.get("item", {})
                        if product.get("@type") == "Product":
                            listing = self._parse_product_from_jsonld(product, html)
                            if listing:
                                listings.append(listing)
                                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON-LD: {e}")
                continue
        
        return listings
    
    def _parse_product_from_jsonld(self, product: dict, html: str) -> Optional[RawListing]:
        try:
            name = product.get("name", "")
            url = product.get("url", "")
            sku = product.get("sku", "")
            brand = product.get("brand", "")
            
            # Extract variant_id from URL pattern /{slug}/p/{id}
            variant_id = self._extract_variant_id_from_url(url)
            if not variant_id:
                variant_id = sku  # Fallback to SKU
            
            # Parse product name: "Apple iPhone 17 Pro (256GB, Silver)"
            model, storage, colour = self._parse_product_name(name)
            
            # Extract price data from HTML DOM by matching product URL/SKU
            selling_price, mrp, discount = self._extract_price_from_html(html, variant_id, url)
            
            # Extract offer badges from HTML
            offer_badges = self._extract_offer_badges_from_html(html, variant_id)
            
            return RawListing(
                variant_id=variant_id,
                source=self.name,
                product_name=name,
                brand=brand,
                model=model,
                storage=storage,
                colour=colour,
                sku=sku,
                product_url=url,
                currency="INR",
                selling_price=selling_price,
                mrp=mrp,
                discount=discount,
                # Availability: no explicit "Out of Stock" marker on listing cards
                # Default to "In Stock" - documented assumption, not scraped fact
                availability="In Stock",
                rating=None,
                review_count=None,
                offers=offer_badges
            )
            
        except Exception as e:
            logger.warning(f"Error parsing product from JSON-LD: {e}")
            return None
    
    def _extract_variant_id_from_url(self, url: str) -> Optional[str]:
        """Extract numeric ID from URL pattern /{slug}/p/{id}"""
        if not url:
            return None
        
        # Pattern: /{slug}/p/{numeric_id}
        match = re.search(r'/p/(\d+)', url)
        if match:
            return match.group(1)
        
        return None
    
    def _parse_product_name(self, name: str) -> tuple:
        """
        Parse product name format: "Apple iPhone 17 Pro (256GB, Silver)"
        Returns: (model, storage, colour)
        """
        model = None
        storage = None
        colour = None
        
        try:
            # Remove "Apple " prefix (with space) to normalize with other sources
            if name.startswith("Apple "):
                name = name[6:]  # Remove "Apple " (6 characters)
            
            # Split on first "("
            if "(" in name:
                parts = name.split("(", 1)
                model = parts[0].strip()
                
                # Parse inner content: "256GB, Silver)"
                inner = parts[1].rstrip(")")
                if "," in inner:
                    storage_colour = inner.split(",", 1)
                    storage = storage_colour[0].strip()
                    colour = storage_colour[1].strip()
                else:
                    # Only one attribute
                    storage = inner.strip()
            else:
                model = name
                
        except Exception as e:
            logger.warning(f"Error parsing product name '{name}': {e}")
        
        return model, storage, colour
    
    def _extract_price_from_html(self, html: str, variant_id: str, url: str) -> tuple:
        """
        Extract price data from HTML DOM by matching product variant_id/URL.
        Returns: (selling_price, mrp, discount)
        """
        try:
            # Find the product card by variant_id (id attribute on the product div)
            card_pattern = r'<li class="product-item"><div[^>]*id="' + re.escape(variant_id) + r'"[^>]*>.*?</li>'
            card_match = re.search(card_pattern, html, re.DOTALL)
            
            if not card_match:
                # Try matching by URL if ID match fails
                url_slug = url.split('/')[-1]  # Get last part of URL
                url_pattern = r'href="/' + re.escape(url_slug) + r'"'
                url_match = re.search(url_pattern, html)
                if url_match:
                    # Get context around URL to find the card
                    start = max(0, url_match.start() - 2000)
                    end = min(len(html), url_match.end() + 2000)
                    card_html = html[start:end]
                else:
                    logger.warning(f"Could not find product card for variant_id {variant_id}")
                    return None, None, None
            else:
                card_html = card_match.group(0)
            
            # Extract selling price - find the first ₹ amount in the card
            # This will be the selling price (MRP appears only in discount-container)
            selling_price_pattern = r'₹\s*([\d,]+)'
            selling_price_matches = re.findall(selling_price_pattern, card_html)
            
            selling_price = None
            if selling_price_matches:
                # Take the first match as selling price
                selling_price = parse_inr(selling_price_matches[0])
            else:
                logger.warning(f"Could not find selling price for variant_id {variant_id}")
            
            # Extract MRP - second ₹ amount in discount-container
            mrp_pattern = r'data-testid="old-price"[^>]*>(₹[\d,]+)'
            mrp_match = re.search(mrp_pattern, card_html)
            
            mrp = None
            if mrp_match:
                mrp = parse_inr(mrp_match.group(1))
            
            # Calculate discount if both prices are present
            discount = None
            if selling_price and mrp:
                discount = mrp - selling_price
                
                # Cross-check with "(Save ₹X)" text if present
                save_pattern = r'\(Save\s*₹\s*([\d,]+)\)'
                save_match = re.search(save_pattern, card_html)
                if save_match:
                    save_str = save_match.group(1).replace(',', '')
                    save_amount = Decimal(save_str)
                    if abs(discount - save_amount) > Decimal('1.00'):  # Allow small rounding differences
                        logger.warning(f"Discount mismatch for variant_id {variant_id}: calculated {discount}, save text {save_amount}")
            
            return selling_price, mrp, discount
            
        except Exception as e:
            logger.warning(f"Error extracting price for variant_id {variant_id}: {e}")
            return None, None, None
    
    def _extract_offer_badges_from_html(self, html: str, variant_id: str) -> list[str]:
        """
        Extract offer badges from HTML DOM.
        Returns list of deduplicated offer strings.
        """
        try:
            # Find the product card by variant_id
            card_pattern = r'<li class="product-item"><div[^>]*id="' + re.escape(variant_id) + r'"[^>]*>.*?</li>'
            card_match = re.search(card_pattern, html, re.DOTALL)
            
            if not card_match:
                return []
            
            card_html = card_match.group(0)
            
            # Extract offer badges from tagsForPlp spans
            offer_pattern = r'<span class="tagsForPlp">([^<]+)</span>'
            offer_matches = re.findall(offer_pattern, card_html)
            
            # Clean and deduplicate offers
            offers = []
            seen = set()
            for offer in offer_matches:
                cleaned_offer = offer.strip()
                if cleaned_offer and cleaned_offer not in seen:
                    seen.add(cleaned_offer)
                    offers.append(cleaned_offer)
            
            return offers
            
        except Exception as e:
            logger.warning(f"Error extracting offers for variant_id {variant_id}: {e}")
            return []
    
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
        Public method to get Croma offers with robots.txt check and HTTP fetch.
        For testing/debugging with saved HTML, use parse_offers() directly.
        """
        try:
            # Robots.txt check is handled by http_client.get()
            html = http_client.get(self.OFFERS_URL)
            if not html:
                logger.error("Failed to fetch Croma offers page")
                return []
            
            return self.parse_offers(html)
            
        except Exception as e:
            logger.error(f"Error getting Croma offers: {e}")
            return []
    
    def parse_offers(self, html: str) -> List[RawOffer]:
        """
        Parse Croma offers HTML and return RawOffer objects.
        This method can be called directly with saved HTML for testing/debugging.
        """
        try:
            offers = self._parse_offers_from_html(html)
            logger.info(f"Parsed {len(offers)} offers from Croma HTML")
            return offers
            
        except Exception as e:
            logger.error(f"Error parsing Croma offers HTML: {e}")
            return []
    
    def _parse_offers_from_html(self, html: str) -> List[RawOffer]:
        offers = []
        
        # Parse offers from the HTML - look for offer-related text
        # Based on the fixture, offers are in tables and lists
        # We'll extract offer text and try to identify bank/discount info
        
        # Look for bank-related content
        bank_pattern = r'(?:ICICI|HDFC|SBI|AXIS|KOTAK|IDFC|YES|HSBC|OneCard)'
        
        # Extract offer text from table content
        # The fixture shows offers in table format with Brand, Banks, Duration
        table_pattern = r'<table[^>]*>.*?</table>'
        table_matches = re.findall(table_pattern, html, re.DOTALL | re.IGNORECASE)
        
        for table in table_matches:
            # Extract text content from table
            text_content = re.sub(r'<[^>]+>', ' ', table)
            text_content = ' '.join(text_content.split())
            
            if text_content.strip():
                # Skip multi-brand comparison tables (contain multiple unrelated brands)
                # These are noise - we only want Apple-specific offers
                unrelated_brands = ['JBL', 'Samsung', 'Google Pixel', 'LG', 'Vivo', 'Nothing', 
                                   'OnePlus', 'Oppo', 'Whirlpool', 'Panasonic', 'TCL', 'Sony', 
                                   'Realme', 'Xiaomi', 'Hitachi']
                has_unrelated_brands = any(brand.lower() in text_content.lower() 
                                          for brand in unrelated_brands)
                
                # Also skip if the text contains "Brand Banks Duration" pattern (comparison table header)
                if 'Brand Banks Duration' in text_content or has_unrelated_brands:
                    logger.info(f"Skipping multi-brand comparison table: {text_content[:100]}...")
                    continue
                
                # Try to identify bank names
                banks = re.findall(bank_pattern, text_content, re.IGNORECASE)
                bank = banks[0] if banks else None
                
                offers.append(RawOffer(
                    offer_text=text_content.strip(),
                    bank=bank,
                    offer_type="bank_offer" if bank else None
                ))
        
        return offers