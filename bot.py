import os
import asyncio
import requests
import schedule
import time
import threading
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import logging
from flask import Flask
from models import db, User, SupportMessage, SupportResponse, ScheduleSlot, Notification, TelegramGroup
from ai_support import ai_support
from conversation_manager import ConversationManager
from private_support_groups import PrivateSupportGroupManager

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get configuration from environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
SUPPORT_GROUP_ID = os.getenv('SUPPORT_GROUP_ID')
FORWARD_SUPPORT_TO_GROUP = os.getenv('FORWARD_SUPPORT_TO_GROUP', 'false').strip().lower() in ('1', 'true', 'yes', 'y')
WEB_DASHBOARD_URL = os.getenv('WEB_DASHBOARD_URL', 'http://localhost:5001')
ESCALATION_TIMEOUT = int(os.getenv('ESCALATION_TIMEOUT', '900'))  # 15 minutes default

# Global variables for tracking
pending_escalations = {}
app_instance = None
flask_app = None
conversation_manager = None

# Initialize Flask app for bot database access
def init_flask_app():
    """Initialize Flask app for bot database access"""
    global flask_app
    if flask_app is None:
        flask_app = Flask(__name__)
        flask_app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///instance/support_system.db')
        flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        flask_app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
        
        db.init_app(flask_app)
        
        with flask_app.app_context():
            db.create_all()
    
    return flask_app

def get_active_support_group_ids():
    """Fetch active Telegram group IDs from the database"""
    ids = []
    try:
        with flask_app.app_context():
            groups = TelegramGroup.query.filter_by(is_active=True).all()
            ids = [str(g.telegram_group_id) for g in groups if g.telegram_group_id]
    except Exception as e:
        logger.error(f"Failed to load Telegram groups: {e}")
    return ids

def resolve_target_group_ids():
    """Return list of group IDs to notify. Prefer DB-configured active groups; fallback to SUPPORT_GROUP_ID env."""
    ids = get_active_support_group_ids()
    if ids:
        return ids
    if SUPPORT_GROUP_ID:
        return [str(SUPPORT_GROUP_ID)]
    return []

