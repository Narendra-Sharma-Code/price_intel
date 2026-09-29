from scrapers.base import BaseAdapter, http_client
from scrapers.types import RawListing, RawOffer
from scrapers.croma import CromaAdapter
from scrapers.vijaysales import VijaySalesAdapter
from scrapers.reliance import RelianceDigitalAdapter

__all__ = ['BaseAdapter', 'http_client', 'RawListing', 'RawOffer', 'CromaAdapter', 'VijaySalesAdapter', 'RelianceDigitalAdapter']
