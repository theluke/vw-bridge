import os
from dotenv import load_dotenv
from weconnect import weconnect

load_dotenv()
weConnect = weconnect.WeConnect(username=os.getenv('VW_USERNAME'), 
                                password=os.getenv('VW_PASSWORD'), 
                                updateAfterLogin=True)

vin = list(weConnect.vehicles.keys())[0]
vehicle = weConnect.vehicles[vin]

print(f"Searching for Honk/Flash control in {vehicle.model.value}...")

# Search the entire object tree for anything named 'honkAndFlash'
found = False
for domain_name, domain in vehicle.domains.items():
    if 'honkAndFlash' in str(domain_name).lower():
        print(f"!!! Found domain: {domain_name}")
        found = True

# Also check if it's a 'service'
if hasattr(vehicle, 'services'):
    for service_id, service in vehicle.services.items():
        if 'honk' in service_id.lower():
            print(f"!!! Found service: {service_id}")
            found = True

if not found:
    print("Standard search failed. Trying deep object traversal...")
    # This looks at every property in the vehicle object
    for attr in dir(vehicle):
        if 'honk' in attr.lower():
            print(f"!!! Found attribute: {attr}")

print("\nScan complete.")