# Define command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    welcome_message = (
        f"Hi {user.first_name}! I'm your advanced support bot with on-call scheduling! 🚀\n\n"
        f"📞 **To send a support request:**\n"
        f"Type: `@support` followed by your message\n"
        f"Example: `@support I need help with my account`\n\n"
        f"🔧 **Features:**\n"
        f"• Automatic on-call tech notification\n"
        f"• Smart escalation system\n"
        f"• Web dashboard integration\n"
        f"• Real-time response tracking\n\n"
        f"💻 **Web Dashboard:** {WEB_DASHBOARD_URL}\n"
        f"Tech team can login to manage and respond to requests!"
    )
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        "🤖 **Support Bot Help**\n\n"
        "**Commands:**\n"
        "/start - Welcome message and bot info\n"
        "/help - Show this help message\n"
        "/status - Check system status\n\n"
        "**Support Requests:**\n"
        "Type `@support` followed by your message\n"
        "Example: `@support My payment failed`\n\n"
        "**How it works:**\n"
        "1. Your request is logged in our system\n"
        "2. Current on-call tech is notified immediately\n"
        "3. If no response in 15 minutes, backup tech is notified\n"
        "4. Process continues until someone responds\n\n"
        f"**Web Dashboard:** {WEB_DASHBOARD_URL}\n"
        "Tech team can view and respond to all requests online!"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show system status and current on-call information."""
    try:
        # Get current on-call info from web dashboard
        response = requests.get(f"{WEB_DASHBOARD_URL}/api/current_oncall", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('on_call_user'):
                on_call = data['on_call_user']
                status_message = (
                    f"🟢 **System Status: ONLINE**\n\n"
                    f"👨‍💻 **Current On-Call:**\n"
                    f"Name: {on_call['first_name']} {on_call['last_name']}\n"
                    f"Email: {on_call['email']}\n\n"
                    f"📊 **Statistics:**\n"
                    f"Open Messages: {data.get('open_messages', 0)}\n"
                    f"In Progress: {data.get('in_progress_messages', 0)}\n"
                    f"Resolved Today: {data.get('resolved_today', 0)}\n\n"
                    f"🌐 **Dashboard:** {WEB_DASHBOARD_URL}"
                )
            else:
                status_message = (
                    f"🟡 **System Status: ONLINE**\n\n"
                    f"⚠️ **No one currently on-call**\n"
                    f"Support requests will be logged but may not be immediately addressed.\n\n"
                    f"🌐 **Dashboard:** {WEB_DASHBOARD_URL}"
                )
        else:
            status_message = (
                f"🟡 **System Status: PARTIAL**\n\n"
                f"Bot is running but web dashboard is not responding.\n"
                f"Support requests will still be forwarded to the group.\n\n"
                f"🌐 **Dashboard:** {WEB_DASHBOARD_URL}"
            )
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        status_message = (
            f"🟡 **System Status: LIMITED**\n\n"
            f"Bot is running but cannot connect to web dashboard.\n"
            f"Error: {str(e)[:100]}..."
        )
    
    await update.message.reply_text(status_message, parse_mode='Markdown')


async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all messages - check for replies first, then @support messages"""
    print(f"DEBUG: Received message update: {update}")
    
    if not update.message:
        print("DEBUG: No message in update")
        return
        
    if not update.message.text:
        print(f"DEBUG: Message has no text: {update.message}")
        return
    
    message_text = update.message.text.strip()
    username = update.effective_user.username or update.effective_user.first_name or "Unknown"
    user_telegram_id = str(update.effective_user.id)
    
    print(f"DEBUG: Processing message from {username}: '{message_text}'")
    print(f"DEBUG: SUPPORT_GROUP_ID: {SUPPORT_GROUP_ID}")
    print(f"DEBUG: Chat type: {update.effective_chat.type}")
    
    # Handle commands
    if message_text.startswith('/'):
        print(f"DEBUG: Skipping other command message: {message_text}")
        return
    
    # Check if this is a private chat message (direct message to bot)
    if update.effective_chat.type == 'private':
        print(f"DEBUG: Processing private chat message from user {username}")
        await handle_private_chat_message(update, context)
        return
    
    # Check if user has an active conversation (reply detection in group)
    reply_info = conversation_manager.handle_user_reply(
        user_telegram_id, username, message_text, update.message.message_id
    )
    
    if reply_info['is_reply']:
        # This is a reply in an active conversation
        await handle_conversation_reply(update, context, reply_info)
        return
    
    # Check if message starts with @support (new support request)
    if message_text.lower().startswith('@support'):
        await handle_support_message(update, context)
        return
    
    # For any other message, do nothing (silent operation)
    print(f"DEBUG: Ignoring non-support message: '{message_text}' from user {username}")

async def handle_conversation_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, reply_info: dict) -> None:
    """Handle a user reply in an active conversation"""
    message_text = update.message.text
    user = update.effective_user
    conversation = reply_info['conversation']
    
    try:
        # For user replies, we'll let the API endpoint handle database operations
        # This prevents duplicate records and ensures proper conversation linking
        print(f"DEBUG: Processing user reply for conversation {conversation.id}")
        
        # Send to web dashboard
        message_data = {
            'telegram_user_id': str(user.id),
            'telegram_username': user.username,
            'telegram_first_name': user.first_name,
            'telegram_last_name': user.last_name,
            'chat_id': str(update.effective_chat.id),  # Required field that was missing!
            'message_text': message_text,
            'message_type': 'reply',
            'conversation_id': conversation.id,
            'is_followup': True
        }
        
        # Try to send to web dashboard
        try:
            response = requests.post(
                f"{WEB_DASHBOARD_URL}/api/support_message",
                json=message_data,
                timeout=10
            )
            if response.status_code == 201:
                api_response = response.json()
                print(f"Reply successfully saved to dashboard: {api_response}")
                # Get message ID from API response for further processing
                message_id = api_response.get('message_id')
                response_id = api_response.get('response_id')
                print(f"User reply saved as response {response_id} to message {message_id}")
            else:
                print(f"Failed to send reply to dashboard: {response.status_code} - {response.text}")
        except requests.RequestException as e:
            print(f"Error sending reply to dashboard: {e}")
        
        # Let the web backend handle AI/human auto-response when on-call
        try:
            await update.message.reply_text(
                "✅ Reply received! We'll follow up shortly.",
                parse_mode='Markdown'
            )
        except Exception as e:
            print(f"Reply ack error: {e}")
        
    except Exception as e:
        print(f"Error handling conversation reply: {e}")
        await update.message.reply_text(
            "❌ **Error processing your reply**\n\n"
            "There was an issue processing your message. Please try again or start a new support request with @support.",
            parse_mode='Markdown'
        )

