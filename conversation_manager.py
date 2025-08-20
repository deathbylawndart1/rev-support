"""
Conversation Manager for Telegram Bot
Handles conversation state tracking and reply detection
"""

import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from flask import current_app
from models import db, ConversationState, SupportMessage, SupportResponse

class ConversationManager:
    """Manages conversation states for reply detection"""
    
    def __init__(self, flask_app=None):
        self.conversation_timeout = timedelta(hours=2)  # 2 hours conversation timeout
        self.flask_app = flask_app
    
    def start_conversation(self, user_telegram_id: str, username: str, message_id: int, topic: str = None) -> ConversationState:
        """Start a new conversation or update existing one"""
        if self.flask_app:
            with self.flask_app.app_context():
                return self._start_conversation_impl(user_telegram_id, username, message_id, topic)
        else:
            return self._start_conversation_impl(user_telegram_id, username, message_id, topic)
    
    def _start_conversation_impl(self, user_telegram_id: str, username: str, message_id: int, topic: str = None) -> ConversationState:
        """Implementation of start_conversation"""
        # Check if user already has an active conversation
        conversation = ConversationState.query.filter_by(
            user_telegram_id=user_telegram_id,
            is_active=True
        ).first()
        
        if conversation:
            # Update existing conversation
            conversation.last_message_id = message_id
            conversation.conversation_topic = topic or conversation.conversation_topic
            conversation.update_activity()
            conversation.awaiting_reply = True
        else:
            # Create new conversation
            conversation = ConversationState(
                user_telegram_id=user_telegram_id,
                username=username,
                last_message_id=message_id,
                conversation_topic=topic,
                awaiting_reply=True,
                expires_at=datetime.utcnow() + self.conversation_timeout
            )
            db.session.add(conversation)
        
        db.session.commit()
        return conversation
    
    def update_conversation_response(self, user_telegram_id: str, response_id: int):
        """Update conversation with technician response"""
        # First try to find active conversation
        conversation = ConversationState.query.filter_by(
            user_telegram_id=user_telegram_id,
            is_active=True
        ).first()
        
        if not conversation:
            # If no active conversation, try to find the most recent inactive one to reactivate
            conversation = ConversationState.query.filter_by(
                user_telegram_id=user_telegram_id
            ).order_by(ConversationState.last_activity.desc()).first()
            
            if conversation:
                # Reactivate existing conversation
                print(f"DEBUG: Reactivating conversation {conversation.id} for user {user_telegram_id}")
                conversation.is_active = True
                conversation.expires_at = datetime.utcnow() + timedelta(hours=24)
            else:
                # Create new conversation if none exists
                print(f"DEBUG: Creating new conversation for user {user_telegram_id} on technician response")
                conversation = ConversationState(
                    user_telegram_id=user_telegram_id,
                    conversation_topic="Support Request",
                    is_active=True,
                    expires_at=datetime.utcnow() + timedelta(hours=24)
                )
                db.session.add(conversation)
                db.session.flush()  # Get the ID
        
        # Update conversation with response
        conversation.last_response_id = response_id

        # Try to resolve the SupportMessage for this response so we can
        # accurately keep last_message_id pointing at the case root.
        try:
            resp_obj = SupportResponse.query.get(response_id)
            if resp_obj and resp_obj.message_id:
                conversation.last_message_id = resp_obj.message_id
        except Exception:
            pass

        # After a technician response, we are awaiting user's reply.
        conversation.awaiting_reply = True
        conversation.update_activity()
        db.session.commit()
        
        print(f"DEBUG: Updated conversation {conversation.id} with response {response_id}, awaiting_reply=True")

    def create_or_reactivate_conversation(self, user_telegram_id: str, username: str, message_id: int, topic: str = None) -> ConversationState:
        """Ensure a conversation exists and is tied to the given SupportMessage.
        This is used when a user sends a message in private chat so that further
        replies can be associated with the correct case.
        """
        if self.flask_app:
            with self.flask_app.app_context():
                return self._create_or_reactivate_conversation_impl(user_telegram_id, username, message_id, topic)
        else:
            return self._create_or_reactivate_conversation_impl(user_telegram_id, username, message_id, topic)

    def _create_or_reactivate_conversation_impl(self, user_telegram_id: str, username: str, message_id: int, topic: str = None) -> ConversationState:
        conversation = ConversationState.query.filter_by(
            user_telegram_id=user_telegram_id,
            is_active=True
        ).first()

        if conversation:
            conversation.last_message_id = message_id
            if topic:
                conversation.conversation_topic = topic
            # A user message means we're not awaiting a user reply; awaiting tech reply instead
            conversation.awaiting_reply = False
            conversation.update_activity()
        else:
            conversation = ConversationState(
                user_telegram_id=user_telegram_id,
                username=username,
                last_message_id=message_id,
                conversation_topic=topic,
                is_active=True,
                awaiting_reply=False
            )
            db.session.add(conversation)
        db.session.commit()
        return conversation
    
    def is_user_in_conversation(self, user_telegram_id: str) -> bool:
        """Check if user has an active conversation"""
        conversation = ConversationState.query.filter_by(
            user_telegram_id=user_telegram_id,
            is_active=True
        ).first()
        
        if not conversation:
            return False
        
        # Check if conversation has expired
        if conversation.is_expired():
            self.end_conversation(user_telegram_id)
            return False
        
        return True
    
    def get_conversation(self, user_telegram_id: str) -> Optional[ConversationState]:
        """Get active conversation for user"""
        if self.flask_app:
            with self.flask_app.app_context():
                return self._get_conversation_impl(user_telegram_id)
        else:
            return self._get_conversation_impl(user_telegram_id)
    
    def _get_conversation_impl(self, user_telegram_id: str) -> Optional[ConversationState]:
        """Implementation of get_conversation"""
        conversation = ConversationState.query.filter_by(
            user_telegram_id=user_telegram_id,
            is_active=True
        ).first()
        
        if conversation and conversation.is_expired():
            self.end_conversation(user_telegram_id)
            return None
        
        return conversation
    
    def handle_user_reply(self, user_telegram_id: str, username: str, message_text: str, message_id: int) -> Dict[str, Any]:
        """Handle a user reply in an active conversation"""
        print(f"DEBUG: Checking for conversation for user {user_telegram_id}")
        
        if self.flask_app:
            with self.flask_app.app_context():
                return self._handle_user_reply_impl(user_telegram_id, username, message_text, message_id)
        else:
            return self._handle_user_reply_impl(user_telegram_id, username, message_text, message_id)
    
    def _handle_user_reply_impl(self, user_telegram_id: str, username: str, message_text: str, message_id: int) -> Dict[str, Any]:
        """Implementation of handle_user_reply"""
        conversation = self._get_conversation_impl(user_telegram_id)
        
        if not conversation:
            print(f"DEBUG: No active conversation found for user {user_telegram_id}")
            return {
                'is_reply': False,
                'conversation': None,
                'context': None
            }
        
        print(f"DEBUG: Found active conversation {conversation.id} for user {user_telegram_id}")
        print(f"DEBUG: Conversation topic: {conversation.conversation_topic}")
        print(f"DEBUG: Last response ID: {conversation.last_response_id}")
        print(f"DEBUG: Awaiting reply: {conversation.awaiting_reply}")
        
        # Only treat as reply if we're actually awaiting a reply from technician response
        if not conversation.awaiting_reply:
            print(f"DEBUG: Conversation {conversation.id} not awaiting reply - ignoring message as regular group chat")
            return {
                'is_reply': False,
                'conversation': None,
                'context': None
            }
        
        # Check if message is too old (more than 1 hour after last activity)
        time_since_activity = datetime.utcnow() - conversation.last_activity
        if time_since_activity.total_seconds() > 3600:  # 1 hour
            print(f"DEBUG: Message too old ({time_since_activity}) - ending conversation and ignoring as reply")
            self.end_conversation(user_telegram_id)
            return {
                'is_reply': False,
                'conversation': None,
                'context': None
            }
        
        print(f"DEBUG: Valid reply detected from user {user_telegram_id} in conversation {conversation.id}")
        
        # Update conversation activity. Do NOT set last_message_id here because
        # message_id is a Telegram message ID, not SupportMessage.id. Linking
        # to SupportMessage is handled in the web backend when persisting the reply.
        conversation.awaiting_reply = False
        conversation.update_activity()
        
        # Get conversation context
        context = {
            'conversation_id': conversation.id,
            'topic': conversation.conversation_topic,
            'started_at': conversation.started_at,
            'last_response_id': conversation.last_response_id,
            'is_followup': True
        }
        
        db.session.commit()
        
        print(f"DEBUG: Processing valid reply from user {user_telegram_id} in conversation {conversation.id}")
        
        return {
            'is_reply': True,
            'conversation': conversation,
            'context': context
        }
    
    def end_conversation(self, user_telegram_id: str):
        """End an active conversation"""
        conversation = ConversationState.query.filter_by(
            user_telegram_id=user_telegram_id,
            is_active=True
        ).first()
        
        if conversation:
            conversation.is_active = False
            conversation.awaiting_reply = False
            db.session.commit()
    
    def cleanup_expired_conversations(self):
        """Clean up expired conversations"""
        expired_conversations = ConversationState.query.filter(
            ConversationState.is_active == True,
            ConversationState.expires_at < datetime.utcnow()
        ).all()
        
        for conversation in expired_conversations:
            conversation.is_active = False
            conversation.awaiting_reply = False
        
        if expired_conversations:
            db.session.commit()
            print(f"Cleaned up {len(expired_conversations)} expired conversations")
    
    def get_conversation_stats(self) -> Dict[str, int]:
        """Get conversation statistics"""
        active_count = ConversationState.query.filter_by(is_active=True).count()
        total_count = ConversationState.query.count()
        awaiting_reply_count = ConversationState.query.filter_by(
            is_active=True, 
            awaiting_reply=True
        ).count()
        
        return {
            'active_conversations': active_count,
            'total_conversations': total_count,
            'awaiting_replies': awaiting_reply_count
        }

# Global conversation manager instance
conversation_manager = ConversationManager()
