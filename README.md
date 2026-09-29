# Price Intel

A Flask-based price intelligence application for Indian retailers that aggregates product prices and offers from Croma, Vijay Sales, and Reliance Digital. It normalizes retailer-specific product data, groups equivalent product variants across sources, and provides price comparison, offer-adjusted effective prices, EMI calculations, and rankings via a JSON API.

## Quick Start

### Local Setup

```bash
# Clone the repository
git clone <repository-url>
cd price_intel

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
flask db upgrade

# Seed database with sample data (optional)
python scripts/seed.py

# Run the application
export USE_CACHED_DATA=true  # Required for demo without live scraping
flask run
```

### Docker Setup

```bash
# Clone the repository
git clone <repository-url>
cd price_intel

# Build and run with Docker Compose
docker compose up
```

The application will be available at `http://localhost:5000`.

## Setup & Run

### Local (Virtual Environment)

```bash
# 1. Create virtual environment
python3 -m venv venv

# 2. Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Initialize database with migrations
flask db upgrade

# 5. (Optional) Seed database with sample data
python scripts/seed.py

# 6. Set environment variable for cached mode
export USE_CACHED_DATA=true

# 7. Run the application
flask run
```

### Docker

```bash
# 1. Build and run with Docker Compose
docker compose up

# The application starts automatically on port 5000
# Access at http://localhost:5000
```

## Demo Without Live Scraping

**Important:** To demo the application without live scraping, you must set `USE_CACHED_DATA=true`. This is required because:

- **Croma** returns HTTP 403 for requests from unfamiliar IPs (bot detection)
- **Vijay Sales** and **Reliance Digital** may rate-limit or block requests from unfamiliar IPs
- This is expected behavior and by design, not a bug

With `USE_CACHED_DATA=true`, the application:
1. Queries the database for cached crawl data
2. If no cache exists, parses saved HTML fixtures from `tests/fixtures/{source}/`
3. Returns real product data without making live HTTP requests

```bash
export USE_CACHED_DATA=true
flask run
```

Then search for "iPhone 17 Pro" to see real cross-source results from Croma and Reliance.

## Architecture Overview

The application is structured with clear separation of concerns:

```
app.py                 # Flask application factory and API routes
├── models.py          # SQLAlchemy models (Crawl, Listing, Offer)
├── config.py          # Configuration management
├── scrapers/          # Retailer-specific adapters
│   ├── base.py        # BaseAdapter with HTTP client, robots.txt handling
│   ├── croma.py       # Croma adapter (JSON-LD parsing)
│   ├── vijaysales.py  # Vijay Sales adapter (URL-based parsing)
│   ├── reliance.py    # Reliance Digital adapter (JSON-LD parsing)
│   ├── normalize.py   # Shared price/colour/storage normalization
│   ├── types.py       # RawListing and RawOffer dataclasses
│   └── registry.py    # Centralized adapter registry
├── services/          # Pure business logic (no Flask/scraper imports)
│   ├── matcher.py     # Product matching and grouping
│   ├── offers.py      # Offer parsing and effective price calculation
│   ├── emi.py         # EMI calculations (reducing-balance formula)
│   ├── ranking.py     # Price ranking
│   └── search.py      # Orchestration layer
└── templates/
    └── index.html     # Single-page UI
```

**Why this structure:**
- **Scrapers** are isolated from business logic, making them testable with HTML fixtures
- **Services** are pure functions without Flask/scraper dependencies, enabling unit testing
- **Normalization** is centralized in `scrapers/normalize.py` to handle format differences
- **Matching** uses exact canonical IDs first, then fuzzy matching for naming variants

## How to Add a New Retailer Adapter

1. Create a new file in `scrapers/` (e.g., `scrapers/newretailer.py`)
2. Implement the `BaseAdapter` class:
   ```python
   from scrapers.base import BaseAdapter
   from scrapers.types import RawListing, RawOffer
   
   class NewRetailerAdapter(BaseAdapter):
       name = "newretailer"
       LISTING_URL = "https://www.newretailer.com/products"
       OFFERS_URL = "https://www.newretailer.com/offers"
       
       def parse_listing(self, html: str) -> List[RawListing]:
           # Parse product listings from HTML
           pass
       
       def parse_offers(self, html: str) -> List[RawOffer]:
           # Parse offers from HTML
           pass
   ```
