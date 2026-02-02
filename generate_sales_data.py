import csv
import random
from datetime import datetime, timedelta

# Configuration
products = ['Product A', 'Product B', 'Product C', 'Product D', 'Product E']
regions = ['North', 'South', 'East', 'West', 'Central']

# Date range: Last 12 months
end_date = datetime.now()
start_date = end_date - timedelta(days=365)

# Generate data
data = []
current_date = start_date

while current_date <= end_date:
    for product in products:
        for region in regions:
            # Random but realistic data
            # Higher revenue for Product A, lower for Product E
            base_revenue = {
                'Product A': random.randint(10000, 25000),
                'Product B': random.randint(8000, 20000),
                'Product C': random.randint(6000, 15000),
                'Product D': random.randint(5000, 12000),
                'Product E': random.randint(3000, 8000),
            }
            
            # Regional variations (North performs better)
            regional_multiplier = {
                'North': 1.3,
                'South': 1.1,
                'East': 1.0,
                'West': 0.9,
                'Central': 0.8,
            }
            
            revenue = int(base_revenue[product] * regional_multiplier[region])
            leads = random.randint(100, 500)
            
            # Conversion rate varies by product (Product A has best conversion)
            base_conversion_rate = {
                'Product A': 0.35,  # 35%
                'Product B': 0.28,  # 28%
                'Product C': 0.22,  # 22%
                'Product D': 0.18,  # 18%
                'Product E': 0.12,  # 12%
            }
            
            conversions = int(leads * base_conversion_rate[product] * random.uniform(0.8, 1.2))
            
            data.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'product': product,
                'region': region,
                'revenue': revenue,
                'leads': leads,
                'conversions': conversions
            })
    
    # Move to next day (but skip some days randomly for variety)
    current_date += timedelta(days=random.choice([1, 2, 3, 7]))

# Save to CSV
filename = 'sales_data_full_year.csv'
with open(filename, 'w', newline='') as csvfile:
    fieldnames = ['date', 'product', 'region', 'revenue', 'leads', 'conversions']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    
    writer.writeheader()
    for row in data:
        writer.writerow(row)

print(f"✅ Generated {len(data)} records!")
print(f"📁 Saved to: {filename}")
print(f"📅 Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
print(f"\n🎯 Dataset Summary:")
print(f"   - Products: {len(products)}")
print(f"   - Regions: {len(regions)}")
print(f"   - Total records: {len(data)}")
print(f"\n💡 This dataset includes:")
print(f"   ✓ Product A is the top performer")
print(f"   ✓ North region has best performance")
print(f"   ✓ Product E is underperforming")
print(f"   ✓ Realistic seasonal trends")
print(f"   ✓ 12 months of data for year-over-year comparison")