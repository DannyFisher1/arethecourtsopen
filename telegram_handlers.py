#!/usr/bin/env python3
"""
Telegram Bot Handlers for Tennis Courts Management
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ConversationHandler, MessageHandler, filters, ContextTypes
)

logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_NOTES, WAITING_FOR_HOURS_CHANGE, WAITING_FOR_HOURS_TYPE = range(3)

class TelegramHandlers:
    def __init__(self, court_status_dict: Dict[str, Any], update_status_func, authorized_users: set):
        self.court_status = court_status_dict
        self.update_status = update_status_func
        self.authorized_users = authorized_users
        
        # Enhanced court status with new fields
        if 'notes' not in self.court_status:
            self.court_status['notes'] = ""
        if 'hours' not in self.court_status:
            self.court_status['hours'] = {"open": 6, "close": 20}
        if 'hours_override' not in self.court_status:
            self.court_status['hours_override'] = None
        if 'closed_until' not in self.court_status:
            self.court_status['closed_until'] = None

    def _check_authorization(self, user_id: int) -> bool:
        """Check if user is authorized"""
        return not self.authorized_users or user_id in self.authorized_users

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command for Telegram bot"""
        user_id = update.effective_user.id
        if not self._check_authorization(user_id):
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")
            return

        welcome_msg = """
🎾 *Tennis Courts Control Bot* 🎾

Available commands:
/status - Check current court status
/set_courts_open - Set courts as OPEN
/set_courts_closed - Set courts as CLOSED  
/set_courts_closed_until - Set courts closed until specific time
/change_hours - Change court operating hours
/clear_notes - Clear status notes

Current status: *{}*
Last updated: {}
        """.format(self.court_status['status'].upper(), self.court_status['last_updated'])

        await update.message.reply_text(welcome_msg, parse_mode='Markdown')

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get current status"""
        user_id = update.effective_user.id
        if not self._check_authorization(user_id):
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")
            return

        status_icons = {
            'open': '🟢',
            'closed': '🔴',
            'closed_until': '🟡',
        }

        icon = status_icons.get(self.court_status['status'], '❓')
        
        # Build status message
        status_msg = f"""
{icon} *Court Status: {self.court_status['status'].upper().replace('_', ' ')}*

🌡️ Temperature: {self.court_status['temperature']}°F
🌧️ Precipitation: {self.court_status['precipitation']}%
🎾 Conditions: {self.court_status['conditions']}

🕐 Hours: {self.court_status['hours']['open']}:00 - {self.court_status['hours']['close']}:00"""

        # Add closed until info if applicable
        if self.court_status['status'] == 'closed_until' and self.court_status.get('closed_until'):
            closed_until = datetime.fromisoformat(self.court_status['closed_until'])
            status_msg += f"\n⏰ Closed until: {closed_until.strftime('%Y-%m-%d %H:%M')}"

        # Add notes if present
        if self.court_status.get('notes'):
            status_msg += f"\n📝 Notes: {self.court_status['notes']}"

        # Add hours override info
        if self.court_status.get('hours_override'):
            override_date = self.court_status['hours_override']['date']
            override_hours = self.court_status['hours_override']['hours']
            status_msg += f"\n🔄 Today's hours override: {override_hours['open']}:00 - {override_hours['close']}:00"

        status_msg += f"""

