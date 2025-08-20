#!/bin/bash
# Telegram Bot Launcher Script
# Starts the AI-powered Telegram support bot

# Change to project directory
cd /home/ryan/CascadeProjects/windsurf-project

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "Activated virtual environment"
fi

# Start Telegram bot
echo "🤖 Starting AI-Powered Telegram Support Bot..."
echo "📱 Bot will respond to messages starting with @support"
echo "🧠 AI Support Technician is active"
echo "⚡ Press Ctrl+C to stop the bot"
echo "=" * 60

# Run the Telegram bot
python3 bot.py

# Keep terminal open on exit
echo ""
echo "Telegram bot stopped. Press Enter to close this window..."
read
