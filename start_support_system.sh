#!/bin/bash
# Combined Support System Launcher
# Starts both Flask server and Telegram bot simultaneously

# Change to project directory
cd /home/ryan/CascadeProjects/windsurf-project

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Activated virtual environment"
fi

echo "🚀 Starting AI Support System..."
echo "============================================================"
echo "📊 Flask Dashboard: http://localhost:5000"
echo "🤖 Telegram Bot: Active and listening"
echo "🔑 Login: admin / admin123"
echo "⚡ Press Ctrl+C to stop both services"
echo "============================================================"

# Start Flask server in background
echo "Starting Flask server..."
python3 app.py &
FLASK_PID=$!

# Wait a moment for Flask to start
sleep 3

# Start Telegram bot in background
echo "Starting Telegram bot..."
python3 bot.py &
BOT_PID=$!

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    kill $FLASK_PID 2>/dev/null
    kill $BOT_PID 2>/dev/null
    echo "✅ All services stopped"
    exit 0
}

# Set trap to cleanup on Ctrl+C
trap cleanup SIGINT

# Wait for both processes
wait $FLASK_PID $BOT_PID
