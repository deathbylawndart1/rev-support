#!/bin/bash
# Flask Server Launcher Script
# Starts the web dashboard server on localhost:5000

# Change to project directory
cd /home/ryan/CascadeProjects/windsurf-project

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "Activated virtual environment"
fi

# Start Flask server
echo "🚀 Starting Flask Web Dashboard Server..."
echo "📊 Dashboard will be available at: http://localhost:5000"
echo "🔑 Login with: admin / admin123"
echo "⚡ Press Ctrl+C to stop the server"
echo "============================================================"

# Run the Flask application
python3 app.py

# Keep terminal open on exit
echo ""
echo "Flask server stopped. Press Enter to close this window..."
read
