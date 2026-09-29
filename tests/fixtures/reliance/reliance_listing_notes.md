# Reliance Digital Listing Page Notes

## Page Structure
- URL: https://www.reliancedigital.in/collection/ios-phones
- Heavy JavaScript application
- Other category URLs on same domain returned empty in testing
- Product grid with individual product cards

## Product Card Structure
- Product URL pattern: /product/{slug}-{modelCode}-{numericId}
- Use trailing numeric id as SKU
- Product name format: "Apple <Model> <Storage>, <Colour>" (NO parentheses)
- Example: "Apple iPhone 18 Pro 2 TB, Glacier"
- Price format: "₹3,14,900.00" (comma AND trailing .00)
- No MRP shown on listing page
- No discount information on listing page
- No offer badges on listing page
- No availability marker visible

## Key Differences from Croma
- No parentheses in product name
- Comma and decimal in price format
- No MRP/discount on listing page
- Offers on separate page only
- Heavy JS app (most likely to need USE_CACHED_DATA fallback)

## Parsing Strategy
- Strip "Apple " prefix
- Split on last comma for colour
- Use regex to extract storage token
- Everything before storage is model
- Parse offers from separate offers page only