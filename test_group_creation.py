#!/usr/bin/env python3
import asyncio
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_create_group():
    """Test the group creation function directly"""
    try:
        from bot import create_telegram_supergroup
        
        result = await create_telegram_supergroup("Test Group", "Test Description")
        
        if result:
            print("✅ Success! Group creation instructions generated:")
            print(f"Setup Code: {result['setup_code']}")
            print(f"Bot Username: {result['bot_username']}")
            print(f"Instructions: {result['instructions']}")
        else:
            print("❌ Failed: Function returned None")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_create_group())
