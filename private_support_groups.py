"""
Private Support Groups Module
Handles creation and management of temporary private support chat groups
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from telegram import Bot, ChatMember
from telegram.error import TelegramError
from models import db, SupportMessage, User
from datetime import datetime

logger = logging.getLogger(__name__)

class PrivateSupportGroupManager:
    """Manages private support groups for individual support cases"""
    
    def __init__(self, bot: Bot, flask_app):
        self.bot = bot
        self.flask_app = flask_app
    
    async def create_private_support_group(self, support_message_id: int, user_telegram_id: str, user_name: str) -> Dict[str, Any]:
        """
        Create a private support group for a specific support case
        
        Args:
            support_message_id: ID of the support message
            user_telegram_id: Telegram user ID who created the support request
            user_name: User's display name
            
        Returns:
            Dict with group info or error details
        """
        try:
            with self.flask_app.app_context():
                # Get support message from database
                support_message = SupportMessage.query.get(support_message_id)
                if not support_message:
                    return {'success': False, 'error': 'Support message not found'}
                
                # Create group title
                group_title = f"Support Case #{support_message_id} - {user_name}"
                
                # Note: Telegram Bot API doesn't support creating groups directly
                # Instead, we'll create a supergroup and add the user
                # For now, we'll simulate this by creating a direct conversation with bot
                # In production, you might want to use a pre-existing group template
                
                # Create a temporary chat ID (this would be replaced with actual group creation in production)
                # For demonstration, we'll use the bot's chat with the user as the "private group"
                chat_id = user_telegram_id  # Direct message chat
                group_id = f"private_{support_message_id}_{user_telegram_id}"  # Synthetic group ID
                
                logger.info(f"Created private support chat {group_id} for case #{support_message_id}")
                
                # Update support message with private group info
                support_message.private_group_id = group_id
                support_message.private_group_title = group_title
                support_message.private_group_created = True
                
                # For direct messages, we'll use a deep link instead of invite link
                try:
                    # Create a deep link to start chat with bot about this case
                    bot_username = (await self.bot.get_me()).username
                    deep_link = f"https://t.me/{bot_username}?start=case_{support_message_id}"
                    support_message.private_group_invite_link = deep_link
                except TelegramError as e:
                    logger.warning(f"Could not create deep link for case {support_message_id}: {e}")
                
                db.session.commit()
                
                # Send welcome message to the private chat
                welcome_message = (
                    f"🎯 **Private Support Chat**\n\n"
                    f"👋 Welcome {user_name}! This is your dedicated support chat.\n\n"
                    f"📋 **Case ID:** #{support_message_id}\n"
                    f"💬 **Original Request:** {support_message.message_text[:100]}{'...' if len(support_message.message_text) > 100 else ''}\n\n"
                    f"🔧 **How this works:**\n"
                    f"• This chat is private between you and our support team\n"
                    f"• A technician will respond to help you\n"
                    f"• You can send messages, files, and screenshots here\n"
                    f"• Continue the conversation here for better privacy\n\n"
                    f"⏱️ **Response Time:** Usually within 15 minutes during business hours"
                )
                
                await self.bot.send_message(
                    chat_id=int(chat_id),
                    text=welcome_message,
                    parse_mode='Markdown'
                )
                
                return {
                    'success': True,
                    'group_id': str(chat.id),
                    'group_title': group_title,
                    'invite_link': support_message.private_group_invite_link
                }
                
        except TelegramError as e:
            logger.error(f"Failed to create private support group for case #{support_message_id}: {e}")
            return {'success': False, 'error': f'Telegram error: {str(e)}'}
        except Exception as e:
            logger.error(f"Unexpected error creating private support group: {e}")
            return {'success': False, 'error': f'Unexpected error: {str(e)}'}
    
    async def add_technician_to_group(self, support_message_id: int, technician_telegram_id: str) -> bool:
        """
        Add a technician to the private support group
        
        Args:
            support_message_id: ID of the support message
            technician_telegram_id: Telegram user ID of the technician
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.flask_app.app_context():
                support_message = SupportMessage.query.get(support_message_id)
                if not support_message or not support_message.private_group_id:
                    return False
                
                # Add technician to the group
                await self.bot.add_chat_member(
                    chat_id=support_message.private_group_id,
                    user_id=int(technician_telegram_id)
                )
                
                # Send notification that technician joined
                technician_message = (
                    f"👨‍💻 **Support Technician Joined**\n\n"
                    f"A technician has joined the chat and will help you with your request.\n"
                    f"Feel free to provide more details or ask questions!"
                )
                
                await self.bot.send_message(
                    chat_id=support_message.private_group_id,
                    text=technician_message,
                    parse_mode='Markdown'
                )
                
                logger.info(f"Added technician {technician_telegram_id} to private group {support_message.private_group_id}")
                return True
                
        except TelegramError as e:
            logger.error(f"Failed to add technician to private group: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error adding technician to group: {e}")
            return False
    
    async def archive_support_group(self, support_message_id: int) -> bool:
        """
        Archive a private support group when case is resolved
        
        Args:
            support_message_id: ID of the support message
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.flask_app.app_context():
                support_message = SupportMessage.query.get(support_message_id)
                if not support_message or not support_message.private_group_id:
                    return False
                
                # Send final message
                final_message = (
                    f"✅ **Support Case Resolved**\n\n"
                    f"Your support case #{support_message_id} has been marked as resolved.\n"
                    f"This chat will be archived. Thank you for using our support system!\n\n"
                    f"If you need further assistance, please create a new support request."
                )
                
                await self.bot.send_message(
                    chat_id=support_message.private_group_id,
                    text=final_message,
                    parse_mode='Markdown'
                )
                
                # Leave the group (archives it from bot's perspective)
                await self.bot.leave_chat(support_message.private_group_id)
                
                logger.info(f"Archived private support group {support_message.private_group_id}")
                return True
                
        except TelegramError as e:
            logger.error(f"Failed to archive private group: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error archiving group: {e}")
            return False
