import os
from dotenv import load_dotenv
from weconnect import weconnect

load_dotenv()
weConnect = weconnect.WeConnect(username=os.getenv('VW_USERNAME'), 
                                password=os.getenv('VW_PASSWORD'), 
                                updateAfterLogin=True)

vin = list(weConnect.vehicles.keys())[0]
vehicle = weConnect.vehicles[vin]

def print_elements(name, domain):
    print(f"\n--- Domain: {name} ---")
    for key, element in domain.items():
        print(f" Element: {key}")
        # If it's a control or has sub-elements, let's see them
        if hasattr(element, 'elements'):
            for sub_key in element.elements.keys():
                print(f"   - Sub-Element: {sub_key}")

if 'vehicleLights' in vehicle.domains:
    print_elements('vehicleLights', vehicle.domains['vehicleLights'])

if 'access' in vehicle.domains:
    print_elements('access', vehicle.domains['access'])