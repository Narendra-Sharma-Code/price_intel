from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
import uuid

db = SQLAlchemy()


class Crawl(db.Model):
    __tablename__ = 'crawl'

    id = db.Column(db.Integer, primary_key=True)
    crawl_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    query = db.Column(db.String, nullable=False)
    started_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    finished_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String, nullable=False)
    source_status = db.Column(db.JSON, nullable=True)

    listings = db.relationship('Listing', backref='crawl', lazy=True)


class Listing(db.Model):
    __tablename__ = 'listing'

    id = db.Column(db.Integer, primary_key=True)
    crawl_id = db.Column(db.String(36), db.ForeignKey('crawl.crawl_id'), nullable=False)
    variant_id = db.Column(db.String, nullable=False, index=True)
    source = db.Column(db.String, nullable=False, index=True)
    product_name = db.Column(db.String, nullable=True)
    brand = db.Column(db.String, nullable=True)
    model = db.Column(db.String, nullable=True)
    storage = db.Column(db.String, nullable=True)
    colour = db.Column(db.String, nullable=True)
    sku = db.Column(db.String, nullable=True)
    product_url = db.Column(db.String, nullable=True)
    image_url = db.Column(db.String, nullable=True)
    currency = db.Column(db.String, nullable=True)
    mrp = db.Column(db.Numeric(10, 2), nullable=True)
    selling_price = db.Column(db.Numeric(10, 2), nullable=True)
    discount = db.Column(db.Numeric(10, 2), nullable=True)
    availability = db.Column(db.String, nullable=True)
    seller = db.Column(db.String, nullable=True)
    rating = db.Column(db.Numeric(3, 2), nullable=True)
    review_count = db.Column(db.Integer, nullable=True)
    scraped_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    offers = db.relationship('Offer', backref='listing', lazy=True)


class Offer(db.Model):
    __tablename__ = 'offer'

    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('listing.id'), nullable=False)
    offer_text = db.Column(db.String, nullable=True)
    offer_type = db.Column(db.String, nullable=True)
    bank = db.Column(db.String, nullable=True)
    offer_discount = db.Column(db.Numeric(10, 2), nullable=True)
    min_purchase = db.Column(db.Numeric(10, 2), nullable=True)
    max_cap = db.Column(db.Numeric(10, 2), nullable=True)
    emi_available = db.Column(db.Boolean, nullable=False, default=False)
    emi_tenure = db.Column(db.Integer, nullable=True)
    emi_rate = db.Column(db.Numeric(5, 2), nullable=True)
    validity = db.Column(db.String, nullable=True)
