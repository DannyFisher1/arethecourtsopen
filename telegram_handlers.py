#!/usr/bin/env python3

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ConversationHandler, MessageHandler, filters, ContextTypes
)

WAITING_FOR_NOTES, WAITING_FOR_HOURS_CHANGE, WAITING_FOR_HOURS_TYPE = range(3)

TARGET_TZ = ZoneInfo("America/New_York")

class TelegramHandlers:
    def __init__(self, court_status_dict: Dict[str, Any], update_status_func, authorized_users: set):
        self.court_status = court_status_dict
        self.update_status = update_status_func
        self.authorized_users = authorized_users
        
        if 'notes' not in self.court_status:
            self.court_status['notes'] = ""
        if 'hours' not in self.court_status:
            self.court_status['hours'] = {"open": 6, "close": 20}
        if 'hours_override' not in self.court_status:
            self.court_status['hours_override'] = None

    def _check_authorization(self, user_id: int) -> bool:
        return not self.authorized_users or user_id in self.authorized_users

    def _format_time_12h(self, hour: int) -> str:
        if hour == 0:
            return "12:00 AM"
        elif hour < 12:
            return f"{hour}:00 AM"
        elif hour == 12:
            return "12:00 PM"
        else:
            return f"{hour - 12}:00 PM"

    def _format_timestamp(self, iso_timestamp: str) -> str:
        """Format ISO timestamp to 'August 18th, 2025 11:53:04AM' format"""
        try:
            dt = datetime.fromisoformat(iso_timestamp)
            
            months = ['January', 'February', 'March', 'April', 'May', 'June',
                     'July', 'August', 'September', 'October', 'November', 'December']
            
            day = dt.day
            suffix = 'st' if day % 10 == 1 and day != 11 else \
                    'nd' if day % 10 == 2 and day != 12 else \
                    'rd' if day % 10 == 3 and day != 13 else 'th'
            
            month = months[dt.month - 1]
            year = dt.year
            hours = dt.hour
            minutes = f"{dt.minute:02d}"
            seconds = f"{dt.second:02d}"
            ampm = 'PM' if hours >= 12 else 'AM'
            display_hours = hours % 12 or 12
            
            return f"{month} {day}{suffix}, {year} {display_hours}:{minutes}:{seconds}{ampm}"
        except:
            return iso_timestamp  # fallback to original if parsing fails

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self._check_authorization(user_id):
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")
            return

        welcome_msg = f"""🎾 *Tennis Courts Control Bot* 🎾

Available commands:
/status - Check current court status  
/open - Set courts as OPEN  
/closed - Set courts as CLOSED  
/change_hours - Change court operating hours  
/clear_notes - Clear status notes

Current status: *{self.court_status['status'].upper()}*  
Last updated: {self._format_timestamp(self.court_status['last_updated'])}
"""

        keyboard = [
            [InlineKeyboardButton("📊 Check Status", callback_data='check_status')],
            [InlineKeyboardButton("🟢 Set Open", callback_data='set_open'), InlineKeyboardButton("🔴 Set Closed", callback_data='set_closed')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_msg, reply_markup=reply_markup)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self._check_authorization(user_id):
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")
            return

        status_icons = {
            'open': '🟢',
            'closed': '🔴',
        }

        icon = status_icons.get(self.court_status['status'], '❓')
        
        status_msg = f"""
{icon} *Court Status: {self.court_status['status'].upper().replace('_', ' ')}*

🌡️ Temperature: {self.court_status['temperature']}°F
🌧️ Precipitation: {self.court_status['precipitation']}%
🎾 Conditions: {self.court_status['conditions']}

🕐 Hours: {self._format_time_12h(self.court_status['hours']['open'])} - {self._format_time_12h(self.court_status['hours']['close'])}"""

        if self.court_status.get('notes'):
            status_msg += f"\n📝 Notes: {self.court_status['notes']}"

        if self.court_status.get('hours_override'):
            override_date = self.court_status['hours_override']['date']
            override_hours = self.court_status['hours_override']['hours']
            status_msg += f"\n🔄 Today's hours override: {self._format_time_12h(override_hours['open'])} - {self._format_time_12h(override_hours['close'])}"

        status_msg += f"""

📅 Last updated: {self._format_timestamp(self.court_status['last_updated'])}
👤 Updated by: {self.court_status['updated_by']}
🔧 Manual override: {'Yes' if self.court_status['manual_override'] else 'No'}
        """

        keyboard = [
            [InlineKeyboardButton("🔄 Refresh Status", callback_data='check_status')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(status_msg, parse_mode='Markdown', reply_markup=reply_markup)

    async def open(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self._check_authorization(user_id):
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")
            return

        username = update.effective_user.username or f"user_{user_id}"
        

        self.update_status("open", f"telegram:{username}", manual_override=True)
        
        keyboard = [
            [InlineKeyboardButton("Add Notes", callback_data='add_notes_open')],
            [InlineKeyboardButton("No Notes", callback_data='no_notes_open')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🟢 Courts set to OPEN\n\nWould you like to add any notes?",
            reply_markup=reply_markup
        )

    async def closed(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self._check_authorization(user_id):
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")
            return

        username = update.effective_user.username or f"user_{user_id}"
        

        self.update_status("closed", f"telegram:{username}", manual_override=True)
        
        keyboard = [
            [InlineKeyboardButton("Add Notes", callback_data='add_notes_closed')],
            [InlineKeyboardButton("No Notes", callback_data='no_notes_closed')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔴 Courts set to CLOSED\n\nWould you like to add any notes?",
            reply_markup=reply_markup
        )

    async def change_hours(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self._check_authorization(user_id):
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")
            return

        keyboard = [
            [InlineKeyboardButton("Change for today only", callback_data='hours_today')],
            [InlineKeyboardButton("Change permanently", callback_data='hours_permanent')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        current_hours = self.court_status['hours']
        await update.message.reply_text(
            f"🕐 Current hours: {self._format_time_12h(current_hours['open'])} - {self._format_time_12h(current_hours['close'])}\n\nHow would you like to change them?",
            reply_markup=reply_markup
        )

    async def clear_notes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self._check_authorization(user_id):
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")
            return

        username = update.effective_user.username or f"user_{user_id}"
        
        self.court_status['notes'] = ""
        self.court_status['last_updated'] = datetime.now(TARGET_TZ).isoformat()
        self.court_status['updated_by'] = f"telegram:{username}"
        
        await update.message.reply_text("🗑️ Status notes cleared")

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        if not self._check_authorization(user_id):
            await query.edit_message_text("Sorry, you're not authorized to use this bot.")
            return

        data = query.data

        if data.startswith('add_notes_'):
            context.user_data['pending_notes_status'] = data.split('_')[2]
            await query.edit_message_text("📝 Please send your notes:")
            return WAITING_FOR_NOTES

        elif data.startswith('no_notes_'):
            self.court_status['notes'] = ""
            await query.edit_message_text("✅ Status updated without notes")
            return ConversationHandler.END

        elif data == 'check_status':
            await self.status_command(query, context)
            return ConversationHandler.END

        elif data == 'set_open':
            await self.open(query, context)
            return ConversationHandler.END

        elif data == 'set_closed':
            await self.closed(query, context)
            return ConversationHandler.END

        elif data in ['hours_today', 'hours_permanent']:
            context.user_data['hours_type'] = data
            current_hours = self.court_status['hours']
            await query.edit_message_text(
                f"🕐 Current hours: {self._format_time_12h(current_hours['open'])} - {self._format_time_12h(current_hours['close'])}\n\n"
                "Please send new hours in format: OPEN-CLOSE\n"
                "Example: 7-19 (for 7 AM to 7 PM)"
            )
            return WAITING_FOR_HOURS_CHANGE

        return ConversationHandler.END

    async def handle_notes_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        notes = update.message.text
        username = update.effective_user.username or f"user_{update.effective_user.id}"
        
        self.court_status['notes'] = notes
        self.court_status['last_updated'] = datetime.now(TARGET_TZ).isoformat()
        self.court_status['updated_by'] = f"telegram:{username}"
        
        await update.message.reply_text(f"✅ Notes added: {notes}")
        return ConversationHandler.END

    async def handle_hours_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        
        try:
            if '-' not in text:
                raise ValueError("Missing dash separator")
                
            open_hour, close_hour = text.split('-')
            open_hour = int(open_hour.strip())
            close_hour = int(close_hour.strip())
            
            if not (0 <= open_hour <= 23) or not (0 <= close_hour <= 23):
                raise ValueError("Hours must be between 0-23")
                
            if open_hour >= close_hour:
                raise ValueError("Opening hour must be before closing hour")
            
            hours_type = context.user_data['hours_type']
            
            username = update.effective_user.username or f"user_{update.effective_user.id}"
            
            if hours_type == 'hours_permanent':
                self.court_status['hours'] = {"open": open_hour, "close": close_hour}
                await update.message.reply_text(f"✅ Hours permanently changed to {self._format_time_12h(open_hour)} - {self._format_time_12h(close_hour)}")
            else:
                today = datetime.now(TARGET_TZ).strftime('%Y-%m-%d')
                self.court_status['hours_override'] = {
                    "date": today,
                    "hours": {"open": open_hour, "close": close_hour}
                }
                await update.message.reply_text(f"✅ Hours changed for today only: {self._format_time_12h(open_hour)} - {self._format_time_12h(close_hour)}")
            
            self.court_status['last_updated'] = datetime.now(TARGET_TZ).isoformat()
            self.court_status['updated_by'] = f"telegram:{username}"
            
        except ValueError as e:
            await update.message.reply_text(
                f"❌ Invalid format. Please use: OPEN-CLOSE\n"
                "Example: 7-19 (for 7 AM to 7 PM)\n"
                "Hours must be 0-23 and opening must be before closing"
            )
            return WAITING_FOR_HOURS_CHANGE

        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("❌ Operation cancelled")
        return ConversationHandler.END

    def get_conversation_handler(self):
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.button_handler),
                CommandHandler('cancel', self.cancel)
            ],
            states={
                WAITING_FOR_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_notes_input)],
                WAITING_FOR_HOURS_CHANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_hours_input)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )

    def setup_handlers(self, application: Application):
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(CommandHandler("open", self.open))
        application.add_handler(CommandHandler("closed", self.closed))

        application.add_handler(CommandHandler("change_hours", self.change_hours))
        application.add_handler(CommandHandler("clear_notes", self.clear_notes))
        
        application.add_handler(self.get_conversation_handler())
        application.add_handler(CallbackQueryHandler(self.button_handler))