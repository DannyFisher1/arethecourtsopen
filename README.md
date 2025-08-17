# Tennis Courts Status System

A web application and Telegram bot system to monitor and control the status of tennis courts in Central Park.

## Features

- **Web Interface**: Real-time display of court status with weather information
- **Telegram Bot Control**: Remote control of court status via Telegram commands
- **Multiple Status Types**: 
  - Open/Closed
  - Critically Open/Critically Closed (for emergency situations)
- **Automatic Updates**: Weather-based automatic status updates
- **Manual Override**: Admin control via Telegram bot

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Create Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Create a new bot with `/newbot`
3. Copy the bot token

### 3. Configure Environment

1. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

2. Edit `.env` and add your configuration:
```env
TELEGRAM_BOT_TOKEN=your_actual_bot_token_here
AUTHORIZED_USERS=your_telegram_user_id,another_user_id
```

### 4. Get Your Telegram User ID

1. Message [@userinfobot](https://t.me/userinfobot) to get your user ID
2. Add your user ID to the `AUTHORIZED_USERS` in `.env`

### 5. Run the Application

```bash
python app.py
```

The web interface will be available at: http://localhost:5000

## Telegram Bot Commands

- `/start` - Get welcome message and available commands
- `/status` - Check current court status
- `/open` - Set courts as OPEN
- `/closed` - Set courts as CLOSED
- `/critical_open` - Set courts as CRITICALLY OPEN (emergency access)
- `/critical_closed` - Set courts as CRITICALLY CLOSED (emergency closure)
- `/auto` - Enable automatic status based on weather and time

## API Endpoints

- `GET /` - Web interface
- `GET /api/status` - Get current status (JSON)
- `GET /api/status/<status>` - Set status (for testing)

## Status Types

1. **Open** 🟢 - Courts are available for normal play
2. **Closed** 🔴 - Courts are not available (weather, maintenance, hours)
3. **Critically Open** 🟡 - Courts available for emergency/priority access only
4. **Critically Closed** ⚫ - Courts closed due to emergency conditions

## Automatic Status Logic

The system automatically updates status based on:
- **Time**: Courts closed outside 6 AM - 8 PM
- **Weather**: Closed if precipitation > 50% or temperature < 35°F or > 95°F
- **Manual Override**: Admin can override automatic status via Telegram

## Security

- Only authorized Telegram users can control the system
- User IDs must be configured in environment variables
- Bot token should be kept secure

## Development

To run in development mode:

```bash
export FLASK_ENV=development
export FLASK_DEBUG=True
python app.py
```

## Production Deployment

For production deployment:

1. Use a production WSGI server (gunicorn, uwsgi)
2. Set up proper environment variables
3. Use a real database instead of in-memory storage
4. Set up proper logging and monitoring
5. Use HTTPS for the web interface

Example with gunicorn:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```
# arethecourtsopen
