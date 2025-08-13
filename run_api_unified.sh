#!/usr/bin/env bash
set -euo pipefail

# KBAI API Unified Run Script
# Combines DARKBO ai_worker.py and kbai-api run_api.sh functionality

echo "🚀 Starting KBAI API with integrated AI processing..."

# Load environment variables if .env exists
if [ -f ".env" ]; then
    echo "📄 Loading environment variables from .env"
    export $(grep -v '^#' .env | xargs)
fi

# Configuration defaults
DEFAULT_HOST="0.0.0.0"
DEFAULT_PORT="8000"
DEFAULT_RELOAD="false"

# Get configuration from environment or use defaults
HOST=${HOST:-$DEFAULT_HOST}
PORT=${PORT:-$DEFAULT_PORT}
RELOAD=${RELOAD:-$DEFAULT_RELOAD}
DATA_DIR=${DATA_DIR:-"./data"}

echo ""
echo "🔧 Configuration:"
echo "   Host: $HOST"
echo "   Port: $PORT"
echo "   Reload: $RELOAD"
echo "   Data Directory: $DATA_DIR"
echo ""

# Check if dependencies are installed
echo "📦 Checking dependencies..."
if ! python -c "import fastapi, uvicorn, openai, sentence_transformers, faiss, docx" 2>/dev/null; then
    echo "⚠️  Missing dependencies. Installing requirements..."
    pip install -r requirements.txt
    echo "✅ Dependencies installed"
fi

# Create ASPCA test document if needed
echo "📝 Creating ASPCA test document..."
python create_aspca_doc.py

# Initialize database
DB_PATH="./app/kbai_api.db"
echo "🗄️  Initializing database..."
if [ ! -f "$DB_PATH" ]; then
    echo "   Creating new database..."
    ./init_db.sh
else
    echo "   Database already exists"
fi

# Generate sample data
echo "📊 Generating sample data..."
python create_sample_data.py

# Build indexes for all projects
echo "🔍 Building AI indexes..."
python -c "
import sys
sys.path.append('.')
from simple_ai_worker import initialize_all_indexes
success = initialize_all_indexes('$DATA_DIR')
if success:
    print('✅ All indexes built successfully')
else:
    print('⚠️  Some indexes failed to build')
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Index building failed. Continuing without AI features..."
fi

echo ""
echo "🎯 Starting KBAI API server..."
echo "📚 API Documentation will be available at:"
echo "   Swagger UI: http://$HOST:$PORT/docs"
echo "   ReDoc: http://$HOST:$PORT/redoc"
echo "   Admin Dashboard: http://$HOST:$PORT/admin"
echo ""
echo "🔑 Authentication:"
echo "   Default credentials: admin / admin"
echo "   API Key: $KBAI_API_TOKEN"
echo ""
echo "⏹️  Press Ctrl+C to stop the server"
echo ""

# Start the server
if [ "$RELOAD" = "true" ]; then
    uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
else
    uvicorn app.main:app --host "$HOST" --port "$PORT"
fi