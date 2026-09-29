# Vijay Sales Listing Page Notes

## Page Structure
- URL: https://www.vijaysales.com/c/iphones?cityId=1
- Main product grid with individual product cards
- Separate "Our Recommendations" section with offer badges

## Product Card Structure
- Product URL pattern: /p/{parentId}/{variantId}/{slug}
- Use variantId (2nd numeric segment) as SKU
- Product name format: "Apple <Model> (<Storage> GB Storage, <Colour>)"
- Price format: "₹ 119900" (space after ₹, no comma)
- MRP always shown even with no discount
- "Out Of Stock" text appears directly in-card when unavailable
- Offer badges only in "Our Recommendations" section, not main grid

## Key Differences from Croma
- Extra word "Storage" in product name
- Space after ₹ symbol
- No commas in price
- MRP always shown (mrp == selling_price when no discount)
- Stock status explicitly shown in card
- Offer badges in separate section