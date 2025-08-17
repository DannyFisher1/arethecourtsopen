#!/bin/bash

echo "🎾 Tennis Courts Status System Setup"
echo "==================================="
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not installed. Please install pip."
    exit 1
fi

echo "✅ pip3 found"

# Install requirements
echo "📦 Installing Python packages..."
pip3 install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Failed to install requirements. Please check your Python environment."
    exit 1
fi

echo "✅ Python packages installed successfully"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cat > .env << EOF
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
AUTHORIZED_USERS=123456789,987654321

# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True
EOF
    echo "✅ .env file created"
else
    echo "✅ .env file already exists"
fi

echo
echo "🚀 Setup Complete!"
echo
echo "Next steps:"
echo "1. Create a Telegram bot:"
echo "   - Message @BotFather on Telegram"
echo "   - Use /newbot to create a new bot"
echo "   - Copy the bot token"
echo
echo "2. Get your Telegram user ID:"
echo "   - Message @userinfobot on Telegram"
echo "   - Copy your user ID"
echo
echo "3. Edit the .env file and replace:"
echo "   - TELEGRAM_BOT_TOKEN with your actual bot token"
echo "   - AUTHORIZED_USERS with your user ID"
echo
echo "4. Start the application:"
echo "   python3 start.py"
echo
echo "The web interface will be available at: http://localhost:5000"
