import os
from dotenv import load_dotenv
from weconnect import weconnect

load_dotenv()
weConnect = weconnect.WeConnect(username=os.getenv('VW_USERNAME'), 
                                password=os.getenv('VW_PASSWORD'), 
                                updateAfterLogin=True)

vin = list(weConnect.vehicles.keys())[0]
vehicle = weConnect.vehicles[vin]

print(f"\n--- Capabilities for {vehicle.model.value} ---")
if 'userCapabilities' in vehicle.domains:
    capabilities = vehicle.domains['userCapabilities']
    for cap_id, capability in capabilities.items():
        # Look for anything related to honk, flash, or remote control
        status = capability.status.value if hasattr(capability, 'status') else "N/A"
        print(f"Capability: {cap_id} | Status: {status}")
else:
    print("User Capabilities domain not found.")