async def handle_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages that start with @support with enhanced web dashboard integration."""
    message_text = update.message.text
    
    # Check if message starts with @support
    if message_text.lower().startswith('@support'):
        # Extract the support message
        support_message = message_text[8:].strip()
        
        if not support_message:
            await update.message.reply_text(
                "❌ Please include your support request after @support\n\n"
                "📝 **Example:**\n"
                "`@support I need help with my account`",
                parse_mode='Markdown'
            )
            
            # Store message in database
            with flask_app.app_context():
                message = SupportMessage(
                    telegram_user_id=str(update.effective_user.id),
                    username=update.effective_user.username or 'Unknown',
                    message_text=update.message.text,
                    message_type='text'
                )
                db.session.add(message)
                db.session.commit()
            
            # AI Support Analysis and Auto-Response
            try:
                # Analyze the message with AI
                analysis = ai_support.analyze_message(message)
                
                # Try to generate an auto-response
                auto_response = ai_support.generate_auto_response(message, analysis)
                
                if auto_response:
                    # Send the AI-generated response
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=auto_response.response_text,
                        parse_mode='Markdown'
                    )
                    
                    # Log the auto-response
                    print(f"AI auto-response sent for message {message.id} with confidence {auto_response.confidence_score:.2f}")
                else:
                    print(f"No suitable AI response found for message {message.id}")
            except Exception as e:
                print(f"AI analysis error: {e}")
                # Continue with normal flow if AI fails
            
            return
        
        # Get user information
        user = update.effective_user
        chat = update.effective_chat
        
        try:
            # Create support message in web dashboard
            message_data = {
                'telegram_user_id': str(user.id),
                'telegram_username': user.username,
                'telegram_first_name': user.first_name,
                'telegram_last_name': user.last_name,
                'chat_id': str(chat.id),
                'chat_title': chat.title,
                'message_text': support_message,
                'priority': 'normal'
            }
            
            # Send to web dashboard API
            response = requests.post(
                f"{WEB_DASHBOARD_URL}/api/support_message",
                json=message_data,
                timeout=10
            )
            
            if response.status_code == 201:
                result = response.json()
                message_id = result['message_id']
                
                # Send confirmation to user
                private_welcome_message = (
                    f"🎯 **Support Request Created - Case #{message_id}**\n\n"
                    f"👋 Hi {user.first_name or 'there'}! Your support request has been received.\n\n"
                    f"📋 **Case Details:**\n"
                    f"• **Case ID:** #{message_id}\n"
                    f"• **Status:** Open\n"
                    f"• **Priority:** Normal\n\n"
                    f"💬 **Your Request:**\n{support_message}\n\n"
                    f"📞 **What happens next:**\n"
                    f"• Our support team has been notified\n"
                    f"• Continue this conversation here in private\n"
                    f"• A technician will respond shortly\n"
                    f"• You can send additional details anytime\n\n"
                    f"💻 **Track online:** {WEB_DASHBOARD_URL}/message/{message_id}"
                )
                
                # Send private message to user (starts private conversation)
                dm_sent = False
                try:
                    await context.bot.send_message(
                        chat_id=user.id,  # Send directly to user (private chat)
                        text=private_welcome_message,
                        parse_mode='Markdown'
                    )
                    dm_sent = True
                except Exception as e:
                    logger.warning(f"DM to user failed, will provide start link in group: {e}")

                # Optional: forward to support group(s) only if explicitly enabled
                if FORWARD_SUPPORT_TO_GROUP:
                    group_message = (
                        f"🆘 **NEW SUPPORT REQUEST #{message_id}**\n\n"
                        f"👤 **From:** {user.first_name} {user.last_name or ''}"
                        f"{f' (@{user.username})' if user.username else ''}\n"
                        f"🆔 **User ID:** {user.id}\n"
                        f"💬 **Chat:** {chat.title or 'Private Chat'} ({chat.id})\n\n"
                        f"🌐 **Dashboard:** {WEB_DASHBOARD_URL}/message/{message_id}"
                    )
                    target_groups = resolve_target_group_ids()
                    for gid in target_groups:
                        try:
                            await context.bot.send_message(
                                chat_id=gid,
                                text=group_message,
                                parse_mode='Markdown'
                            )
                        except Exception as e:
                            logger.error(f"Failed to send group notification to {gid}: {e}")

                # If DM couldn't be sent, post minimal instruction in the group to start DM
                if not dm_sent:
                    try:
                        me = await context.bot.get_me()
                        bot_username = me.username
                        deep_link = f"https://t.me/{bot_username}?start=case_{message_id}"
                        minimal_msg = (
                            "👋 Please start a private chat with me to continue support: "
                            f"{deep_link}"
                        )
                        await context.bot.send_message(
                            chat_id=chat.id,
                            text=minimal_msg
                        )
                    except Exception as e:
                        logger.error(f"Failed to send minimal start link in group: {e}")
                
                # Start escalation tracking
                start_escalation_tracking(message_id, user.id, chat.id)
                
                # Private conversation already started with direct message above
                logger.info(f"Private support conversation initiated for case #{message_id} with user {user.username or user.id}")
                
                logger.info(f"Support message #{message_id} created for user {user.id}")
                
            else:
                # Fallback to old method if web dashboard is down
                await fallback_support_handling(update, context, support_message)
                
        except Exception as e:
            logger.error(f"Error creating support message: {e}")
            await fallback_support_handling(update, context, support_message)

async def fallback_support_handling(update: Update, context: ContextTypes.DEFAULT_TYPE, support_message: str):
    """Fallback method when web dashboard is unavailable. DM-first, no group content."""
    user = update.effective_user
    chat = update.effective_chat

    # Try to DM the user with a fallback acknowledgement
    fallback_dm = (
        "🟡 Support system is in limited mode right now.\n\n"
        "We've received your request here. Please continue this conversation in private messages with me. "
        "A technician will follow up shortly."
    )
    dm_sent = False
    try:
        await context.bot.send_message(chat_id=user.id, text=fallback_dm)
        dm_sent = True
    except Exception as e:
        logger.warning(f"Fallback DM failed: {e}")

    # If DM failed, provide a minimal start link in the current chat
    if not dm_sent:
        try:
            me = await context.bot.get_me()
            bot_username = me.username
            deep_link = f"https://t.me/{bot_username}?start=support"
            await update.message.reply_text(
                f"Please start a private chat with me to continue support: {deep_link}"
            )
        except Exception as e:
            logger.error(f"Failed to provide start link in chat: {e}")

async def handle_private_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages sent directly to the bot in private chat - link to support cases"""
    user = update.effective_user
    message_text = update.message.text
    user_telegram_id = str(user.id)
    username = user.username or 'Unknown'
    
    print(f"DEBUG: Processing private chat message from {username}: '{message_text}'")
    
    try:
        with flask_app.app_context():
            # First check if user has an active conversation using conversation manager
            reply_info = conversation_manager.handle_user_reply(
                user_telegram_id, username, message_text, update.message.message_id
            )
            
            if reply_info['is_reply']:
                # This is a reply in an active conversation - handle as conversation reply
                print(f"DEBUG: User {username} sent reply in private chat for active conversation {reply_info['conversation'].id}")
                await handle_conversation_reply(update, context, reply_info)
                return
            
            # Find the most recent support case for this user (private group OR direct message)
            recent_support_case = SupportMessage.query.filter_by(
                telegram_user_id=user_telegram_id
            ).filter(
                SupportMessage.status.in_(['open', 'assigned', 'in_progress'])
            ).order_by(SupportMessage.created_at.desc()).first()
            
            if recent_support_case:
                print(f"DEBUG: Found associated support case #{recent_support_case.id} for private message")
                
                # Do NOT create a new SupportMessage here. We'll record this as a
                # SupportResponse to the existing case via the web dashboard API.
                
                # Update conversation manager for the original case
                conversation_manager.create_or_reactivate_conversation(
                    user_telegram_id, username, recent_support_case.id
                )
                
                # Send API request to dashboard to notify of new private message
                try:
                    response = requests.post(
                        f"{WEB_DASHBOARD_URL}/api/support_message",
                        json={
                            'telegram_user_id': user_telegram_id,
                            'telegram_username': user.username,
                            'telegram_first_name': user.first_name,
                            'telegram_last_name': user.last_name,
                            'chat_id': update.effective_chat.id,
                            'chat_title': f"Private Chat - Case #{recent_support_case.id}",
                            'message_text': message_text,
                            'is_followup': True,
                            'message_type': 'reply',
                            'conversation_id': recent_support_case.id
                        },
                        timeout=5
                    )
                    
                    if response.status_code in (200, 201):
                        print(f"DEBUG: Successfully notified dashboard of private chat message for case #{recent_support_case.id}")
                        
                        # Send confirmation to user
                        await update.message.reply_text(
                            f"✅ **Message received for Case #{recent_support_case.id}**\n\n"
                            f"Your message has been added to the support conversation.\n"
                            f"A technician will respond shortly.",
                            parse_mode='Markdown'
                        )
                    else:
                        print(f"DEBUG: Dashboard API returned status {response.status_code}")
                        await update.message.reply_text(
                            "📝 Message received! Our support team will respond soon."
                        )
                        
                except requests.RequestException as e:
                    print(f"DEBUG: Failed to notify dashboard: {e}")
                    await update.message.reply_text(
                        "📝 Message received! Our support team will respond soon."
                    )
                    
                logger.info(f"Private chat message processed for case #{recent_support_case.id} from user {username}")
                
            else:
                print(f"DEBUG: No active support case found for user {username} in private chat")
                # No active support case - treat as new support request
                await update.message.reply_text(
                    f"👋 Hello! It looks like you're reaching out for support.\n\n"
                    f"To create a new support case, please send your message in our support group with the `@support` prefix.\n\n"
                    f"Example: `@support I need help with my account`\n\n"
                    f"If you have an existing case, please continue the conversation there.",
                    parse_mode='Markdown'
                )
                
    except Exception as e:
        logger.error(f"Error handling private chat message from {username}: {e}")
        await update.message.reply_text(
            "❌ Sorry, there was an error processing your message.\n"
            "Please try again or contact support through our main group."
        )

