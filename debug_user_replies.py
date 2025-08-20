#!/usr/bin/env python3
"""
Debug script to test user reply tracking in dashboard
"""

from app import app, db
from models import ConversationState, SupportMessage, SupportResponse
from conversation_manager import conversation_manager
from datetime import datetime

def debug_user_reply_tracking():
    """Debug the user reply tracking system"""
    with app.app_context():
        print("=== DEBUGGING USER REPLY TRACKING ===\n")
        
        # Get the current conversation state
        user_id = "7166768323"  # From the database query above
        print(f"1. Checking conversation for user {user_id}")
        
        conversation = ConversationState.query.filter_by(
            user_telegram_id=user_id,
            is_active=True
        ).first()
        
        if conversation:
            print(f"   ✅ Active conversation found: ID {conversation.id}")
            print(f"   - Topic: {conversation.conversation_topic}")
            print(f"   - Awaiting Reply: {conversation.awaiting_reply}")
            print(f"   - Last Activity: {conversation.last_activity}")
            print(f"   - Last Response ID: {conversation.last_response_id}")
        else:
            print("   ❌ No active conversation found!")
            return
        
        print(f"\n2. Testing conversation manager reply detection...")
        
        # Simulate a user reply using the conversation manager
        test_message_text = "This is a test user reply"
        test_message_id = 999999  # Fake message ID for testing
        username = "testuser"
        
        reply_info = conversation_manager.handle_user_reply(
            user_telegram_id=user_id,
            username=username,
            message_text=test_message_text,
            message_id=test_message_id
        )
        
        print(f"   Reply Detection Result:")
        print(f"   - Is Reply: {reply_info['is_reply']}")
        print(f"   - Conversation: {reply_info['conversation'].id if reply_info['conversation'] else None}")
        print(f"   - Context: {reply_info['context']}")
        
        if reply_info['is_reply']:
            print("   ✅ Conversation manager correctly detected user reply!")
        else:
            print("   ❌ Conversation manager failed to detect user reply!")
            
        print(f"\n3. Checking recent messages in database...")
        recent_messages = SupportMessage.query.order_by(SupportMessage.created_at.desc()).limit(3).all()
        
        for msg in recent_messages:
            print(f"   Message ID {msg.id}: '{msg.message_text[:30]}...' by {msg.telegram_username}")
            print(f"   - Status: {msg.status}")
            print(f"   - User ID: {msg.telegram_user_id}")
            print(f"   - Created: {msg.created_at}")
            
            # Check if this message has responses
            responses = SupportResponse.query.filter_by(message_id=msg.id).all()
            if responses:
                for resp in responses:
                    print(f"     → Response: '{resp.response_text[:20]}...' (sent: {resp.sent_to_telegram})")
            
        print(f"\n4. Checking API endpoint response...")
        print("   The bot should be calling /api/support_message when user replies")
        print("   Let's check if this endpoint is working correctly...")

if __name__ == "__main__":
    debug_user_reply_tracking()
