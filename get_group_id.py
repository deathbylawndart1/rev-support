#!/usr/bin/env python3
"""
Script to get Telegram group ID from the bot's updates
"""
import os
import asyncio
from dotenv import load_dotenv
from telegram import Bot

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')

async def get_group_id():
    bot = Bot(token=BOT_TOKEN)
    
    print("Fetching recent updates...")
    updates = await bot.get_updates(limit=10)
    
    if not updates:
        print("No recent updates found. Please:")
        print("1. Make sure the bot is added to the support group")
        print("2. Send a message in the group")
        print("3. Run this script again")
        return
    
    print("\nRecent chats where the bot received messages:")
    print("-" * 50)
    
    seen_chats = set()
    for update in updates:
        if update.message and update.message.chat:
            chat = update.message.chat
            chat_id = chat.id
            
            if chat_id not in seen_chats:
                seen_chats.add(chat_id)
                chat_type = chat.type
                chat_title = chat.title or "Private Chat"
                username = chat.username or "N/A"
                
                print(f"Chat ID: {chat_id}")
                print(f"  Type: {chat_type}")
                print(f"  Title: {chat_title}")
                print(f"  Username: @{username}" if username != "N/A" else "  Username: N/A")
                print("-" * 50)
    
    if not seen_chats:
        print("No chats found in recent updates.")
    else:
        print(f"\nFound {len(seen_chats)} unique chat(s)")
        print("\nTo use a group ID, update your .env file:")
        print("SUPPORT_GROUP_ID=<the_negative_number_above>")

if __name__ == "__main__":
    asyncio.run(get_group_id())
