#!/usr/bin/env python3
"""
Startup script for Tennis Courts Status System
"""

import os
import sys
from dotenv import load_dotenv

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Check if required environment variables are set
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token or bot_token == 'your_bot_token_here':
        print("⚠️  WARNING: TELEGRAM_BOT_TOKEN not configured!")
        print("   The Telegram bot will not work until you:")
        print("   1. Create a bot with @BotFather on Telegram")
        print("   2. Copy the bot token to your .env file")
        print("   3. Add your Telegram user ID to AUTHORIZED_USERS")
        print()
    
    authorized_users = os.getenv('AUTHORIZED_USERS', '')
    if not authorized_users or '123456789' in authorized_users:
        print("⚠️  WARNING: AUTHORIZED_USERS not configured properly!")
        print("   Add your Telegram user ID to the .env file")
        print("   Get your ID by messaging @userinfobot on Telegram")
        print()
    
    print("🎾 Starting Tennis Courts Status System...")
    print("   Web interface: http://localhost:5001")
    print("   API endpoint: http://localhost:5001/api/status")
    print()
    
    # Import and run the main app
    try:
        import app
        # The app.py file will handle its own execution
        exec(open('app.py').read())
    except ImportError as e:
        print(f"❌ Error importing app: {e}")
        print("   Make sure you've installed the requirements:")
        print("   pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
