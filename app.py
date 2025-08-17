#!/usr/bin/env python3
"""
Tennis Courts Status API with Telegram Bot Control
"""

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
    "status": "open",  # open, closed, critically_open, critically_closed
    "temperature": 72,
    "precipitation": 0,
    "conditions": "Courts available for tennis",
    "last_updated": datetime.now().isoformat(),
    "updated_by": "system",
    "manual_override": False
}

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
AUTHORIZED_USERS = set(map(int, os.getenv('AUTHORIZED_USERS', '').split(',')) if os.getenv('AUTHORIZED_USERS') else [])

# Weather simulation (replace with real weather API in production)
def get_weather_data():
    """Simulate weather data - replace with real API call"""
    import random
    return {
        "temperature": random.randint(45, 85),
        "precipitation": random.randint(0, 20) if random.random() > 0.7 else 0,
        "conditions": "Good for tennis" if random.random() > 0.3 else "Weather may affect play"
    }

def update_status(status: str, updated_by: str = "system", manual_override: bool = False):
    """Update court status"""
    global COURT_STATUS
    
    # Get current weather if not manually overridden
    if not manual_override:
        weather = get_weather_data()
        COURT_STATUS.update(weather)
    
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
    """Get current court status"""
    return jsonify(COURT_STATUS)

@app.route('/api/status/<new_status>')
def set_status(new_status):
    """Set court status (for testing - in production, use POST with authentication)"""
    valid_statuses = ['open', 'closed', 'critically_open', 'critically_closed']
    if new_status in valid_statuses:
        update_status(new_status, "api", manual_override=True)
        return jsonify({"success": True, "status": COURT_STATUS})
    return jsonify({"error": "Invalid status"}), 400

# Telegram Bot Commands
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
/critical_open - Set courts as CRITICALLY OPEN (emergency access)
/critical_closed - Set courts as CRITICALLY CLOSED (emergency closure)
/auto - Enable automatic status (weather-based)

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
        'critically_open': '🟡',
        'critically_closed': '⚫'
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

async def set_critical_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set courts as critically open"""
    user_id = update.effective_user.id
    if AUTHORIZED_USERS and user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Sorry, you're not authorized to use this bot.")
        return
    
    username = update.effective_user.username or f"user_{user_id}"
    update_status("critically_open", f"telegram:{username}", manual_override=True)
    await update.message.reply_text("🟡 Courts set to CRITICALLY OPEN (Emergency Access)")

async def set_critical_closed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set courts as critically closed"""
    user_id = update.effective_user.id
    if AUTHORIZED_USERS and user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Sorry, you're not authorized to use this bot.")
        return
    
    username = update.effective_user.username or f"user_{user_id}"
    update_status("critically_closed", f"telegram:{username}", manual_override=True)
    await update.message.reply_text("⚫ Courts set to CRITICALLY CLOSED (Emergency Closure)")

async def set_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enable automatic status updates"""
    user_id = update.effective_user.id
    if AUTHORIZED_USERS and user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Sorry, you're not authorized to use this bot.")
        return
    
    username = update.effective_user.username or f"user_{user_id}"
    # Reset to automatic mode - determine status based on weather and time
    now = datetime.now()
    is_open_hours = 6 <= now.hour < 20  # 6 AM to 8 PM
    weather = get_weather_data()
    
    auto_status = "open" if is_open_hours and weather["precipitation"] < 30 else "closed"
    update_status(auto_status, f"telegram:{username}", manual_override=False)
    
    await update.message.reply_text(f"🔄 Automatic mode enabled. Status set to: {auto_status.upper()}")

# Global application instance
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
        telegram_application.add_handler(CommandHandler("critical_open", set_critical_open))
        telegram_application.add_handler(CommandHandler("critical_closed", set_critical_closed))
        telegram_application.add_handler(CommandHandler("auto", set_auto))
        
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
def auto_status_updater():
    """Update status automatically based on time and weather"""
    while True:
        try:
            if not COURT_STATUS.get('manual_override', False):
                now = datetime.now()
                is_open_hours = 6 <= now.hour < 20  # 6 AM to 8 PM
                weather = get_weather_data()
                
                # Determine status based on conditions
                if not is_open_hours:
                    auto_status = "closed"
                elif weather["precipitation"] > 50:
                    auto_status = "closed"
                elif weather["temperature"] < 35 or weather["temperature"] > 95:
                    auto_status = "closed"
                else:
                    auto_status = "open"
                
                if COURT_STATUS["status"] != auto_status:
                    update_status(auto_status, "auto-updater", manual_override=False)
            
            time.sleep(300)  # Check every 5 minutes
        except Exception as e:
            logger.error(f"Error in auto status updater: {e}")
            time.sleep(60)  # Wait 1 minute before retrying

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Start background threads
    telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    telegram_thread.start()
    
    auto_updater_thread = threading.Thread(target=auto_status_updater, daemon=True)
    auto_updater_thread.start()
    
    # Start Flask app
    logger.info("Starting Flask application...")
    app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)
