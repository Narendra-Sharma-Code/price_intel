import re
import logging
from typing import List, Optional
from decimal import Decimal

from scrapers.base import BaseAdapter, http_client
from scrapers.types import RawListing, RawOffer
from scrapers.normalize import parse_inr

logger = logging.getLogger(__name__)


class VijaySalesAdapter(BaseAdapter):
    name = "vijaysales"
    
    BASE_URL = "https://www.vijaysales.com"
    CATEGORY_URL = f"{BASE_URL}/c/iphones?cityId=1"
    OFFERS_URL = f"{BASE_URL}/event-pages/bank-offers"
    
    def search(self, query: str, storage: Optional[str] = None, colour: Optional[str] = None) -> List[RawListing]:
        """
        Public method to search Vijay Sales with robots.txt check and HTTP fetch.
        For testing/debugging with saved HTML, use parse_listing() directly.
        """
        try:
            # Robots.txt check is handled by http_client.get()
            html = http_client.get(self.CATEGORY_URL)
            if not html:
                logger.error("Failed to fetch Vijay Sales category page")
                return []
            
            return self.parse_listing(html, query, storage, colour)
            
        except Exception as e:
            logger.error(f"Error searching Vijay Sales: {e}")
            return []
    
    def parse_listing(self, html: str, query: Optional[str] = None, storage: Optional[str] = None, colour: Optional[str] = None) -> List[RawListing]:
        """
        Parse Vijay Sales listing HTML and return RawListing objects.
        This method can be called directly with saved HTML for testing/debugging.
        """
        try:
            listings = self._parse_product_cards(html)
            
            # Filter by query/storage/colour if provided
            if query or storage or colour:
                listings = self._filter_listings(listings, query, storage, colour)
            
            logger.info(f"Parsed {len(listings)} listings from Vijay Sales HTML")
            return listings
            
        except Exception as e:
            logger.error(f"Error parsing Vijay Sales listing HTML: {e}")
            return []
    
    def _parse_product_cards(self, html: str) -> List[RawListing]:
        listings = []
        
        # More robust approach: find all product URLs first, then parse each one's context
        # This ensures we catch products from all sections (main grid, recommendations, etc.)
        # Match both href and data-href attributes
        url_pattern = r'(?:href|data-href)="(/p/P\d+/\d+/[a-z0-9-]+)"'
        url_matches = re.findall(url_pattern, html)
        
        logger.info(f"Found {len(url_matches)} product URL matches, {len(set(url_matches))} unique")
        
        for url in url_matches:
            try:
                # Find the position of this URL in the HTML (try both href and data-href)
                url_pos = html.find(f'href="{url}"')
                if url_pos == -1:
                    url_pos = html.find(f'data-href="{url}"')
                if url_pos == -1:
                    continue
                
                # Get context around the URL to find product data
                # Increase context window significantly to capture the entire card structure
                context_start = max(0, url_pos - 5000)
                context_end = min(len(html), url_pos + len(url) + 10000)
                context = html[context_start:context_end]
                
                listing = self._parse_product_from_context(context, url)
                if listing:
                    listings.append(listing)
                    
            except Exception as e:
                logger.warning(f"Error parsing product for URL {url}: {e}")
                continue
        
        # Deduplicate by product URL
        seen_urls = set()
        unique_listings = []
        for listing in listings:
            if listing.product_url not in seen_urls:
                seen_urls.add(listing.product_url)
                unique_listings.append(listing)
            else:
                logger.debug(f"Deduplicated product URL: {listing.product_url}")
        
        logger.info(f"Parsed {len(unique_listings)} unique listings from {len(listings)} total")
        return unique_listings
    
    def _parse_product_from_context(self, context: str, url: str) -> Optional[RawListing]:
        """Parse product data from HTML context around a product URL"""
        try:
            # Extract SKU from URL pattern: /p/{parentId}/{variantId}/{slug}
            sku = self._extract_sku_from_url(url)
            if not sku:
                logger.warning(f"Could not extract SKU from URL: {url}")
                return None
            
            # Build full URL if needed
            product_url = url if url.startswith('http') else f"{self.BASE_URL}{url}"
            
            # Extract product name from context
            # Try specific selectors in order of preference
            name_match = re.search(r'<div class="product-name">([^<]+)</div>', context)
            if not name_match:
                name_match = re.search(r'<div class="product-title">([^<]+)</div>', context)
            if not name_match:
                name_match = re.search(r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</h3>', context)
            if not name_match:
                name_match = re.search(r'<div[^>]*class="[^"]*name[^"]*"[^>]*>([^<]+)</div>', context)
            if not name_match:
                # Try to find the product name in a reasonable way - look for text that looks like a product name
                # It should contain "iPhone" or similar brand names
                potential_names = re.findall(r'>([^<]{10,100})<', context)
                for pn in potential_names:
                    if 'iPhone' in pn or 'Apple' in pn:
                        name_match = re.search(r'>([^<]+)<', f'>{pn}<')
                        if name_match:
                            break
            
            if not name_match:
                logger.warning(f"Could not extract product name from context for URL {url}")
                return None
            
            product_name = name_match.group(1).strip()
            
            # Parse product name: "Apple iPhone 17 Pro (256 GB Storage, Silver)"
            model, storage, colour = self._parse_product_name(product_name)
            
            # Extract prices from context
            selling_price, mrp = self._extract_prices_from_context(context)
            
            # Calculate discount (Vijay Sales always shows MRP)
            discount = None
            if selling_price and mrp:
                discount = mrp - selling_price
                if discount == 0:
                    discount = Decimal('0')  # Explicit zero when no discount
            
            # Extract stock status from context
            availability = self._extract_availability_from_context(context)
            
            logger.debug(f"Parsed product: {product_name}, SKU: {sku}, Price: {selling_price}")
            
            return RawListing(
                variant_id=sku,  # Use SKU as variant_id
                source=self.name,
                product_name=product_name,
                brand="Apple",  # Hardcoded for iPhones category
                model=model,
                storage=storage,
                colour=colour,
                sku=sku,
                product_url=product_url,
                currency="INR",
                selling_price=selling_price,
                mrp=mrp,
                discount=discount,
                availability=availability,
                rating=None,
                review_count=None
            )
            
        except Exception as e:
            logger.warning(f"Error parsing product from context: {e}")
            return None
    
    def _extract_sku_from_url(self, url: str) -> Optional[str]:
        """Extract variantId from URL pattern: /p/{parentId}/{variantId}/{slug}"""
        # Pattern: /p/P{parentId}/{variantId}/{slug}
        # Example: /p/P245221/245221/apple-iphone-air-256-gb-storage-space-black
        match = re.search(r'/p/P\d+/(\d+)/', url)
        if match:
            return match.group(1)
        return None
    
    def _parse_product_name(self, name: str) -> tuple:
        """
        Parse product name format: "Apple iPhone 17 Pro (256 GB Storage, Silver)"
        Returns: (model, storage, colour)
        """
        model = None
        storage = None
        colour = None
        
        try:
            # Remove "Apple " prefix (with space)
            if name.startswith("Apple "):
                name = name[6:]  # Remove "Apple " (6 characters)
            
            # Split on first "("
            if "(" in name:
                parts = name.split("(", 1)
                model = parts[0].strip()
                
                # Parse inner content: "256 GB Storage, Silver)"
                inner = parts[1].rstrip(")")
                if "," in inner:
                    storage_colour = inner.split(",", 1)
                    storage = storage_colour[0].strip()
                    # Remove "Storage" suffix if present
                    storage = storage.replace(" Storage", "")
                    colour = storage_colour[1].strip()
                else:
                    # Only one attribute
                    storage = inner.strip()
                    storage = storage.replace(" Storage", "")
            else:
                model = name
                
        except Exception as e:
            logger.warning(f"Error parsing product name '{name}': {e}")
        
        return model, storage, colour
    
    def _extract_prices_from_context(self, context: str) -> tuple:
        """Extract selling price and MRP from HTML context"""
        # Vijay Sales uses data-price attributes and hidden spans
        # Format: <div class="discountedPrice" data-price="119900">
        selling_price = None
        mrp = None
        
        # Try to extract selling price from data-price attribute
        selling_price_match = re.search(r'data-price="(\d+)"', context)
        if selling_price_match:
            selling_price = parse_inr(selling_price_match.group(1))
        
        # Try to extract MRP from originalPrice section
        # Look for the originalPrice div and extract price from nested spans
        mrp_match = re.search(r'<div class="originalPrice[^"]*"[^>]*>.*?<div class="price">.*?<span>₹</span>\s*<span>(\d+)</span>', context, re.DOTALL)
        if mrp_match:
            mrp = parse_inr(mrp_match.group(1))
        
        # If no MRP found in originalPrice, try alternative patterns
        if not mrp:
            # Try extracting from any price span that might be MRP
            mrp_match = re.search(r'<span class="mrpLabel">MRP</span>.*?<span>₹</span>\s*<span>(\d+)</span>', context, re.DOTALL)
            if mrp_match:
                mrp = parse_inr(mrp_match.group(1))
        
        return selling_price, mrp
    
    def _extract_availability_from_context(self, context: str) -> str:
        """Extract stock status from HTML context"""
        # Try product-stock class first
        stock_match = re.search(r'<p class="product-stock">([^<]+)</p>', context)
        if stock_match:
            status = stock_match.group(1).strip()
            if "Out Of Stock" in status or "out of stock" in status.lower():
                return "Out of Stock"
            return status
        
        # Try stock-status class as fallback
        stock_match = re.search(r'<div class="stock-status">([^<]+)</div>', context)
        if stock_match:
            status = stock_match.group(1).strip()
            if "Out Of Stock" in status or "out of stock" in status.lower():
                return "Out of Stock"
            return status
        
        return "In Stock"  # Default if not found
    
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
        Public method to get Vijay Sales offers with robots.txt check and HTTP fetch.
        For testing/debugging with saved HTML, use parse_offers() directly.
        """
        try:
            # Robots.txt check is handled by http_client.get()
            html = http_client.get(self.OFFERS_URL)
            if not html:
                logger.error("Failed to fetch Vijay Sales offers page")
                return []
            
            return self.parse_offers(html)
            
        except Exception as e:
            logger.error(f"Error getting Vijay Sales offers: {e}")
            return []
    
    def parse_offers(self, html: str) -> List[RawOffer]:
        """
        Parse Vijay Sales offers HTML and return RawOffer objects.
        This method can be called directly with saved HTML for testing/debugging.
        """
        try:
            offers = self._parse_offers_from_html(html)
            logger.info(f"Parsed {len(offers)} offers from Vijay Sales HTML")
            return offers
            
        except Exception as e:
            logger.error(f"Error parsing Vijay Sales offers HTML: {e}")
            return []
    
    def _parse_offers_from_html(self, html: str) -> List[RawOffer]:
        offers = []
        
        # Parse offer items from HTML
        offer_pattern = r'<div class="offer-item">.*?</div>'
        offer_matches = re.findall(offer_pattern, html, re.DOTALL)
        
        for offer_html in offer_matches:
            try:
                # Extract bank name if present
                bank_match = re.search(r'<span class="bank-name">([^<]+)</span>', offer_html)
                bank = bank_match.group(1).strip() if bank_match else None
                
                # Extract offer details
                details_match = re.search(r'<span class="offer-details">([^<]+)</span>', offer_html)
                offer_text = details_match.group(1).strip() if details_match else ""
                
                # Extract discount amount if present
                discount_match = re.search(r'₹(\d+)', offer_text)
                offer_discount = None
                if discount_match:
                    offer_discount = Decimal(discount_match.group(1))
                
                offers.append(RawOffer(
                    offer_text=offer_text,
                    bank=bank,
                    offer_discount=offer_discount,
                    offer_type="bank_offer" if bank else None
                ))
                
            except Exception as e:
                logger.warning(f"Error parsing offer item: {e}")
                continue
        
        return offers