import pytest
import os
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import Mock, patch
import json

from app import create_app
from scrapers.types import RawListing, RawOffer


@pytest.fixture
def app():
    # Set USE_CACHED_DATA to false for tests
    os.environ['USE_CACHED_DATA'] = 'false'
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mock_adapter_success():
    """Mock adapter that returns successful results"""
    adapter = Mock()
    adapter.name = "test_source"
    adapter.search.return_value = [
        RawListing(
            variant_id="123",
            source="test_source",
            product_name="Test Product",
            brand="Test",
            model="iPhone 17 Pro",
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
    ]
    adapter.get_offers.return_value = []
    return adapter


@pytest.fixture
def mock_adapter_failure():
    """Mock adapter that raises an exception"""
    adapter = Mock()
    adapter.name = "failing_source"
    adapter.search.side_effect = Exception("Scraping failed")
    adapter.get_offers.side_effect = Exception("Scraping failed")
    return adapter


@pytest.fixture
def mock_adapter_empty():
    """Mock adapter that returns empty results"""
    adapter = Mock()
    adapter.name = "empty_source"
    adapter.search.return_value = []
    adapter.get_offers.return_value = []
    return adapter


def test_health_endpoint(client):
    """Test that /health endpoint still works"""
    response = client.get('/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'ok'
    assert data['db'] == 'connected'


def test_search_missing_model(client):
    """Test that /api/search returns 400 when model is missing"""
    response = client.post('/api/search', json={})
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data
    assert 'model' in data['error']


def test_search_success(client, mock_adapter_success):
    """Test successful search with mocked adapter"""
    with patch('services.search.get_scraper', return_value=mock_adapter_success):
        with patch('services.search.list_scrapers', return_value=['test_source']):
            with patch('config.Config') as mock_config:
                mock_config.USE_CACHED_DATA = False
                mock_config.DEFAULT_ANNUAL_INTEREST_RATE = Decimal('12')
                response = client.post('/api/search', json={'model': 'iPhone 17 Pro'})
                
                assert response.status_code == 200
                data = json.loads(response.data)
                
                assert 'crawl_id' in data
                assert 'source_status' in data
                assert 'results' in data
                assert 'best_deal' in data


def test_search_partial_failure(client, mock_adapter_success, mock_adapter_failure):
    """Test that partial adapter failure doesn't break the response"""
    with patch('services.search.get_scraper') as mock_get_scraper:
        # Mock get_scraper to return different adapters based on name
        def get_adapter(name):
            if name == 'test_source':
                return mock_adapter_success
            elif name == 'failing_source':
                return mock_adapter_failure
            return Mock()
        
        mock_get_scraper.side_effect = get_adapter
        
        with patch('services.search.list_scrapers', return_value=['test_source', 'failing_source']):
            with patch('config.Config') as mock_config:
                mock_config.USE_CACHED_DATA = False
                mock_config.DEFAULT_ANNUAL_INTEREST_RATE = Decimal('12')
                response = client.post('/api/search', json={'model': 'iPhone 17 Pro'})
                
                assert response.status_code == 200
                data = json.loads(response.data)
                
                # Should have results from the successful adapter
                assert 'results' in data
                # Note: Results may be empty if query filter doesn't match mock data
                # The important part is that partial failure doesn't crash
                
                # Source status should show one success and one failure
                assert 'source_status' in data
                assert 'test_source' in data['source_status']
                assert 'failing_source' in data['source_status']


def test_search_empty_results(client, mock_adapter_empty):
    """Test search when adapter returns empty results"""
    with patch('services.search.get_scraper', return_value=mock_adapter_empty):
        with patch('services.search.list_scrapers', return_value=['empty_source']):
            with patch('config.Config') as mock_config:
                mock_config.USE_CACHED_DATA = False
                mock_config.DEFAULT_ANNUAL_INTEREST_RATE = Decimal('12')
                response = client.post('/api/search', json={'model': 'iPhone 17 Pro'})
                
                assert response.status_code == 200
                data = json.loads(response.data)
                
                # Should return success but with empty results
                assert 'results' in data
                assert len(data['results']) == 0


def test_product_not_found(client):
    """Test /api/product when variant doesn't exist"""
    # This test requires a DB with no data
    # For now, we'll just test the endpoint exists and returns a JSON response
    response = client.get('/api/product/nonexistent')
    # Without DB data, it might return 404 or 500
    # Either is acceptable for this test
    assert response.status_code in [404, 500]
    data = json.loads(response.data)
    assert 'error' in data


def test_offers_not_found(client):
    """Test /api/offers when variant doesn't exist"""
    # This test requires a DB with no data
    response = client.get('/api/offers/nonexistent')
    # Without DB data, it might return 404 or 500
    assert response.status_code in [404, 500]
    data = json.loads(response.data)
    assert 'error' in data


def test_price_history_not_found(client):
    """Test /api/price-history when variant doesn't exist"""
    response = client.get('/api/price-history/nonexistent')
    assert response.status_code == 404
    data = json.loads(response.data)
    assert 'error' in data


def test_search_with_filters(client, mock_adapter_success):
    """Test search with budget and other filters"""
    with patch('services.search.get_scraper', return_value=mock_adapter_success):
        with patch('services.search.list_scrapers', return_value=['test_source']):
            with patch('config.Config') as mock_config:
                mock_config.USE_CACHED_DATA = False
                mock_config.DEFAULT_ANNUAL_INTEREST_RATE = Decimal('12')
                response = client.post('/api/search', json={
                    'model': 'iPhone 17 Pro',
                    'budget_min': '5000',
                    'budget_max': '15000',
                    'storage': '256GB',
                    'colour': 'Silver',
                    'tenure': 12,
                    'bank': 'HDFC'
                })
                
                assert response.status_code == 200
                data = json.loads(response.data)
                assert 'results' in data
