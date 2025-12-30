import os
from dotenv import load_dotenv
from weconnect import weconnect

load_dotenv()
weConnect = weconnect.WeConnect(username=os.getenv('VW_USERNAME'), 
                                password=os.getenv('VW_PASSWORD'), 
                                updateAfterLogin=True)

vin = list(weConnect.vehicles.keys())[0]
vehicle = weConnect.vehicles[vin]

print(f"Scanning all domains for controls on {vehicle.model.value}...")

for domain_name, domain in vehicle.domains.items():
    for element_name, element in domain.items():
        # We are looking for anything that is 'Control' or has 'enabled' property
        if hasattr(element, 'enabled') or "Control" in str(type(element)):
            print(f"FOUND CONTROL: [{domain_name}] -> {element_name}")
            print(f"  - Type: {type(element)}")
            if hasattr(element, 'value'):
                print(f"  - Current Value: {element.value}")