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
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import threading
import time
from dotenv import load_dotenv
import aiohttp
import asyncio
import weather_set

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

# Court status storage (in production, use a database)
COURT_STATUS = {
    "status": "open",  # open, closed
    "temperature": 0,
    "precipitation": 0,
    "conditions": "Checking conditions...",
    "last_updated": datetime.now().isoformat(),
    "updated_by": "system",
    "manual_override": False
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
DEFAULT_OPEN_HOUR = int(os.getenv('DEFAULT_OPEN_HOUR', 6))
DEFAULT_CLOSE_HOUR = int(os.getenv('DEFAULT_CLOSE_HOUR', 20))




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

# Flask routes
@app.route('/')
def index():
    """Serve the main HTML page"""
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    """Get current court status and update weather"""
    from flask import request
    
    # Update weather data using user's headers
    try:
        weather = get_weather_data(user_headers=request.headers)
        COURT_STATUS.update(weather)
    except Exception:
        # Continue without weather update if it fails
        pass
    
    return jsonify(COURT_STATUS)

@app.route('/api/status/<new_status>')
def set_status(new_status):
    """Set court status (for testing - in production, use POST with authentication)"""
    valid_statuses = ['open', 'closed']
    if new_status in valid_statuses:
        update_status(new_status, "api", manual_override=True)
        return jsonify({"success": True, "status": COURT_STATUS})
    return jsonify({"error": "Invalid status"}), 400



# ... (REST OF TELEGRAM BOT COMMANDS - NO CHANGES)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command for Telegram bot"""
    user_id = update.effective_user.id
    if AUTHORIZED_USERS and user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Sorry, you're not authorized to use this bot.")
        return
    
    welcome_msg = """
🎾 *Tennis Courts Control Bot* 🎾

Available commands:
/status - Check current court status
/open - Set courts as OPEN
/closed - Set courts as CLOSED

Current status: *{}*
Last updated: {}
    """.format(COURT_STATUS['status'].upper(), COURT_STATUS['last_updated'])
    
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get current status"""
    user_id = update.effective_user.id
    if AUTHORIZED_USERS and user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Sorry, you're not authorized to use this bot.")
        return
    
    status_icons = {
        'open': '🟢',
        'closed': '🔴',
    }
    
    icon = status_icons.get(COURT_STATUS['status'], '❓')
    
    status_msg = f"""
{icon} *Court Status: {COURT_STATUS['status'].upper().replace('_', ' ')}*

🌡️ Temperature: {COURT_STATUS['temperature']}°F
🌧️ Precipitation: {COURT_STATUS['precipitation']}%
🎾 Conditions: {COURT_STATUS['conditions']}

📅 Last updated: {COURT_STATUS['last_updated']}
👤 Updated by: {COURT_STATUS['updated_by']}
🔧 Manual override: {'Yes' if COURT_STATUS['manual_override'] else 'No'}
    """
    
    await update.message.reply_text(status_msg, parse_mode='Markdown')

async def set_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set courts as open"""
    user_id = update.effective_user.id
    if AUTHORIZED_USERS and user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Sorry, you're not authorized to use this bot.")
        return
    
    username = update.effective_user.username or f"user_{user_id}"
    update_status("open", f"telegram:{username}", manual_override=True)
    await update.message.reply_text("🟢 Courts set to OPEN")

async def set_closed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set courts as closed"""
    user_id = update.effective_user.id
    if AUTHORIZED_USERS and user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Sorry, you're not authorized to use this bot.")
        return
    
    username = update.effective_user.username or f"user_{user_id}"
    update_status("closed", f"telegram:{username}", manual_override=True)
    await update.message.reply_text("🔴 Courts set to CLOSED")

telegram_application = None

def setup_telegram_bot():
    """Setup Telegram bot (synchronous version)"""
    global telegram_application
    
    if TELEGRAM_BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        logger.warning("Telegram bot token not configured. Bot will not start.")
        return None
    
    try:
        telegram_application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Add command handlers
        telegram_application.add_handler(CommandHandler("start", start))
        telegram_application.add_handler(CommandHandler("status", status_command))
        telegram_application.add_handler(CommandHandler("open", set_open))
        telegram_application.add_handler(CommandHandler("closed", set_closed))
        
        logger.info("Telegram bot configured successfully")
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