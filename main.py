import os
import subprocess
import logging
from flask import Flask, jsonify
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load credentials
load_dotenv()
USERNAME = os.getenv('VW_USERNAME')
PASSWORD = os.getenv('VW_PASSWORD')
SPIN = os.getenv('VW_SPIN')
VIN = 'WVWZZZAUZLW802874'

# Absolute path to your venv's CLI tool
CLI_PATH = '/home/luca/scripts/vw-bridge/venv/bin/weconnect-cli'

app = Flask(__name__)

def run_vw_command(action_type):
    """
    Executes the CLI command as a subprocess.
    action_type: 'flash' or 'honkandflash'
    """
    cmd = [
        CLI_PATH,
        '--username', USERNAME,
        '--password', PASSWORD,
        '--spin', SPIN,
        'set', f'/vehicles/{VIN}/controls/honkAndFlash', action_type
    ]
    
    try:
        logger.info(f"Executing CLI command for: {action_type}")
        # Run the command and wait for it to finish
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            logger.info(f"CLI Success: {result.stdout.strip()}")
            return {"status": "success", "action": action_type}, 200
        else:
            logger.error(f"CLI Failed: {result.stderr.strip()}")
            return {"status": "error", "message": result.stderr.strip()}, 500
            
    except Exception as e:
        logger.error(f"System error: {str(e)}")
        return {"status": "error", "message": str(e)}, 500

@app.route('/horn', methods=['GET'])
def trigger_horn():
    res, code = run_vw_command('honkandflash')
    return jsonify(res), code

@app.route('/flash', methods=['GET'])
def trigger_flash():
    res, code = run_vw_command('flash')
    return jsonify(res), code

if __name__ == '__main__':
    # Flask listens on port 5000 for SmartThings
    app.run(host='0.0.0.0', port=5000)