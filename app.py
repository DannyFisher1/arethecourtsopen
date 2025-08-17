# FILE: tennis/app.py
# --------------------------------------------------------------------------------
#!/usr/bin/env python3
"""
Tennis Courts Status API with Telegram Bot Control
"""

from math import floor
import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any
from flask import Flask, jsonify, render_template
from telegram.ext import Application
import threading
import time
from dotenv import load_dotenv
import aiohttp
import asyncio
import weather_set
from telegram_handlers import TelegramHandlers

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
DEFAULT_OPEN_HOUR = int(os.getenv('DEFAULT_OPEN_HOUR'))
DEFAULT_CLOSE_HOUR = str(os.getenv('DEFAULT_CLOSE_HOUR'))

# Court status storage (in production, use a database)
COURT_STATUS = {
    "status": "open",  # open, closed, closed_until
    "temperature": 0,
    "precipitation": 0,
    "conditions": "Checking conditions...",
    "last_updated": datetime.now().isoformat(),
    "updated_by": "system",
    "manual_override": False,
    "notes": "",  # Additional notes about court status
    "hours": {"open": DEFAULT_OPEN_HOUR, "close": DEFAULT_CLOSE_HOUR},  # Regular operating hours
    "hours_override": None,  # Temporary hours override for specific day
    "closed_until": None  # ISO datetime string for when courts reopen
}
CONDITIONS = weather_set.MET_WEATHER_CONDITIONS


# --- CONFIGURATION FROM ENVIRONMENT VARIABLES ---
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
AUTHORIZED_USERS = set(map(int, os.getenv('AUTHORIZED_USERS', '').split(',')) if os.getenv('AUTHORIZED_USERS') else [])

# App Configuration
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', 5001))

# Auto Status Logic
WEATHER_LOCATION = os.getenv('WEATHER_LOCATION', 'New York, NY')





# --- END OF CONFIGURATION ---


async def get_met_weather(lat=40.7128, lon=-74.0060, user_headers=None):
    url = f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={lat}&lon={lon}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise Exception(f"Weather API returned status {resp.status}")
                
                data = await resp.json()
                current = data["properties"]["timeseries"][0]
                
                weather_data = {
                    "temperature": floor((current["data"]["instant"]["details"]["air_temperature"])*1.8+32),
                    "precipitation": current["data"].get("next_1_hours", {}).get("details", {}).get("precipitation_amount", 0),
                    "conditions": CONDITIONS.get(current["data"].get("next_1_hours", {}).get("summary", {}).get("symbol_code", "unknown"), "unknown")
                }
                
                return weather_data
                
    except Exception as e:
        logger.error(f"Weather fetch failed: {e}")
        raise

def get_weather_data(user_headers=None):
    """Synchronous wrapper for the async weather function"""
    try:
        weather_data = asyncio.run(get_met_weather(user_headers=user_headers))
        return weather_data
    except Exception as e:
        # Return default values if weather fetch fails
        return {
            "temperature": 0,
            "precipitation": 0,
            "conditions": f"Weather unavailable"
        }

def update_status(status: str, updated_by: str = "system", manual_override: bool = False):
    """Update court status"""
    global COURT_STATUS
    
    COURT_STATUS.update({
        "status": status,
        "last_updated": datetime.now().isoformat(),
        "updated_by": updated_by,
        "manual_override": manual_override
    })
    
    logger.info(f"Court status updated to '{status}' by {updated_by}")

def update_weather_only(weather_data: dict):
    """Update only weather data without changing status timestamp"""
    global COURT_STATUS
    
    # Only update weather-related fields
    weather_fields = ["temperature", "precipitation", "conditions"]
    for field in weather_fields:
        if field in weather_data:
            COURT_STATUS[field] = weather_data[field]

# Flask routes
@app.route('/')
def index():
    """Serve the main HTML page"""
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    """Get current court status and update weather"""
    from flask import request
    
    # Update weather data using user's headers (without changing status timestamp)
    try:
        weather = get_weather_data(user_headers=request.headers)
        update_weather_only(weather)
    except Exception:
        # Continue without weather update if it fails
        pass
    
    return jsonify(COURT_STATUS)

@app.route('/api/status/<new_status>')
def set_status(new_status):
    """Set court status (for testing - in production, use POST with authentication)"""
    valid_statuses = ['open', 'closed', 'closed_until']
    if new_status in valid_statuses:
        update_status(new_status, "api", manual_override=True)
        return jsonify({"success": True, "status": COURT_STATUS})
    return jsonify({"error": "Invalid status"}), 400



telegram_application = None
telegram_handlers = None

def setup_telegram_bot():
    """Setup Telegram bot with new handlers"""
    global telegram_application, telegram_handlers
    
    if TELEGRAM_BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        logger.warning("Telegram bot token not configured. Bot will not start.")
        return None
    
    try:
        telegram_application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Create telegram handlers instance
        telegram_handlers = TelegramHandlers(
            court_status_dict=COURT_STATUS,
            update_status_func=update_status,
            authorized_users=AUTHORIZED_USERS
        )
        
        # Setup all handlers
        telegram_handlers.setup_handlers(telegram_application)
        
        logger.info("Telegram bot configured successfully with new handlers")
        return telegram_application
        
    except Exception as e:
        logger.error(f"Error setting up Telegram bot: {e}")
        return None

def run_telegram_bot():
    """Run Telegram bot in a separate thread using manual polling"""
    try:
        bot_app = setup_telegram_bot()
        if bot_app:
            logger.info("Starting Telegram bot polling...")
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def start_polling():
                """Start polling in async context"""
                await bot_app.initialize()
                await bot_app.start()
                await bot_app.updater.start_polling(allowed_updates=["message", "callback_query"])
                
                # Keep running until stopped
                try:
                    while True:
                        await asyncio.sleep(1)
                except asyncio.CancelledError:
                    pass
                finally:
                    await bot_app.updater.stop()
                    await bot_app.stop()
                    await bot_app.shutdown()
            
            loop.run_until_complete(start_polling())
    except Exception as e:
        logger.error(f"Error running Telegram bot: {e}")
    finally:
        if 'loop' in locals():
            loop.close()

# Automatic status updates (runs in background)

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Start background threads
    telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    telegram_thread.start()

    # Start Flask app using environment variables
    logger.info(f"Starting Flask application on {FLASK_HOST}:{FLASK_PORT}...")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, use_reloader=False)