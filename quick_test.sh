#!/usr/bin/env bash
set -euo pipefail

echo "🧪 KBAI API Quick Test Setup"
echo "============================"

# Clean up any previous data
echo "🧹 Cleaning up previous data..."
python cleanup.py

# Setup environment
echo "🔧 Setting up environment..."
if [ ! -f ".env" ]; then
    echo "❌ .env file not found! Please create it first."
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Initialize everything
echo "🚀 Initializing system..."
./run_api_unified.sh &
SERVER_PID=$!

# Wait a moment for server to start
sleep 10

# Run tests
echo "🧪 Running comprehensive tests..."
python test_kbai_comprehensive.py --standalone

# Clean up
echo "🛑 Stopping server..."
kill $SERVER_PID 2>/dev/null || true

echo "✅ Test complete!"