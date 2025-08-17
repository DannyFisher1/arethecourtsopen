#!/usr/bin/env python3

from math import floor
import os
import asyncio
from datetime import datetime
from typing import Dict, Any
from flask import Flask, jsonify, render_template
from telegram.ext import Application
import threading
from dotenv import load_dotenv
import aiohttp
import weather_set
from telegram_handlers import TelegramHandlers

load_dotenv()

app = Flask(__name__)

DEFAULT_OPEN_HOUR = int(os.getenv('DEFAULT_OPEN_HOUR', '6'))
DEFAULT_CLOSE_HOUR = int(os.getenv('DEFAULT_CLOSE_HOUR', '20'))
WEATHER_LAT = float(os.getenv('WEATHER_LAT', '40.7128'))
WEATHER_LON = float(os.getenv('WEATHER_LON', '-74.0060'))
INITIAL_STATUS = os.getenv('INITIAL_STATUS', 'open')
INITIAL_CONDITIONS = os.getenv('INITIAL_CONDITIONS', 'Checking conditions...')

COURT_STATUS = {
    "status": INITIAL_STATUS,
    "temperature": 0,
    "precipitation": 0,
    "conditions": INITIAL_CONDITIONS,
    "last_updated": datetime.now().isoformat(),
    "updated_by": "system",
    "manual_override": False,
    "notes": "",
    "hours": {"open": DEFAULT_OPEN_HOUR, "close": DEFAULT_CLOSE_HOUR},
    "hours_override": None,
    "closed_until": None
}
CONDITIONS = weather_set.MET_WEATHER_CONDITIONS

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
AUTHORIZED_USERS = set(map(int, os.getenv('AUTHORIZED_USERS', '').split(',')) if os.getenv('AUTHORIZED_USERS') else [])
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))

async def get_met_weather(lat=None, lon=None, user_headers=None):
    lat = lat or WEATHER_LAT
    lon = lon or WEATHER_LON
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
        raise

def get_weather_data(user_headers=None):
    try:
        weather_data = asyncio.run(get_met_weather(user_headers=user_headers))
        return weather_data
    except Exception as e:
        return {
            "temperature": 0,
            "precipitation": 0,
            "conditions": "Weather unavailable"
        }

def update_status(status: str, updated_by: str = "system", manual_override: bool = False):
    global COURT_STATUS
    
    COURT_STATUS.update({
        "status": status,
        "last_updated": datetime.now().isoformat(),
        "updated_by": updated_by,
        "manual_override": manual_override
    })

def update_weather_only(weather_data: dict):
    global COURT_STATUS
    
    weather_fields = ["temperature", "precipitation", "conditions"]
    for field in weather_fields:
        if field in weather_data:
            COURT_STATUS[field] = weather_data[field]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    from flask import request
    
    try:
        weather = get_weather_data(user_headers=request.headers)
        update_weather_only(weather)
    except Exception:
        pass
    
    return jsonify(COURT_STATUS)

@app.route('/api/status/<new_status>')
def set_status(new_status):
    valid_statuses = ['open', 'closed', 'closed_until']
    if new_status in valid_statuses:
        update_status(new_status, "api", manual_override=True)
        return jsonify({"success": True, "status": COURT_STATUS})
    return jsonify({"error": "Invalid status"}), 400

telegram_application = None
telegram_handlers = None

def setup_telegram_bot():
    global telegram_application, telegram_handlers
    
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        return None
    
    try:
        telegram_application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        telegram_handlers = TelegramHandlers(
            court_status_dict=COURT_STATUS,
            update_status_func=update_status,
            authorized_users=AUTHORIZED_USERS
        )
        
        telegram_handlers.setup_handlers(telegram_application)
        
        return telegram_application
        
    except Exception as e:
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
        pass
    finally:
        if 'loop' in locals():
            loop.close()

if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    
    telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    telegram_thread.start()

    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, use_reloader=False)