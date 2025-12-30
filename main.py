import os
import logging
import time
from flask import Flask, jsonify
from dotenv import load_dotenv
from weconnect import weconnect

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()
USERNAME = os.getenv('VW_USERNAME')
PASSWORD = os.getenv('VW_PASSWORD')
SPIN = os.getenv('VW_SPIN')

app = Flask(__name__)

def get_weconnect():
    """Attempts to connect to VW with retries for those 500 errors."""
    for i in range(3):
        try:
            return weconnect.WeConnect(
                username=USERNAME, 
                password=PASSWORD, 
                updateAfterLogin=True,
                updatePictures=False # Critical: Avoids 429/500 errors
            )
        except Exception as e:
            logger.warning(f"Connection attempt {i+1} failed: {e}. Retrying in 10s...")
            time.sleep(10)
    return None

# Initialize once
weConnect = get_weconnect()

def perform_action(mode_string):
    if not weConnect:
        return {"error": "VW Server is down (500). Try again later."}, 503
    
    try:
        weConnect.update()
        vin = list(weConnect.vehicles.keys())[0]
        vehicle = weConnect.vehicles[vin]

        # Use the absolute path logic that the CLI uses
        control = None
        if hasattr(vehicle, 'controls'):
            # In your GTE, it's usually an attribute of the controls object
            control = getattr(vehicle.controls, 'honkAndFlash', None)
        
        if control:
            control.value.mode.value = mode_string 
            control.value.spin.value = SPIN
            control.enabled = True
            logger.info(f"Successfully sent {mode_string} to {vin}")
            return {"status": "success", "action": mode_string}, 200
        
        return {"error": "Control honkAndFlash not found on this vehicle"}, 404

    except Exception as e:
        logger.error(f"Action failed: {str(e)}")
        return {"status": "error", "message": str(e)}, 500

@app.route('/horn')
def trigger_horn():
    res, code = perform_action('honkandflash')
    return jsonify(res), code

@app.route('/flash')
def trigger_flash():
    res, code = perform_action('flash')
    return jsonify(res), code

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)