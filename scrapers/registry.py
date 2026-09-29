from scrapers.croma import CromaAdapter
from scrapers.vijaysales import VijaySalesAdapter
from scrapers.reliance import RelianceDigitalAdapter

# Registry of all available scrapers
SCRAPER_REGISTRY = {
    "croma": CromaAdapter,
    "vijaysales": VijaySalesAdapter,
    "reliance": RelianceDigitalAdapter,
}


def get_scraper(name: str):
    """Get a scraper instance by name"""
    scraper_class = SCRAPER_REGISTRY.get(name.lower())
    if scraper_class:
        return scraper_class()
    raise ValueError(f"Unknown scraper: {name}. Available: {list(SCRAPER_REGISTRY.keys())}")


def list_scrapers():
    """List all available scrapers"""
    return list(SCRAPER_REGISTRY.keys())
