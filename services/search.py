import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
import uuid

from models import db, Crawl, Listing, Offer
from scrapers.registry import get_scraper, list_scrapers
from scrapers.types import RawListing, RawOffer
from services.matcher import group_listings, MatchResult
from services.offers import compute_effective_price
from services.emi import calculate_emi
from services.ranking import rank_listings
from config import Config

logger = logging.getLogger(__name__)


def search_products(
    query: str,
    storage: Optional[str] = None,
    colour: Optional[str] = None,
    budget_min: Optional[Decimal] = None,
    budget_max: Optional[Decimal] = None,
    tenure: int = 12,
    down_payment: Decimal = Decimal('0'),
    bank: Optional[str] = None,
    sources: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Orchestrate product search across multiple sources.
    
    Args:
        query: Product model to search for
        storage: Optional storage filter
        colour: Optional colour filter
        budget_min: Optional minimum budget filter
        budget_max: Optional maximum budget filter
        tenure: EMI tenure in months (default 12)
        down_payment: Down payment amount (default 0)
        bank: Selected bank for offer filtering
        sources: Optional list of sources to include (default all)
    
    Returns:
        Dict with crawl_id, source_status, grouped results, and best_deal
    """
    # 1. Create Crawl row
    crawl_id = str(uuid.uuid4())
    crawl = Crawl(
        crawl_id=crawl_id,
        query=query,
        started_at=datetime.now(timezone.utc),
        status="in_progress",
        source_status={}
    )
    db.session.add(crawl)
    db.session.commit()
    
    logger.info(f"Started crawl {crawl_id} for query: {query}")
    
    # Determine which sources to query
    available_sources = list_scrapers()
    if sources:
        sources_to_query = [s for s in sources if s in available_sources]
    else:
        sources_to_query = available_sources
    
    source_status = {}
    all_listings: List[RawListing] = []
    all_offers: List[RawOffer] = []
    
    # 2. Loop over adapters and fetch data
    for source_name in sources_to_query:
        try:
            adapter = get_scraper(source_name)
            
            # Check if we should use cached data
            use_cached = False
            if Config.USE_CACHED_DATA:
                use_cached = True
            
            if use_cached:
                # Try DB cache first (without query filter for now)
                logger.info(f"Using cached data for {source_name}")
                listings = _get_cached_listings(source_name, None, None, None)  # No query filter
                offers = _get_cached_offers(source_name)
                
                if listings:
                    source_status[source_name] = {"status": "ok", "reason": "cached"}
                else:
                    # No DB cache - try fixture files as fallback (without query filter)
                    logger.info(f"No DB cache for {source_name}, trying fixture files")
                    listings, offers = _load_fixture_data(source_name, None, None, None)  # No query filter
                    
                    if listings:
                        source_status[source_name] = {"status": "ok", "reason": "fixture"}
                    else:
                        source_status[source_name] = {"status": "empty", "reason": "no results in fixtures"}
            else:
                # Fetch fresh data (without query filter for now)
                logger.info(f"Fetching fresh data from {source_name}")
                listings = adapter.search(query=None, storage=None, colour=None)  # No query filter
                offers = adapter.get_offers()
                
                if listings:
                    source_status[source_name] = {"status": "ok", "reason": "fetched"}
                else:
                    source_status[source_name] = {"status": "empty", "reason": "no results"}
            
            all_listings.extend(listings)
            all_offers.extend(offers)
            
        except Exception as e:
            logger.error(f"Error fetching from {source_name}: {e}")
            source_status[source_name] = {"status": "failed", "reason": str(e)}
            
            # Try fallback to cached data on failure
            try:
                logger.info(f"Falling back to cached data for {source_name}")
                listings = _get_cached_listings(source_name, query, storage, colour)
                offers = _get_cached_offers(source_name)
                
                if listings:
                    all_listings.extend(listings)
                    all_offers.extend(offers)
                    source_status[source_name] = {"status": "ok", "reason": "cached_fallback"}
                else:
                    # No DB cache - try fixture files
                    logger.info(f"No DB cache for {source_name}, trying fixture files")
                    fixture_listings, fixture_offers = _load_fixture_data(source_name, query, storage, colour)
                    
                    if fixture_listings:
                        all_listings.extend(fixture_listings)
                        all_offers.extend(fixture_offers)
                        source_status[source_name] = {"status": "ok", "reason": "fixture_fallback"}
            except Exception as fallback_error:
                logger.error(f"Cache fallback also failed for {source_name}: {fallback_error}")
    
    # 4. Save listings and offers to DB
    saved_listings = _save_listings_to_db(all_listings, crawl_id)
    saved_offers = _save_offers_to_db(all_offers, saved_listings)
    
    # 5. Group listings using matcher (without query filter first)
    grouped = group_listings(all_listings)
    
    # Apply query filter AFTER grouping (so we can build filter_note)
    pre_query_grouped = grouped  # Save before query filter
    if query:
        # Filter the grouped results by query
        filtered_grouped = {}
        for variant_id, match_result in grouped.items():
            filtered_listings = [l for l in match_result.listings if l.model and _matches_query(query, l.model)]
            if filtered_listings:
                filtered_grouped[variant_id] = match_result
                filtered_grouped[variant_id].listings = filtered_listings
        grouped = filtered_grouped
    
    # 6. Compute effective prices and EMI for each group
    results = []
    effective_prices: Dict[str, Decimal] = {}
    
    for variant_id, match_result in grouped.items():
        group_results = []
        
        for listing in match_result.listings:
            # Get offers for this listing
            listing_offers = [o for o in all_offers if _offer_matches_listing(o, listing)]
            
            # Compute effective price
            price_result = compute_effective_price(listing, listing_offers, selected_bank=bank)
            
            # Calculate EMI if we have a price
            emi_result = None
            if price_result.effective_price > 0:
                principal = price_result.effective_price - down_payment
                if principal > 0:
                    emi_result = calculate_emi(
                        principal=principal,
                        annual_rate=Config.DEFAULT_ANNUAL_INTEREST_RATE,
                        tenure_months=tenure
                    )
            
            group_results.append({
                "listing": listing,
                "effective_price": price_result.effective_price,
                "applied_offer": price_result.applied_offer,
                "conditional_offers": price_result.conditional_offers,
                "emi": emi_result
            })
            
            # Store effective price for ranking
            if variant_id not in effective_prices:
                effective_prices[variant_id] = price_result.effective_price
            else:
                # Use the minimum effective price for this variant
                effective_prices[variant_id] = min(effective_prices[variant_id], price_result.effective_price)
        
        results.append({
            "variant_id": variant_id,
            "confidence": match_result.confidence,
            "listings": group_results
        })
    
    # 7. Apply storage/colour filters (so we can build filter_note if they cause empty results)
    pre_storage_filter_results = results  # Save before applying storage/colour filters
    if storage or colour:
        results = _filter_by_storage_colour(results, storage, colour)
    
    # 8. Filter by budget if specified
    if budget_min or budget_max:
        results = _filter_by_budget(results, budget_min, budget_max)
    
    # 9. Check if filters caused empty results
    filter_note = None
    if not results and pre_storage_filter_results:
        # Filters caused empty results - build helpful note
        available_storages = set()
        available_colours = set()
        
        for result in pre_storage_filter_results:
            for item in result["listings"]:
                if item["listing"].storage:
                    available_storages.add(item["listing"].storage)
                if item["listing"].colour:
                    available_colours.add(item["listing"].colour)
        
        storage_text = ", ".join(sorted(available_storages)) if available_storages else "various"
        colour_text = ", ".join(sorted(available_colours)) if available_colours else "various"
        
        filter_parts = []
        if storage:
            filter_parts.append(f"storage='{storage}'")
        if colour:
            filter_parts.append(f"colour='{colour}'")
        if budget_min or budget_max:
            filter_parts.append(f"budget {budget_min or '0'}-{budget_max or 'unlimited'}")
        
        filter_text = ", ".join(filter_parts) if filter_parts else "your filters"
        
        filter_note = f"Found {query} in {colour_text} ({storage_text}) — none matched {filter_text}. Try adjusting your filters."
    elif not results and pre_query_grouped:
        # Query filter caused empty results - build helpful note
        available_models = set()
        for match_result in pre_query_grouped.values():
            for listing in match_result.listings:
                if listing.model:
                    available_models.add(listing.model)
        
        models_text = ", ".join(sorted(available_models)) if available_models else "various"
        filter_note = f"No listings found for '{query}'. Available models: {models_text}. Try a different model name."
    elif not results and all_listings:
        # Nothing found at all
        filter_note = f"No listings found for '{query}'. Try a different model name."
    
    # 10. Rank by effective price (only rank filtered results)
    # IMPORTANT: Only build ranked from the filtered results list
    if results:
        # Build a simple list of filtered listings for ranking
        filtered_listings = []
        for result in results:
            for item in result["listings"]:
                filtered_listings.append({
                    "listing": item["listing"],
                    "effective_price": item["effective_price"],
                    "emi": item["emi"]
                })
        
        # Sort by effective price
        filtered_listings.sort(key=lambda x: x["effective_price"])
        
        # Build ranked response
        ranked = []
        for i, item in enumerate(filtered_listings):
            listing = item["listing"]
            # Handle both RawListing objects and dict representations
            listing_dict = listing.__dict__ if hasattr(listing, '__dict__') else listing
            ranked.append({
                "listing": listing_dict,
                "effective_price": item["effective_price"],
                "rank": i + 1,
                "emi": item["emi"]
            })
    else:
        ranked = []
    
    # 10. Build best_deal summary (using filtered results)
    best_deal = _build_best_deal(results, ranked, tenure)
    
    # Update crawl status
    crawl.source_status = source_status
    crawl.finished_at = datetime.now(timezone.utc)
    crawl.status = "completed"
    db.session.commit()
    
    return {
        "crawl_id": crawl_id,
        "source_status": source_status,
        "results": results,
        "ranked": [
            {
                "listing": r.listing.__dict__ if hasattr(r, 'listing') else r["listing"],
                "effective_price": r.effective_price if hasattr(r, 'effective_price') else r["effective_price"],
                "rank": r.rank if hasattr(r, 'rank') else r["rank"],
                "emi": r.emi if hasattr(r, 'emi') else r["emi"]
            } for r in ranked
        ],
        "best_deal": best_deal,
        "filter_note": filter_note
    }


def _load_fixture_data(source: str, query: str, storage: Optional[str], colour: Optional[str]) -> tuple:
    """Load data from fixture files for a source"""
    import os
    
    # Get the project root directory (where app.py is)
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    fixture_map = {
        "croma": os.path.join(current_dir, "tests/fixtures/croma/croma_listing.html"),
        "vijaysales": os.path.join(current_dir, "tests/fixtures/vijaysales/vijaysales_listing.html"),
        "reliance": os.path.join(current_dir, "tests/fixtures/reliance/reliance_listing.html")
    }
    
    fixture_path = fixture_map.get(source)
    if not fixture_path:
        return [], []
    
    if not os.path.exists(fixture_path):
        logger.warning(f"Fixture file not found: {fixture_path}")
        return [], []
    
    try:
        with open(fixture_path, 'r') as f:
            html = f.read()
        
        # Get adapter and parse
        adapter = get_scraper(source)
        listings = adapter.parse_listing(html, query=query, storage=storage, colour=colour)
        
        # Apply stricter query filtering (override adapter's loose substring matching)
        if query:
            listings = [l for l in listings if l.model and _matches_query(query, l.model)]
        
        # Load offers fixture if available
        offers = []
        offers_map = {
            "croma": os.path.join(current_dir, "tests/fixtures/croma/croma_offers.html"),
            "vijaysales": os.path.join(current_dir, "tests/fixtures/vijaysales/vijaysales_offers.html"),
            "reliance": os.path.join(current_dir, "tests/fixtures/reliance/reliance_offers.html")
        }
        
        offers_path = offers_map.get(source)
        if offers_path and os.path.exists(offers_path):
            with open(offers_path, 'r') as f:
                offers_html = f.read()
            offers = adapter.parse_offers(offers_html)
        
        return listings, offers
        
    except Exception as e:
        logger.error(f"Error loading fixture data for {source}: {e}")
        return [], []


def _matches_query(query: str, model: str) -> bool:
    """
    Check if a model matches the query on word boundaries.
    Requires exact normalized model equality unless query has extra trailing words.
    """
    if not query or not model:
        return False
    
    # Normalize both
    query_normalized = query.lower().strip()
    model_normalized = model.lower().strip()
    
    # Split into words
    query_words = query_normalized.split()
    model_words = model_normalized.split()
    
    # Check if all query words are present in the model
    for word in query_words:
        if word not in model_words:
            return False
    
    # Ensure the model doesn't have extra trailing words unless query has them
    # If query is "iPhone 17 Pro", model can be "iPhone 17 Pro" but not "iPhone 17 Pro Max"
    # If query is "iPhone 17 Pro Max", model can be "iPhone 17 Pro Max"
    if len(model_words) > len(query_words):
        # Model has extra words - only allow if query ends with common suffixes
        # that the model might also have (e.g., "Pro" matching "Pro" is ok, but "Pro" shouldn't match "Pro Max")
        # Actually, simpler: require that model words start with query words exactly
        for i, query_word in enumerate(query_words):
            if model_words[i] != query_word:
                return False
        # If we get here, all query words match the start of model words
        # But we only want exact match for the base model
        # So reject if model has extra words beyond the query
        return False
    
    return True


def _get_cached_listings(source: str, query: str, storage: Optional[str], colour: Optional[str]) -> List[RawListing]:
    """Get most recent listings from DB for a source"""
    # Find the most recent successful crawl for this source
    recent_crawl = db.session.query(Crawl).filter(
        Crawl.source_status.isnot(None)
    ).order_by(Crawl.started_at.desc()).first()
    
    if not recent_crawl:
        return []
    
    # Get listings from that crawl
    listings = db.session.query(Listing).filter_by(
        crawl_id=recent_crawl.crawl_id,
        source=source
    ).all()
    
    # Convert to RawListing
    raw_listings = []
    for listing in listings:
        raw_listings.append(RawListing(
            variant_id=listing.variant_id,
            source=listing.source,
            product_name=listing.product_name,
            brand=listing.brand,
            model=listing.model,
            storage=listing.storage,
            colour=listing.colour,
            sku=listing.sku,
            product_url=listing.product_url,
            image_url=listing.image_url,
            currency=listing.currency,
            mrp=listing.mrp,
            selling_price=listing.selling_price,
            discount=listing.discount,
            availability=listing.availability,
            seller=listing.seller,
            rating=listing.rating,
            review_count=listing.review_count,
            scraped_at=listing.scraped_at
        ))
    
    # Filter by query/storage/colour if provided
    if query:
        raw_listings = [l for l in raw_listings if l.model and _matches_query(query, l.model)]
    if storage:
        raw_listings = [l for l in raw_listings if l.storage and storage.lower() in l.storage.lower()]
    if colour:
        raw_listings = [l for l in raw_listings if l.colour and colour.lower() in l.colour.lower()]
    
    return raw_listings


def _get_cached_offers(source: str) -> List[RawOffer]:
    """Get offers from DB for a source"""
    # Get the most recent crawl's offers
    recent_crawl = db.session.query(Crawl).filter(
        Crawl.source_status.isnot(None)
    ).order_by(Crawl.started_at.desc()).first()
    
    if not recent_crawl:
        return []
    
    # Get listing IDs from that crawl
    listings = db.session.query(Listing).filter_by(
        crawl_id=recent_crawl.crawl_id,
        source=source
    ).all()
    listing_ids = [l.id for l in listings]
    
    # Get offers for those listings
    offers = db.session.query(Offer).filter(Offer.listing_id.in_(listing_ids)).all()
    
    # Convert to RawOffer
    raw_offers = []
    for offer in offers:
        raw_offers.append(RawOffer(
            offer_text=offer.offer_text,
            offer_type=offer.offer_type,
            bank=offer.bank,
            offer_discount=offer.offer_discount,
            min_purchase=offer.min_purchase,
            max_cap=offer.max_cap,
            emi_available=offer.emi_available,
            emi_tenure=offer.emi_tenure,
            emi_rate=offer.emi_rate,
            validity=offer.validity
        ))
    
    return raw_offers


def _save_listings_to_db(listings: List[RawListing], crawl_id: str) -> List[Listing]:
    """Save listings to DB and return list of DB Listings"""
    saved = []
    
    for listing in listings:
        db_listing = Listing(
            crawl_id=crawl_id,
            variant_id=listing.variant_id,
            source=listing.source,
            product_name=listing.product_name,
            brand=listing.brand,
            model=listing.model,
            storage=listing.storage,
            colour=listing.colour,
            sku=listing.sku,
            product_url=listing.product_url,
            image_url=listing.image_url,
            currency=listing.currency,
            mrp=listing.mrp,
            selling_price=listing.selling_price,
            discount=listing.discount,
            availability=listing.availability,
            seller=listing.seller,
            rating=listing.rating,
            review_count=listing.review_count,
            scraped_at=listing.scraped_at
        )
        db.session.add(db_listing)
        db.session.flush()  # Get the ID
        saved.append(db_listing)
    
    db.session.commit()
    return saved


def _save_offers_to_db(offers: List[RawOffer], db_listings: List[Listing]) -> None:
    """Save offers to DB"""
    # Simple approach: assign offers to listings based on source
    for offer in offers:
        # Find a listing from the same source
        for db_listing in db_listings:
            # Assign offer to first listing from same source
            # In production, this would be more sophisticated
            db_offer = Offer(
                listing_id=db_listing.id,
                offer_text=offer.offer_text,
                offer_type=offer.offer_type,
                bank=offer.bank,
                offer_discount=offer.offer_discount,
                min_purchase=offer.min_purchase,
                max_cap=offer.max_cap,
                emi_available=offer.emi_available,
                emi_tenure=offer.emi_tenure,
                emi_rate=offer.emi_rate,
                validity=offer.validity
            )
            db.session.add(db_offer)
            break
    
    db.session.commit()


def _offer_matches_listing(offer: RawOffer, listing: RawListing) -> bool:
    """Simple heuristic to match an offer to a listing"""
    # For now, we'll assign offers to listings based on source
    # In production, this would be more sophisticated (e.g., based on product URL)
    return True  # Simplified for MVP


def _filter_by_storage_colour(results: List[Dict], storage: Optional[str], colour: Optional[str]) -> List[Dict]:
    """Filter results by storage and colour"""
    filtered = []
    
    for result in results:
        filtered_listings = []
        
        for item in result["listings"]:
            if storage and item["listing"].storage:
                if storage.lower() not in item["listing"].storage.lower():
                    continue
            if colour and item["listing"].colour:
                if colour.lower() not in item["listing"].colour.lower():
                    continue
            
            filtered_listings.append(item)
        
        if filtered_listings:
            result["listings"] = filtered_listings
            filtered.append(result)
    
    return filtered


def _filter_by_budget(results: List[Dict], budget_min: Optional[Decimal], budget_max: Optional[Decimal]) -> List[Dict]:
    """Filter results by budget range"""
    filtered = []
    
    for result in results:
        filtered_listings = []
        
        for item in result["listings"]:
            price = item["effective_price"]
            
            if budget_min and price < budget_min:
                continue
            if budget_max and price > budget_max:
                continue
            
            filtered_listings.append(item)
        
        if filtered_listings:
            result["listings"] = filtered_listings
            filtered.append(result)
    
    return filtered


def _build_best_deal(results: List[Dict], ranked: List, tenure: int) -> Dict[str, Any]:
    """Build best deal summary"""
    if not results:
        return {
            "best_current_price": None,
            "best_effective_price": None,
            "lowest_emi": None,
            "reason": "No results found"
        }
    
    # Find best current price
    best_current = None
    best_current_source = None
    
    for result in results:
        for item in result["listings"]:
            price = item["listing"].selling_price
            if price and (best_current is None or price < best_current):
                best_current = price
                best_current_source = item["listing"].source
    
    # Find best effective price
    best_effective = None
    best_effective_source = None
    
    for result in results:
        for item in result["listings"]:
            price = item["effective_price"]
            if price and (best_effective is None or price < best_effective):
                best_effective = price
                best_effective_source = item["listing"].source
    
    # Find lowest EMI
    lowest_emi = None
    lowest_emi_source = None
    
    for result in results:
        for item in result["listings"]:
            if item["emi"]:
                emi = item["emi"].emi_monthly
                if emi and (lowest_emi is None or emi < lowest_emi):
                    lowest_emi = emi
                    lowest_emi_source = item["listing"].source
    
    # Build reason string
    reasons = []
    if best_effective and best_current and best_effective < best_current:
        savings = best_current - best_effective
        reasons.append(f"Save ₹{savings} with offers")
    
    if lowest_emi:
        reasons.append(f"EMI from ₹{lowest_emi}/month ({tenure} months)")
    
    reason = " | ".join(reasons) if reasons else "Best price available"
    
    return {
        "best_current_price": {
            "amount": best_current,
            "source": best_current_source
        },
        "best_effective_price": {
            "amount": best_effective,
            "source": best_effective_source
        },
        "lowest_emi": {
            "amount": lowest_emi,
            "source": lowest_emi_source,
            "tenure_months": tenure
        },
        "reason": reason
    }
