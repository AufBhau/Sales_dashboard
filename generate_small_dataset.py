import csv
from datetime import datetime, timedelta

# Small dataset for quick testing
data = []

# Last 30 days
end_date = datetime.now()
start_date = end_date - timedelta(days=30)

products = ['Product A', 'Product B', 'Product C']
regions = ['North', 'South', 'East']

current_date = start_date
while current_date <= end_date:
    for product in products:
        for region in regions:
            if product == 'Product A':
                revenue = 15000
                leads = 300
                conversions = 90
            elif product == 'Product B':
                revenue = 12000
                leads = 250
                conversions = 65
            else:  # Product C
                revenue = 8000
                leads = 200
                conversions = 35
            
            # Regional variation
            if region == 'North':
                revenue = int(revenue * 1.2)
            elif region == 'South':
                revenue = int(revenue * 1.0)
            else:  # East
                revenue = int(revenue * 0.9)
            
            data.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'product': product,
                'region': region,
                'revenue': revenue,
                'leads': leads,
                'conversions': conversions
            })
    
    current_date += timedelta(days=1)

# Save to CSV
filename = 'sales_data_30_days.csv'
with open(filename, 'w', newline='') as csvfile:
    fieldnames = ['date', 'product', 'region', 'revenue', 'leads', 'conversions']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    
    writer.writeheader()
    for row in data:
        writer.writerow(row)

print(f"✅ Generated {len(data)} records!")
print(f"📁 Saved to: {filename}")
print(f"📅 Date range: Last 30 days")