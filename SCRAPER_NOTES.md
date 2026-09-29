# Scraper Implementation Notes

## Multi-Source Architecture

The project now supports three e-commerce sources:
- **Croma**: JSON-LD + DOM hybrid parsing
- **Vijay Sales**: Direct DOM parsing with stock status
- **Reliance Digital**: DOM parsing with separate offers page

## Croma Adapter

### Availability Assumption
The Croma listing page does not show explicit "Out of Stock" markers on product cards. The availability field is currently hardcoded to "In Stock" for all parsed items. **This is an assumption, not a scraped fact.**

To improve this in the future:
- Fetch individual product pages to check availability
- Look for stock indicators in the DOM (may require JavaScript rendering)
- Add API-based stock checking if available

### Price Parsing
Price data is NOT available in JSON-LD, so the implementation uses a hybrid approach:
- JSON-LD provides product metadata (name, SKU, URLs)
- DOM parsing extracts price data by correlating JSON-LD items with HTML product cards

Price extraction logic:
- Find product card by matching variant_id (from JSON-LD) to HTML id attribute
- Extract selling_price: first ₹ amount in the card (followed by "Incl. all Taxes")
- Extract MRP: second ₹ amount in discount-container (only when discount exists)
- Calculate discount: MRP - selling_price (cross-checked with "Save ₹X" text)
- Handle missing MRP: new launches and non-discounted items only show selling_price

All 21 items now have selling_price extracted, with 6 items having MRP/discount (discounted products).

## Vijay Sales Adapter

### Product Name Format
- Format: "Apple <Model> (<Storage> GB Storage, <Colour>)"
- Extra word "Storage" and inconsistent spacing
- Custom parser removes "Apple " prefix and "Storage" suffix

### Price Format
- Format: "₹ 119900" (space after ₹, no comma)
- MRP always shown even with no discount
- When mrp == selling_price, discount = 0 (not None)

### Stock Status
- "Out Of Stock" text appears directly in-card
- Parsed from HTML instead of defaulting to "In Stock"

### Offer Badges
- Only appear in "Our Recommendations" section, not main grid
- Parsed from separate section for get_offers()

## Reliance Digital Adapter

### Product Name Format
- Format: "Apple <Model> <Storage>, <Colour>" (NO parentheses)
- Example: "Apple iPhone 18 Pro 2 TB, Glacier"
- Custom parser strips "Apple ", splits on last comma, regex extracts storage

### Price Format
- Format: "₹3,14,900.00" (comma AND trailing .00)
- No MRP shown on listing page
- No discount information on listing page
- Offers parsed from separate offers page only

### Availability
- No availability marker visible
- Defaults to "In Stock" (assumption, not scraped fact)

### JS Application Warning
- This site is a heavy JavaScript application
- Other category URLs on the same domain returned empty in testing
- Most likely to need USE_CACHED_DATA fallback in production

## Shared Price Parsing

### parse_inr() Function
Location: `scrapers/normalize.py`

Handles three known INR price formats:
- "₹1,28,490" (Croma format)
- "₹ 119900" (Vijay Sales format: space after ₹, no comma)
- "₹3,14,900.00" (Reliance format: comma and trailing .00)

All adapters use this shared function for consistent price parsing.

## Registry System

Location: `scrapers/registry.py`

Provides centralized access to all adapters:
- `get_scraper(name)`: Get adapter instance by name
- `list_scrapers()`: List all available scrapers

## Testing Strategy

All tests use fixture HTML files to avoid network calls:
- Croma: 25 tests, covers JSON-LD parsing, price extraction, offer badges
- Vijay Sales: 16 tests, covers custom name parsing, stock status, zero discount handling
- Reliance: 16 tests, covers no-parentheses name format, separate offers page
- Normalization: 9 tests, covers all three price formats

Total: 66 tests, all passing.

## API Usage

### Public Methods (with HTTP fetch)
```python
adapter = CromaAdapter()
listings = adapter.search("iPhone 17 Pro", storage="256GB", colour="Silver")
offers = adapter.get_offers()
```

### Testing Methods (with saved HTML)
```python
adapter = CromaAdapter()
with open('fixture.html', 'r') as f:
    html = f.read()
listings = adapter.parse_listing(html, query="iPhone 17 Pro")
offers = adapter.parse_offers(html)
```

### Registry Usage
```python
from scrapers.registry import get_scraper, list_scrapers

# Get specific adapter
croma = get_scraper("croma")

# List all available
print(list_scrapers())  # ['croma', 'vijaysales', 'reliance']
```