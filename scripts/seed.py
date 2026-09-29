#!/usr/bin/env python3
"""
Seed the database with sample crawl data from fixtures.
This creates a realistic sample crawl with 2-3 phone models across 3 sources.
"""
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, Crawl, Listing, Offer
from scrapers.croma import CromaAdapter
from scrapers.vijaysales import VijaySalesAdapter
from scrapers.reliance import RelianceDigitalAdapter
from services.matcher import build_variant_id


def load_fixture_file(filepath):
    """Load fixture file content"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def seed_database():
    """Seed database with sample crawl data"""
    app = create_app()
    
    with app.app_context():
        print("Seeding database with sample crawl data...")
        
        # Create a crawl row
        crawl_id = "sample-crawl-001"
        crawl = Crawl(
            crawl_id=crawl_id,
            query="iPhone 17 Pro",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            status="completed"
        )
        db.session.add(crawl)
        db.session.flush()
        
        # Load fixture data
        fixtures_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tests/fixtures")
        
        # Croma data
        croma_html = load_fixture_file(os.path.join(fixtures_dir, "croma/croma_listing.html"))
        croma_adapter = CromaAdapter()
        croma_listings = croma_adapter.parse_listing(croma_html)
        
        # Vijay Sales data
        vijaysales_html = load_fixture_file(os.path.join(fixtures_dir, "vijaysales/vijaysales_listing.html"))
        vijaysales_adapter = VijaySalesAdapter()
        vijaysales_listings = vijaysales_adapter.parse_listing(vijaysales_html)
        
        # Reliance data
        reliance_html = load_fixture_file(os.path.join(fixtures_dir, "reliance/reliance_listing.html"))
        reliance_adapter = RelianceDigitalAdapter()
        reliance_listings = reliance_adapter.parse_listing(reliance_html)
        
        # Save listings to DB (limit to a few to keep it small)
        all_listings = []
        
        # Save Croma listings (first 5)
        for listing in croma_listings[:5]:
            variant_id = build_variant_id(listing.brand, listing.model, listing.storage, listing.colour)
            db_listing = Listing(
                crawl_id=crawl.crawl_id,
                variant_id=variant_id,
                source="croma",
                product_name=listing.product_name,
                brand=listing.brand,
                model=listing.model,
                storage=listing.storage,
                colour=listing.colour,
                sku=listing.sku,
                selling_price=Decimal(str(listing.selling_price)) if listing.selling_price else None,
                mrp=Decimal(str(listing.mrp)) if listing.mrp else None,
                discount=Decimal(str(listing.discount)) if listing.discount else None,
                currency=listing.currency,
                availability=listing.availability,
                product_url=listing.product_url,
                image_url=listing.image_url,
                rating=listing.rating,
                review_count=listing.review_count,
                scraped_at=listing.scraped_at
            )
            db.session.add(db_listing)
            db.session.flush()
            all_listings.append((db_listing, listing))
        
        # Save Vijay Sales listings (first 3)
        for listing in vijaysales_listings[:3]:
            variant_id = build_variant_id(listing.brand, listing.model, listing.storage, listing.colour)
            db_listing = Listing(
                crawl_id=crawl.crawl_id,
                variant_id=variant_id,
                source="vijaysales",
                product_name=listing.product_name,
                brand=listing.brand,
                model=listing.model,
                storage=listing.storage,
                colour=listing.colour,
                sku=listing.sku,
                selling_price=Decimal(str(listing.selling_price)) if listing.selling_price else None,
                mrp=Decimal(str(listing.mrp)) if listing.mrp else None,
                discount=Decimal(str(listing.discount)) if listing.discount else None,
                currency=listing.currency,
                availability=listing.availability,
                product_url=listing.product_url,
                image_url=listing.image_url,
                rating=listing.rating,
                review_count=listing.review_count,
                scraped_at=listing.scraped_at
            )
            db.session.add(db_listing)
            db.session.flush()
            all_listings.append((db_listing, listing))
        
        # Save Reliance listings (all 3)
        for listing in reliance_listings:
            variant_id = build_variant_id(listing.brand, listing.model, listing.storage, listing.colour)
            db_listing = Listing(
                crawl_id=crawl.crawl_id,
                variant_id=variant_id,
                source="reliance",
                product_name=listing.product_name,
                brand=listing.brand,
                model=listing.model,
                storage=listing.storage,
                colour=listing.colour,
                sku=listing.sku,
                selling_price=Decimal(str(listing.selling_price)) if listing.selling_price else None,
                mrp=Decimal(str(listing.mrp)) if listing.mrp else None,
                discount=Decimal(str(listing.discount)) if listing.discount else None,
                currency=listing.currency,
                availability=listing.availability,
                product_url=listing.product_url,
                image_url=listing.image_url,
                rating=listing.rating,
                review_count=listing.review_count,
                scraped_at=listing.scraped_at
            )
            db.session.add(db_listing)
            db.session.flush()
            all_listings.append((db_listing, listing))
        
        # Load and save offers
        # Croma offers
        croma_offers_html = load_fixture_file(os.path.join(fixtures_dir, "croma/croma_offers.html"))
        croma_offers = croma_adapter.parse_offers(croma_offers_html)
        
        # Vijay Sales offers
        vijaysales_offers_html = load_fixture_file(os.path.join(fixtures_dir, "vijaysales/vijaysales_offers.html"))
        vijaysales_offers = vijaysales_adapter.parse_offers(vijaysales_offers_html)
        
        # Reliance offers
        reliance_offers_html = load_fixture_file(os.path.join(fixtures_dir, "reliance/reliance_offers.html"))
        reliance_offers = reliance_adapter.parse_offers(reliance_offers_html)
        
        # Assign offers to listings from same source
        for db_listing, raw_listing in all_listings:
            source = db_listing.source
            
            if source == "croma" and croma_offers:
                for offer in croma_offers[:2]:  # Assign first 2 offers
                    db_offer = Offer(
                        listing_id=db_listing.id,
                        offer_text=offer.offer_text,
                        offer_type=offer.offer_type,
                        bank=offer.bank,
                        offer_discount=Decimal(str(offer.offer_discount)) if offer.offer_discount else None,
                        min_purchase=Decimal(str(offer.min_purchase)) if offer.min_purchase else None,
                        max_cap=Decimal(str(offer.max_cap)) if offer.max_cap else None,
                        emi_available=offer.emi_available,
                        emi_tenure=offer.emi_tenure,
                        emi_rate=Decimal(str(offer.emi_rate)) if offer.emi_rate else None,
                        validity=offer.validity
                    )
                    db.session.add(db_offer)
            
            elif source == "vijaysales" and vijaysales_offers:
                for offer in vijaysales_offers[:1]:  # Assign first offer
                    db_offer = Offer(
                        listing_id=db_listing.id,
                        offer_text=offer.offer_text,
                        offer_type=offer.offer_type,
                        bank=offer.bank,
                        offer_discount=Decimal(str(offer.offer_discount)) if offer.offer_discount else None,
                        min_purchase=Decimal(str(offer.min_purchase)) if offer.min_purchase else None,
                        max_cap=Decimal(str(offer.max_cap)) if offer.max_cap else None,
                        emi_available=offer.emi_available,
                        emi_tenure=offer.emi_tenure,
                        emi_rate=Decimal(str(offer.emi_rate)) if offer.emi_rate else None,
                        validity=offer.validity
                    )
                    db.session.add(db_offer)
            
            elif source == "reliance" and reliance_offers:
                for offer in reliance_offers[:1]:  # Assign first offer
                    db_offer = Offer(
                        listing_id=db_listing.id,
                        offer_text=offer.offer_text,
                        offer_type=offer.offer_type,
                        bank=offer.bank,
                        offer_discount=Decimal(str(offer.offer_discount)) if offer.offer_discount else None,
                        min_purchase=Decimal(str(offer.min_purchase)) if offer.min_purchase else None,
                        max_cap=Decimal(str(offer.max_cap)) if offer.max_cap else None,
                        emi_available=offer.emi_available,
                        emi_tenure=offer.emi_tenure,
                        emi_rate=Decimal(str(offer.emi_rate)) if offer.emi_rate else None,
                        validity=offer.validity
                    )
                    db.session.add(db_offer)
        
        db.session.commit()
        
        print(f"✓ Created crawl: {crawl.crawl_id}")
        print(f"✓ Saved {len(all_listings)} listings")
        print(f"✓ Saved offers for listings")
        print("\nDatabase seeded successfully!")


if __name__ == "__main__":
    seed_database()
