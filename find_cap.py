import os
from dotenv import load_dotenv
from weconnect import weconnect

load_dotenv()
try:
    weConnect = weconnect.WeConnect(username=os.getenv('VW_USERNAME'), 
                                    password=os.getenv('VW_PASSWORD'), 
                                    updateAfterLogin=True)

    vin = list(weConnect.vehicles.keys())[0]
    vehicle = weConnect.vehicles[vin]

    print(f"\n--- Checking EVERYTHING in userCapabilities for {vehicle.model.value} ---")
    
    if 'userCapabilities' in vehicle.domains:
        caps_status = vehicle.domains['userCapabilities']['capabilitiesStatus']
        
        # We search the object's internal dictionary for anything that looks like a capability list
        # In newer versions, it's often stored in 'capabilities' or just directly in the object
        data_source = None
        if hasattr(caps_status, 'capabilities'):
            data_source = caps_status.capabilities
        elif hasattr(caps_status, 'elements'):
            data_source = caps_status.elements
        
        if data_source:
            for key, cap in data_source.items():
                # Status '0' usually means the car is authorized to do this
                status = getattr(cap.status, 'value', 'Unknown Status')
                print(f"ID: {key:35} | Status: {status}")
        else:
            print("Could not find a list of capabilities. Dumping object attributes:")
            print(dir(caps_status))
            
    else:
        print("Domain 'userCapabilities' not found.")

except Exception as e:
    print(f"Error: {e}")