def start_escalation_tracking(message_id: int, user_id: int, chat_id: int):
    """Start tracking escalation for a support message."""
    escalation_time = datetime.now() + timedelta(seconds=ESCALATION_TIMEOUT)
    pending_escalations[message_id] = {
        'user_id': user_id,
        'chat_id': chat_id,
        'escalation_time': escalation_time,
        'escalation_level': 1
    }
    logger.info(f"Escalation tracking started for message #{message_id}")

async def check_escalations():
    """Check for messages that need escalation."""
    global pending_escalations
    current_time = datetime.now()
    
    messages_to_escalate = []
    for message_id, escalation_data in pending_escalations.items():
        if current_time >= escalation_data['escalation_time']:
            messages_to_escalate.append(message_id)
    
    for message_id in messages_to_escalate:
        await escalate_message(message_id)

async def escalate_message(message_id: int):
    """Escalate a support message to the next level."""
    try:
        escalation_data = pending_escalations.get(message_id)
        if not escalation_data:
            return
        
        # Check if message is still unresolved
        response = requests.get(f"{WEB_DASHBOARD_URL}/api/message/{message_id}/status")
        if response.status_code == 200:
            message_status = response.json()
            if message_status.get('status') in ['resolved', 'in_progress']:
                # Message is handled, remove from escalation
                del pending_escalations[message_id]
                logger.info(f"Message #{message_id} resolved, removing from escalation")
                return
        
        # Escalate to next level
        escalation_level = escalation_data['escalation_level'] + 1
        
        # Notify backup on-call person
        escalation_response = requests.post(
            f"{WEB_DASHBOARD_URL}/api/escalate/{message_id}",
            json={'escalation_level': escalation_level}
        )
        
        if escalation_response.status_code == 200:
            # Update escalation tracking
            escalation_data['escalation_level'] = escalation_level
            escalation_data['escalation_time'] = datetime.now() + timedelta(seconds=ESCALATION_TIMEOUT)
            
            # Notify in support group(s) (optional)
            if FORWARD_SUPPORT_TO_GROUP and app_instance:
                escalation_message = (
                    f"🚨 **ESCALATION ALERT**\n\n"
                    f"📋 **Message ID:** #{message_id}\n"
                    f"⏰ **Escalation Level:** {escalation_level}\n"
                    f"⚠️ **No response received within {ESCALATION_TIMEOUT//60} minutes**\n\n"
                    f"🔄 **Next backup tech has been notified**\n"
                    f"🌐 **View:** {WEB_DASHBOARD_URL}/message/{message_id}"
                )
                for gid in resolve_target_group_ids():
                    try:
                        await app_instance.bot.send_message(
                            chat_id=gid,
                            text=escalation_message,
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Failed to send escalation alert to {gid}: {e}")
            
            logger.info(f"Message #{message_id} escalated to level {escalation_level}")
        else:
            # Remove from escalation if escalation failed
            del pending_escalations[message_id]
            logger.error(f"Failed to escalate message #{message_id}")
            
    except Exception as e:
        logger.error(f"Error escalating message #{message_id}: {e}")
        # Remove problematic escalation
        if message_id in pending_escalations:
            del pending_escalations[message_id]

def run_escalation_checker():
    """Run the escalation checker in a separate thread."""
    def escalation_loop():
        while True:
            try:
                asyncio.run(check_escalations())
            except Exception as e:
                logger.error(f"Error in escalation checker: {e}")
            time.sleep(60)  # Check every minute
    
    escalation_thread = threading.Thread(target=escalation_loop, daemon=True)
    escalation_thread.start()
    logger.info("Escalation checker started")


async def add_users_to_group(group_id: str, user_ids: list) -> int:
    """Add multiple users to a Telegram group"""
    if not app_instance:
        logger.error("Bot application not initialized")
        return 0
    
    added_count = 0
    bot = app_instance.bot
    
    for user_id in user_ids:
        try:
            # Convert user_id to int if it's a string
            user_id_int = int(user_id)
            
            # Try to add the user to the group
            # Note: Bot must be admin in the group to add members
            await bot.add_chat_member(
                chat_id=group_id,
                user_id=user_id_int
            )
            added_count += 1
            logger.info(f"Successfully added user {user_id_int} to group {group_id}")
        except Exception as e:
            logger.error(f"Failed to add user {user_id} to group {group_id}: {e}")
            # Continue with next user even if one fails
            continue
    
    return added_count

def main() -> None:
    """Main function to start the bot"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found in environment variables")
        return
    
    # Initialize Flask app for database access
    init_flask_app()
    # Warn if no target groups configured when forwarding is enabled
    try:
        if FORWARD_SUPPORT_TO_GROUP and not resolve_target_group_ids():
            logger.warning("No Telegram support groups configured. Set SUPPORT_GROUP_ID or add active groups in Admin > Telegram Groups.")
    except Exception as e:
        logger.error(f"Error checking Telegram groups: {e}")
    
    # Initialize conversation manager and private support group manager with Flask app
    global conversation_manager, private_group_manager
    conversation_manager = ConversationManager(flask_app)
    
    # Create the Application and get bot instance for private group manager
    application = Application.builder().token(BOT_TOKEN).build()
    private_group_manager = PrivateSupportGroupManager(application.bot, flask_app)
    
    logger.info("🚀 Starting Enhanced Support Bot with Web Dashboard Integration")
    logger.info(f"📊 Web Dashboard: {WEB_DASHBOARD_URL}")
    logger.info(f"⏰ Escalation Timeout: {ESCALATION_TIMEOUT} seconds")
    
    # Use the existing Application instance
    global app_instance
    app_instance = application

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages))

    # Start escalation checker
    run_escalation_checker()
    
    # Start the bot
    logger.info("🤖 Bot is starting...")
    logger.info("📱 Ready to receive support requests!")
    logger.info("🛑 Press Ctrl+C to stop the bot")
    application.run_polling()

if __name__ == "__main__":
    main()