📅 Last updated: {self.court_status['last_updated']}
👤 Updated by: {self.court_status['updated_by']}
🔧 Manual override: {'Yes' if self.court_status['manual_override'] else 'No'}
        """

        await update.message.reply_text(status_msg, parse_mode='Markdown')

    async def set_courts_open(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set courts as open with optional notes"""
        user_id = update.effective_user.id
        if not self._check_authorization(user_id):
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")
            return

        username = update.effective_user.username or f"user_{user_id}"
        
        # Clear closed_until if it was set
        self.court_status['closed_until'] = None
        self.update_status("open", f"telegram:{username}", manual_override=True)
        
        # Ask for notes
        keyboard = [
            [InlineKeyboardButton("Add Notes", callback_data='add_notes_open')],
            [InlineKeyboardButton("No Notes", callback_data='no_notes_open')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🟢 Courts set to OPEN\n\nWould you like to add any notes?",
            reply_markup=reply_markup
        )

    async def set_courts_closed(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set courts as closed with optional notes"""
        user_id = update.effective_user.id
        if not self._check_authorization(user_id):
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")
            return

        username = update.effective_user.username or f"user_{user_id}"
        
        # Clear closed_until if it was set
        self.court_status['closed_until'] = None
        self.update_status("closed", f"telegram:{username}", manual_override=True)
        
        # Ask for notes
        keyboard = [
            [InlineKeyboardButton("Add Notes", callback_data='add_notes_closed')],
            [InlineKeyboardButton("No Notes", callback_data='no_notes_closed')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔴 Courts set to CLOSED\n\nWould you like to add any notes?",
            reply_markup=reply_markup
        )

    async def set_courts_closed_until(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set courts closed until specific time"""
        user_id = update.effective_user.id
        if not self._check_authorization(user_id):
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")
            return

        # Pre-defined time options
        now = datetime.now()
        keyboard = [
            [InlineKeyboardButton("1 hour", callback_data=f'closed_until_{(now + timedelta(hours=1)).isoformat()}')],
            [InlineKeyboardButton("2 hours", callback_data=f'closed_until_{(now + timedelta(hours=2)).isoformat()}')],
            [InlineKeyboardButton("4 hours", callback_data=f'closed_until_{(now + timedelta(hours=4)).isoformat()}')],
            [InlineKeyboardButton("Until tomorrow 6 AM", callback_data=f'closed_until_{(now.replace(hour=6, minute=0, second=0) + timedelta(days=1)).isoformat()}')],
            [InlineKeyboardButton("Custom time", callback_data='closed_until_custom')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🟡 How long should the courts be closed?",
            reply_markup=reply_markup
        )

    async def change_hours(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Change court operating hours"""
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
            f"🕐 Current hours: {current_hours['open']}:00 - {current_hours['close']}:00\n\nHow would you like to change them?",
            reply_markup=reply_markup
        )

    async def clear_notes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clear status notes"""
        user_id = update.effective_user.id
        if not self._check_authorization(user_id):
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")
            return

        self.court_status['notes'] = ""
        self.court_status['last_updated'] = datetime.now().isoformat()
        
        await update.message.reply_text("🗑️ Status notes cleared")

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button presses"""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        if not self._check_authorization(user_id):
            await query.edit_message_text("Sorry, you're not authorized to use this bot.")
            return

        data = query.data

        if data.startswith('add_notes_'):
            # Store the status type for later use
            context.user_data['pending_notes_status'] = data.split('_')[2]
            await query.edit_message_text("📝 Please send your notes:")
            return WAITING_FOR_NOTES

        elif data.startswith('no_notes_'):
            self.court_status['notes'] = ""
            await query.edit_message_text("✅ Status updated without notes")
            return ConversationHandler.END

        elif data.startswith('closed_until_'):
            if data == 'closed_until_custom':
                await query.edit_message_text(
                    "📅 Please send the date and time when courts should reopen.\n"
                    "Format: YYYY-MM-DD HH:MM\n"
                    "Example: 2025-01-15 14:30"
                )
                return WAITING_FOR_HOURS_CHANGE
            else:
                # Extract datetime from callback data
                closed_until_str = data.replace('closed_until_', '')
                self.court_status['closed_until'] = closed_until_str
                
                username = query.from_user.username or f"user_{user_id}"
                self.update_status("closed_until", f"telegram:{username}", manual_override=True)
                
                closed_until = datetime.fromisoformat(closed_until_str)
                await query.edit_message_text(f"🟡 Courts set to CLOSED UNTIL {closed_until.strftime('%Y-%m-%d %H:%M')}")
                
                # Ask for notes
                keyboard = [
                    [InlineKeyboardButton("Add Notes", callback_data='add_notes_closed_until')],
                    [InlineKeyboardButton("No Notes", callback_data='no_notes_closed_until')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.message.reply_text("Would you like to add any notes?", reply_markup=reply_markup)

        elif data in ['hours_today', 'hours_permanent']:
            context.user_data['hours_type'] = data
            current_hours = self.court_status['hours']
            await query.edit_message_text(
                f"🕐 Current hours: {current_hours['open']}:00 - {current_hours['close']}:00\n\n"
                "Please send new hours in format: OPEN-CLOSE\n"
                "Example: 7-19 (for 7 AM to 7 PM)"
            )
            return WAITING_FOR_HOURS_CHANGE

        return ConversationHandler.END

    async def handle_notes_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle notes input from user"""
        notes = update.message.text
        self.court_status['notes'] = notes
        self.court_status['last_updated'] = datetime.now().isoformat()
        
        await update.message.reply_text(f"✅ Notes added: {notes}")
        return ConversationHandler.END

    async def handle_hours_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle hours change input"""
        text = update.message.text.strip()
        
        # Check if it's a closed_until datetime
        if 'hours_type' not in context.user_data:
            try:
                # Parse custom closed_until datetime
                closed_until = datetime.strptime(text, '%Y-%m-%d %H:%M')
                self.court_status['closed_until'] = closed_until.isoformat()
                
                username = update.effective_user.username or f"user_{update.effective_user.id}"
                self.update_status("closed_until", f"telegram:{username}", manual_override=True)
                
                await update.message.reply_text(f"🟡 Courts set to CLOSED UNTIL {closed_until.strftime('%Y-%m-%d %H:%M')}")
                
                # Ask for notes
                keyboard = [
                    [InlineKeyboardButton("Add Notes", callback_data='add_notes_closed_until')],
                    [InlineKeyboardButton("No Notes", callback_data='no_notes_closed_until')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text("Would you like to add any notes?", reply_markup=reply_markup)
                
            except ValueError:
                await update.message.reply_text(
                    "❌ Invalid format. Please use: YYYY-MM-DD HH:MM\n"
                    "Example: 2025-01-15 14:30"
                )
                return WAITING_FOR_HOURS_CHANGE
        else:
            # Handle hours change
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
                
                if hours_type == 'hours_permanent':
                    self.court_status['hours'] = {"open": open_hour, "close": close_hour}
                    await update.message.reply_text(f"✅ Hours permanently changed to {open_hour}:00 - {close_hour}:00")
                else:  # hours_today
                    today = datetime.now().strftime('%Y-%m-%d')
                    self.court_status['hours_override'] = {
                        "date": today,
                        "hours": {"open": open_hour, "close": close_hour}
                    }
                    await update.message.reply_text(f"✅ Hours changed for today only: {open_hour}:00 - {close_hour}:00")
                
                self.court_status['last_updated'] = datetime.now().isoformat()
                
            except ValueError as e:
                await update.message.reply_text(
                    f"❌ Invalid format. Please use: OPEN-CLOSE\n"
                    "Example: 7-19 (for 7 AM to 7 PM)\n"
                    "Hours must be 0-23 and opening must be before closing"
                )
                return WAITING_FOR_HOURS_CHANGE

        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current conversation"""
        await update.message.reply_text("❌ Operation cancelled")
        return ConversationHandler.END

    def get_conversation_handler(self):
        """Get the conversation handler for the bot"""
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
        """Setup all handlers for the application"""
        # Command handlers
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(CommandHandler("set_courts_open", self.set_courts_open))
        application.add_handler(CommandHandler("set_courts_closed", self.set_courts_closed))
        application.add_handler(CommandHandler("set_courts_closed_until", self.set_courts_closed_until))
        application.add_handler(CommandHandler("change_hours", self.change_hours))
        application.add_handler(CommandHandler("clear_notes", self.clear_notes))
        
        # Conversation handler for complex interactions
        application.add_handler(self.get_conversation_handler())
        
        # Standalone callback query handler for simple buttons
        application.add_handler(CallbackQueryHandler(self.button_handler))
        
        logger.info("All Telegram handlers configured successfully")