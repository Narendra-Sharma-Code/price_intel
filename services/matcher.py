import re
from typing import Dict, List, Tuple
from dataclasses import dataclass

from scrapers.types import RawListing


@dataclass
class MatchResult:
    """Result of a match operation with confidence score"""
    listings: List[RawListing]
    confidence: str  # "exact" or "fuzzy"
    variant_id: str


def normalize_storage(storage: str) -> str:
    """Normalize storage string to canonical form"""
    if not storage:
        return ""
    # Remove spaces, convert to lowercase
    normalized = re.sub(r'\s+', '', storage).lower()
    return normalized


def normalize_colour(colour: str) -> str:
    """Normalize colour string to canonical form"""
    if not colour:
        return ""
    # Remove spaces, convert to lowercase
    return re.sub(r'\s+', '', colour).lower()


def build_variant_id(brand: str, model: str, storage: str, colour: str) -> str:
    """
    Build a deterministic canonical variant ID from product attributes.
    
    Example: "apple-iphone-17-pro-256gb-silver"
    """
    # Normalize each component
    norm_brand = brand.lower().strip() if brand else ""
    norm_model = re.sub(r'\s+', '-', model.lower().strip()) if model else ""
    norm_storage = normalize_storage(storage)
    norm_colour = normalize_colour(colour)
    
    # Join with hyphens, skip empty components
    components = [c for c in [norm_brand, norm_model, norm_storage, norm_colour] if c]
    return "-".join(components)


def group_listings(listings: List[RawListing]) -> Dict[str, MatchResult]:
    """
    Group listings from multiple sources by variant ID.
    
    First attempts exact matches using build_variant_id.
    For unmatched listings, uses fuzzy matching on model names.
    
    Returns dict mapping variant_id to MatchResult with confidence.
    """
    # Separate matched and unmatched listings
    exact_groups: Dict[str, List[RawListing]] = {}
    unmatched: List[RawListing] = []
    
    # First pass: exact matches
    for listing in listings:
        variant_id = build_variant_id(
            listing.brand,
            listing.model,
            listing.storage,
            listing.colour
        )
        
        if variant_id not in exact_groups:
            exact_groups[variant_id] = []
        exact_groups[variant_id].append(listing)
    
    # Second pass: fuzzy match unmatched listings
    # (In this simple implementation, we just group by model name for fuzzy matches)
    fuzzy_groups: Dict[str, List[RawListing]] = {}
    
    # Get all unique model names from exact groups
    existing_models = set()
    for listings_list in exact_groups.values():
        for lst in listings_list:
            if lst.model:
                existing_models.add(lst.model.lower())
    
    # Try to fuzzy match unmatched listings
    from rapidfuzz import fuzz, process
    
    for listing in listings:
        if not listing.model:
            continue
        
        # Check if this listing is already in exact groups
        variant_id = build_variant_id(
            listing.brand,
            listing.model,
            listing.storage,
            listing.colour
        )
        
        if variant_id in exact_groups:
            continue  # Already matched exactly
        
        # Try fuzzy match against existing models
        if existing_models:
            # Find best match
            result = process.extractOne(
                listing.model.lower(),
                list(existing_models),
                scorer=fuzz.WRatio,
                score_cutoff=85  # Threshold for fuzzy match
            )
            
            if result:
                matched_model = result[0]
                score = result[1]
                
                # Find the variant_id for this matched model
                matched_variant_id = None
                for vid, lst in exact_groups.items():
                    for lst_item in lst:
                        if lst_item.model and lst_item.model.lower() == matched_model:
                            matched_variant_id = vid
                            break
                    if matched_variant_id:
                        break
                
                if matched_variant_id:
                    exact_groups[matched_variant_id].append(listing)
                else:
                    # Create new fuzzy group
                    if listing.model not in fuzzy_groups:
                        fuzzy_groups[listing.model] = []
                    fuzzy_groups[listing.model].append(listing)
            else:
                # No fuzzy match, create new group
                if listing.model not in fuzzy_groups:
                    fuzzy_groups[listing.model] = []
                fuzzy_groups[listing.model].append(listing)
        else:
            # No existing models, create new group
            if listing.model not in fuzzy_groups:
                fuzzy_groups[listing.model] = []
            fuzzy_groups[listing.model].append(listing)
    
    # Build final result dict with confidence scores
    result: Dict[str, MatchResult] = {}
    
    # Add exact groups
    for variant_id, listings_list in exact_groups.items():
        result[variant_id] = MatchResult(
            listings=listings_list,
            confidence="exact",
            variant_id=variant_id
        )
    
    # Add fuzzy groups
    for model_name, listings_list in fuzzy_groups.items():
        # Build a variant_id for the fuzzy group
        variant_id = f"fuzzy-{model_name.lower().replace(' ', '-')}"
        result[variant_id] = MatchResult(
            listings=listings_list,
            confidence="fuzzy",
            variant_id=variant_id
        )
    
    return result
