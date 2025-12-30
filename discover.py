import os
from dotenv import load_dotenv
from weconnect import weconnect

load_dotenv()
weConnect = weconnect.WeConnect(username=os.getenv('VW_USERNAME'), 
                                password=os.getenv('VW_PASSWORD'), 
                                updateAfterLogin=True)

for vin, vehicle in weConnect.vehicles.items():
    print(f"\n--- Vehicle: {vehicle.model.value} (VIN: {vin}) ---")
    print("Available Domains:")
    for domain in vehicle.domains.keys():
        print(f" - {domain}")