import time
import logging
import urllib.robotparser
from abc import ABC, abstractmethod
from typing import List, Optional
from urllib.parse import urlparse
import httpx

from scrapers.types import RawListing, RawOffer

logger = logging.getLogger(__name__)


class RobotsTxtCache:
    def __init__(self):
        self.cache = {}
        self.rp = urllib.robotparser.RobotFileParser()

    def can_fetch(self, url: str, user_agent: str = "*") -> bool:
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        
        if domain not in self.cache:
            robots_url = f"{domain}/robots.txt"
            try:
                self.rp.set_url(robots_url)
                self.rp.read()
                self.cache[domain] = self.rp
                logger.info(f"Fetched robots.txt for {domain}")
            except Exception as e:
                logger.warning(f"Failed to fetch robots.txt for {domain}: {e}")
                self.cache[domain] = None
        
        if self.cache[domain] is None:
            return True
        
        return self.cache[domain].can_fetch(user_agent, url)


robots_cache = RobotsTxtCache()


class HTTPClient:
    def __init__(self):
        self.client = httpx.Client(
            timeout=10.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )
        self.last_request_time = {}
        self.min_delay = 1.5

    def get(self, url: str) -> Optional[str]:
        if not robots_cache.can_fetch(url):
            logger.warning(f"robots.txt disallows: {url}")
            return None
        
        parsed = urlparse(url)
        domain = parsed.netloc
        current_time = time.time()
        
        if domain in self.last_request_time:
            elapsed = current_time - self.last_request_time[domain]
            if elapsed < self.min_delay:
                sleep_time = self.min_delay - elapsed
                logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s for {domain}")
                time.sleep(sleep_time)
        
        for attempt in range(3):
            try:
                response = self.client.get(url)
                self.last_request_time[domain] = time.time()
                
                if response.status_code == 200:
                    return response.text
                elif response.status_code == 429:
                    backoff = (2 ** attempt) * 1.5
                    logger.warning(f"Rate limited (429) on {url}, retrying in {backoff}s (attempt {attempt + 1}/3)")
                    time.sleep(backoff)
                elif response.status_code in (403, 404):
                    logger.warning(f"HTTP {response.status_code} for {url}")
                    return None
                elif response.status_code >= 500:
                    backoff = (2 ** attempt) * 1.5
                    logger.warning(f"Server error {response.status_code} for {url}, retrying in {backoff}s (attempt {attempt + 1}/3)")
                    time.sleep(backoff)
                else:
                    logger.warning(f"Unexpected status {response.status_code} for {url}")
                    return None
                    
            except httpx.TimeoutException:
                logger.warning(f"Timeout fetching {url} (attempt {attempt + 1}/3)")
                if attempt < 2:
                    time.sleep((2 ** attempt) * 1.5)
            except httpx.ConnectError:
                logger.warning(f"Connection error for {url} (attempt {attempt + 1}/3)")
                if attempt < 2:
                    time.sleep((2 ** attempt) * 1.5)
            except Exception as e:
                logger.error(f"Unexpected error fetching {url}: {e}")
                return None
        
        logger.error(f"Failed to fetch {url} after 3 attempts")
        return None

    def close(self):
        self.client.close()


http_client = HTTPClient()


class BaseAdapter(ABC):
    name: str = "base"
    
    @abstractmethod
    def search(self, query: str, storage: Optional[str] = None, colour: Optional[str] = None) -> List[RawListing]:
        pass
    
    @abstractmethod
    def get_offers(self) -> List[RawOffer]:
        pass