3. Register the adapter in `scrapers/registry.py`:
   ```python
   from scrapers.newretailer import NewRetailerAdapter
   
   _ADAPTERS = {
       "croma": CromaAdapter,
       "vijaysales": VijaySalesAdapter,
       "reliance": RelianceDigitalAdapter,
       "newretailer": NewRetailerAdapter,  # Add here
   }
   ```
4. Add fixture files in `tests/fixtures/newretailer/` for testing
5. Add unit tests in `tests/test_newretailer.py`

## EMI and Offer Assumptions

### EMI Calculation

- **Formula:** Standard reducing-balance (amortization) formula
  ```
  r = annual_rate / 12 / 100
  EMI = P * r * (1+r)^n / ((1+r)^n - 1)
  ```
  Where P = principal, r = monthly interest rate, n = tenure in months

- **Zero-rate case:** If `annual_rate == 0`, EMI = P / n (no-cost EMI)

- **Default rate:** 12% annual rate is used when the user doesn't supply one

- **Precision:** All calculations use `Decimal` and round to nearest rupee

### Offer Application

- **Unrestricted offers:** Applied to effective price regardless of bank
- **Bank-restricted offers:** Only applied when `selected_bank` matches the offer's bank
- **Conditional offers:** Shown as conditional (not applied to effective price) when bank doesn't match
- **Applied offer:** The single best offer that can be applied to the listing
- **Conditional offers:** All other bank-restricted offers that don't match the selected bank

## Matching Approach

### Variant ID Construction

```python
build_variant_id(brand, model, storage, colour)
# Example: "apple-iphone-17-pro-256gb-silver"
```

- Normalizes storage and colour using patterns from `scrapers/normalize.py`
- Converts to lowercase and joins with hyphens
- Ensures consistent IDs across sources despite format differences

### Matching Strategy

1. **Exact match first:** Listings with identical `variant_id` are grouped together
2. **Fuzzy match fallback:** If no exact match, uses `rapidfuzz` for model name similarity
   - Threshold: 85% similarity
   - Matches "iPhone 17 Pro" with "Apple iPhone 17 Pro"
   - Does NOT match "iPhone 17 Pro" with "iPhone 17 Pro Max" (word boundaries)

### Confidence Levels

- **Exact:** Listings grouped by identical `variant_id`
- **Fuzzy:** Listings grouped by fuzzy model name matching

## Known Limitations

1. **Croma blocking:** Returns HTTP 403 for live scraping from unfamiliar IPs (bot detection). Use `USE_CACHED_DATA=true` for demo.

2. **Reliance Digital:** Heavy JavaScript application. Only some category URLs return data via plain HTTP. The fixture data may not represent the full live catalog.

3. **Placeholder URLs:** Some Reliance fixture entries have placeholder product URLs for variants not available live at capture time.

4. **Rating/review_count:** Not populated for these sources (not exposed on listing pages).

5. **Offer parsing:** Multi-brand comparison tables are skipped as noise. Only Apple-specific offers are retained.

6. **Live reliability:** Vijay Sales and Reliance may rate-limit or block requests from unfamiliar IPs. Use cached mode for reliable demos.

## How to Run Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_croma.py -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

**Current test count:** 96 tests passing

## API Endpoints

- `POST /api/search` - Search products with filters
- `GET /api/product/<variant_id>` - Get most recent listings for a variant
- `GET /api/offers/<variant_id>` - Get offers for a variant
- `GET /api/price-history/<variant_id>` - Get price history grouped by source
- `GET /health` - Health check

## Sample Output

See `sample_output/search_iphone_17_pro.json` for a complete API response example, and `sample_output/search_iphone_17_pro.csv` for a flattened CSV representation.
