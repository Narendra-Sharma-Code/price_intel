import logging
import sys
from flask import Flask, jsonify, request, render_template
from flask_migrate import Migrate
from sqlalchemy import text
from decimal import Decimal, InvalidOperation
from config import Config
from models import db, Crawl, Listing, Offer
from services.search import search_products

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(levelname)s - %(module)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate = Migrate(app, db)

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/health')
    def health():
        try:
            db.session.execute(text('SELECT 1'))
            return jsonify({'status': 'ok', 'db': 'connected'}), 200
        except Exception as e:
            logger.error(f'Health check failed: {e}')
            return jsonify({'status': 'error', 'db': 'disconnected', 'error': str(e)}), 500

    @app.route('/api/search', methods=['POST'])
    def api_search():
        """Search for products across multiple sources"""
        try:
            data = request.get_json()
            
            # Validate required field
            if not data or 'model' not in data:
                return jsonify({'error': 'Missing required field: model'}), 400
            
            query = data['model']
            
            # Extract optional parameters
            storage = data.get('storage')
            colour = data.get('colour')
            budget_min = _parse_decimal(data.get('budget_min'))
            budget_max = _parse_decimal(data.get('budget_max'))
            tenure = data.get('tenure', 12)
            down_payment = _parse_decimal(data.get('down_payment', '0'))
            bank = data.get('bank')
            sources = data.get('sources')
            
            # Call search service
            result = search_products(
                query=query,
                storage=storage,
                colour=colour,
                budget_min=budget_min,
                budget_max=budget_max,
                tenure=tenure,
                down_payment=down_payment,
                bank=bank,
                sources=sources
            )
            
            return jsonify(result), 200
            
        except Exception as e:
            logger.error(f'Search error: {e}')
            return jsonify({'error': str(e)}), 500

    @app.route('/api/product/<variant_id>')
    def api_product(variant_id):
        """Get the most recent listings for a variant"""
        try:
            # Find the most recent crawl
            recent_crawl = db.session.query(Crawl).order_by(Crawl.started_at.desc()).first()
            
            if not recent_crawl:
                return jsonify({'error': 'No crawl data available'}), 404
            
            # Get listings for this variant from the most recent crawl
            listings = db.session.query(Listing).filter_by(
                crawl_id=recent_crawl.crawl_id,
                variant_id=variant_id
            ).all()
            
            if not listings:
                return jsonify({'error': 'Variant not found'}), 404
            
            # Convert to dict
            result = []
            for listing in listings:
                result.append({
                    'id': listing.id,
                    'variant_id': listing.variant_id,
                    'source': listing.source,
                    'product_name': listing.product_name,
                    'brand': listing.brand,
                    'model': listing.model,
                    'storage': listing.storage,
                    'colour': listing.colour,
                    'sku': listing.sku,
                    'product_url': listing.product_url,
                    'image_url': listing.image_url,
                    'currency': listing.currency,
                    'mrp': str(listing.mrp) if listing.mrp else None,
                    'selling_price': str(listing.selling_price) if listing.selling_price else None,
                    'discount': str(listing.discount) if listing.discount else None,
                    'availability': listing.availability,
                    'seller': listing.seller,
                    'rating': str(listing.rating) if listing.rating else None,
                    'review_count': listing.review_count,
                    'scraped_at': listing.scraped_at.isoformat() if listing.scraped_at else None
                })
            
            return jsonify(result), 200
            
        except Exception as e:
            logger.error(f'Product lookup error: {e}')
            return jsonify({'error': str(e)}), 500

    @app.route('/api/offers/<variant_id>')
    def api_offers(variant_id):
        """Get offers for a variant"""
        try:
            # Find the most recent crawl
            recent_crawl = db.session.query(Crawl).order_by(Crawl.started_at.desc()).first()
            
            if not recent_crawl:
                return jsonify({'error': 'No crawl data available'}), 404
            
            # Get listings for this variant
            listings = db.session.query(Listing).filter_by(
                crawl_id=recent_crawl.crawl_id,
                variant_id=variant_id
            ).all()
            
            if not listings:
                return jsonify({'error': 'Variant not found'}), 404
            
            # Get offers for these listings
            listing_ids = [l.id for l in listings]
            offers = db.session.query(Offer).filter(Offer.listing_id.in_(listing_ids)).all()
            
            # Convert to dict
            result = []
            for offer in offers:
                result.append({
                    'id': offer.id,
                    'listing_id': offer.listing_id,
                    'offer_text': offer.offer_text,
                    'offer_type': offer.offer_type,
                    'bank': offer.bank,
                    'offer_discount': str(offer.offer_discount) if offer.offer_discount else None,
                    'min_purchase': str(offer.min_purchase) if offer.min_purchase else None,
                    'max_cap': str(offer.max_cap) if offer.max_cap else None,
                    'emi_available': offer.emi_available,
                    'emi_tenure': offer.emi_tenure,
                    'emi_rate': str(offer.emi_rate) if offer.emi_rate else None,
                    'validity': offer.validity
                })
            
            return jsonify(result), 200
            
        except Exception as e:
            logger.error(f'Offers lookup error: {e}')
            return jsonify({'error': str(e)}), 500

    @app.route('/api/price-history/<variant_id>')
    def api_price_history(variant_id):
        """Get price history for a variant, grouped by source"""
        try:
            # Get all listings for this variant, ordered by scraped_at
            listings = db.session.query(Listing).filter_by(variant_id=variant_id).order_by(Listing.scraped_at.desc()).all()
            
            if not listings:
                return jsonify({'error': 'Variant not found'}), 404
            
            # Group by source
            history = {}
            for listing in listings:
                source = listing.source
                if source not in history:
                    history[source] = []
                
                history[source].append({
                    'id': listing.id,
                    'crawl_id': listing.crawl_id,
                    'selling_price': str(listing.selling_price) if listing.selling_price else None,
                    'mrp': str(listing.mrp) if listing.mrp else None,
                    'discount': str(listing.discount) if listing.discount else None,
                    'scraped_at': listing.scraped_at.isoformat() if listing.scraped_at else None
                })
            
            return jsonify(history), 200
            
        except Exception as e:
            logger.error(f'Price history error: {e}')
            return jsonify({'error': str(e)}), 500

    return app


def _parse_decimal(value):
    """Parse a value to Decimal, return None if invalid"""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (ValueError, InvalidOperation):
        return None


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
