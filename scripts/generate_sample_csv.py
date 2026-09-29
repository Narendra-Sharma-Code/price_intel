#!/usr/bin/env python3
"""
Generate CSV from search JSON response.
"""
import json
import csv
import sys

# Read the JSON file
with open('sample_output/search_iphone_17_pro.json', 'r') as f:
    data = json.load(f)

# Write CSV
with open('sample_output/search_iphone_17_pro.csv', 'w', newline='') as csvfile:
    fieldnames = ['source', 'product_name', 'storage', 'colour', 'selling_price', 
                  'effective_price', 'emi_monthly', 'availability', 'product_url']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    
    writer.writeheader()
    
    for item in data.get('ranked', []):
        listing = item['listing']
        emi_monthly = item.get('emi', {}).get('emi_monthly') if item.get('emi') else None
        
        writer.writerow({
            'source': listing['source'],
            'product_name': listing['product_name'],
            'storage': listing['storage'],
            'colour': listing['colour'],
            'selling_price': listing['selling_price'],
            'effective_price': item['effective_price'],
            'emi_monthly': emi_monthly,
            'availability': listing['availability'],
            'product_url': listing['product_url']
        })

print("✓ Generated sample_output/search_iphone_17_pro.csv")
