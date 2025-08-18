#!/usr/bin/env python3

from math import floor
import os
import asyncio
from datetime import datetime
from typing import Dict, Any
from flask import Flask, jsonify, render_template, request
from telegram.ext import Application
import threading
from dotenv import load_dotenv
import aiohttp
import weather_set
from zoneinfo import ZoneInfo
from telegram_handlers import TelegramHandlers

load_dotenv()

app = Flask(__name__)

# --- Configuration and Initial State ---
DEFAULT_OPEN_HOUR = int(os.getenv('DEFAULT_OPEN_HOUR', '6'))
DEFAULT_CLOSE_HOUR = int(os.getenv('DEFAULT_CLOSE_HOUR', '20'))
WEATHER_LAT = float(os.getenv('WEATHER_LAT', '40.7128'))
WEATHER_LON = float(os.getenv('WEATHER_LON', '-74.0060'))
INITIAL_STATUS = os.getenv('INITIAL_STATUS', 'open')
INITIAL_CONDITIONS = os.getenv('INITIAL_CONDITIONS', 'Checking conditions...')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
AUTHORIZED_USERS = set(map(int, os.getenv('AUTHORIZED_USERS', '').split(',')) if os.getenv('AUTHORIZED_USERS') else [])
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))


TARGET_TZ = ZoneInfo("America/New_York")


# --- In-memory Application State ---
COURT_STATUS = {
    "status": INITIAL_STATUS,
    "temperature": 0,
    "precipitation": 0,
    "conditions": INITIAL_CONDITIONS,
    "last_updated": datetime.now(TARGET_TZ).isoformat(),
    "updated_by": "system",
    "manual_override": False,
    "notes": "",
    "hours": {"open": DEFAULT_OPEN_HOUR, "close": DEFAULT_CLOSE_HOUR},
    "hours_override": None,
    "check_back_at": None
}
CONDITIONS = weather_set.MET_WEATHER_CONDITIONS

telegram_application = None
telegram_handlers = None

# --- Core Functions ---
async def get_met_weather(lat=None, lon=None):
    lat = lat or WEATHER_LAT
    lon = lon or WEATHER_LON
    url = f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={lat}&lon={lon}"
    try:
        async with aiohttp.ClientSession() as session:
            # Note: Production servers may require specific headers, e.g., a User-Agent.
            # For met.no, a User-Agent is good practice.
            headers = {'User-Agent': 'CourtStatusApp/1.0 yourdomain.com'}
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    print(f"Weather API returned status {resp.status}") # Added logging
                    return None
                
                data = await resp.json()
                current = data["properties"]["timeseries"][0]
                
                weather_data = {
                    "temperature": floor((current["data"]["instant"]["details"]["air_temperature"])*1.8+32),
                    "precipitation": current["data"].get("next_1_hours", {}).get("details", {}).get("precipitation_amount", 0),
                    "conditions": CONDITIONS.get(current["data"].get("next_1_hours", {}).get("summary", {}).get("symbol_code", "unknown"), "unknown")
                }
                
                return weather_data
                
    except Exception as e:
        print(f"Error fetching weather: {e}") # Added logging
        return None

def get_weather_data():
    try:
        weather_data = asyncio.run(get_met_weather())
        if weather_data:
            return weather_data
    except Exception as e:
        print(f"Error in get_weather_data: {e}") # Added logging

    # Return a default error state if fetching fails
    return {
        "temperature": "N/A",
        "precipitation": "N/A",
        "conditions": "Weather unavailable"
    }

def update_status(status: str, updated_by: str = "system", manual_override: bool = False):
    global COURT_STATUS
    
    COURT_STATUS.update({
        "status": status,
        "last_updated": datetime.now(TARGET_TZ).isoformat(),
        "updated_by": updated_by,
        "manual_override": manual_override
    })

def update_weather_only(weather_data: dict):
    global COURT_STATUS
    
    weather_fields = ["temperature", "precipitation", "conditions"]
    for field in weather_fields:
        if field in weather_data:
            COURT_STATUS[field] = weather_data[field]

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    weather = get_weather_data()
    update_weather_only(weather)
    return jsonify(COURT_STATUS)

@app.route('/api/status/<new_status>')
def set_status(new_status):
    valid_statuses = ['open', 'closed']
    if new_status in valid_statuses:
        update_status(new_status, "api", manual_override=True)
        return jsonify({"success": True, "status": COURT_STATUS})
    return jsonify({"error": "Invalid status"}), 400

# --- Telegram Bot Setup and Logic ---
def setup_telegram_bot():
    global telegram_application, telegram_handlers
    
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        print("Telegram bot token not found. Bot will not start.")
        return None
    
    try:
        telegram_application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        telegram_handlers = TelegramHandlers(
            court_status_dict=COURT_STATUS,
            update_status_func=update_status,
            authorized_users=AUTHORIZED_USERS
        )
        
        telegram_handlers.setup_handlers(telegram_application)
        
        print("Telegram bot setup complete.")
        return telegram_application
        
    except Exception as e:
        print(f"Failed to set up Telegram bot: {e}")
        return None

def run_telegram_bot():
    try:
        bot_app = setup_telegram_bot()
        if bot_app:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def start_polling():
                await bot_app.initialize()
                await bot_app.start()
                await bot_app.updater.start_polling(allowed_updates=["message", "callback_query"])
                print("Telegram bot is running...")
                
                # Keep the event loop running
                while True:
                    await asyncio.sleep(3600) # Sleep for a long time
            
            loop.run_until_complete(start_polling())
    except Exception as e:
        print(f"An error occurred in the Telegram bot thread: {e}")
    finally:
        if 'loop' in locals():
            loop.close()

# --- Application Entry Point ---

print("Starting Telegram bot in a background thread...")
telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
telegram_thread.start()

if __name__ == '__main__':
    print("Running Flask development server...")
    # Make sure the templates directory exists for local development
    os.makedirs('templates', exist_ok=True)

    # Note: We do not start the thread here again because it's already started above.
    # The Flask development server is for testing the web interface locally.
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, use_reloader=False)