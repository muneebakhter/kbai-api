#!/usr/bin/env bash
set -euo pipefail

echo "🚀 KBAI API with DARKBO Integration - Complete Demo"
echo "=================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧹 Step 1: Clean up any previous data${NC}"
python cleanup.py

echo ""
echo -e "${BLUE}🔧 Step 2: Install dependencies${NC}"
pip install -r requirements.txt -q

echo ""
echo -e "${BLUE}📊 Step 3: Generate sample data and initialize system${NC}"
./run_api_unified.sh &
SERVER_PID=$!

# Wait for server to start
echo "⏳ Waiting for server to start..."
sleep 10

echo ""
echo -e "${BLUE}🧪 Step 4: Run comprehensive tests${NC}"
python test_kbai_comprehensive.py --standalone

echo ""
echo -e "${BLUE}🎯 Step 5: Interactive Demo${NC}"
echo "Server is running at http://localhost:8000"
echo ""
echo -e "${GREEN}Available endpoints:${NC}"
echo "  • Swagger UI: http://localhost:8000/docs"
echo "  • Admin Dashboard: http://localhost:8000/admin"
echo "  • Health Check: http://localhost:8000/healthz"
echo ""
echo -e "${GREEN}Authentication:${NC}"
echo "  • Username: admin"
echo "  • Password: admin"
echo "  • API Key: kbai-secure-api-token-change-in-production"
echo ""
echo -e "${GREEN}Sample Queries to Try:${NC}"
echo "  • 'How do I reset my password?' (tech-support project)"
echo "  • 'What is the vacation policy?' (hr-policies project)"
echo "  • 'What is the ASPCA website?' (aspca-test project)"
echo ""

# Get an auth token for demonstration
echo -e "${YELLOW}Getting authentication token...${NC}"
TOKEN=$(curl -s -X POST "http://localhost:8000/v1/auth/token" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin",
    "client_name": "demo-client",
    "scopes": ["read:basic", "write:projects"]
  }' | jq -r '.access_token')

echo -e "${GREEN}✅ Token obtained: ${TOKEN:0:20}...${NC}"
echo ""

# Demonstrate queries
echo -e "${YELLOW}🔍 Demonstrating queries:${NC}"
echo ""

echo "1. Password reset query:"
curl -s -X POST "http://localhost:8000/v1/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "How do I reset my password?", "project_id": "tech-support"}' | \
  jq -r '.answer' | head -3
echo ""

echo "2. ASPCA website query:"
curl -s -X POST "http://localhost:8000/v1/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "What is the ASPCA website?", "project_id": "aspca-test"}' | \
  jq -r '.answer' | head -3
echo ""

echo "3. List all projects:"
curl -s -X GET "http://localhost:8000/v1/projects" \
  -H "Authorization: Bearer $TOKEN" | \
  jq -r '.[] | "  • \(.id): \(.name) (\(if .active then "active" else "inactive" end))"'
echo ""

echo -e "${GREEN}🎉 Demo Complete!${NC}"
echo ""
echo -e "${YELLOW}The server is still running. You can:${NC}"
echo "  • Visit http://localhost:8000/docs for interactive API documentation"
echo "  • Visit http://localhost:8000/admin for the admin dashboard"
echo "  • Test queries with the token: $TOKEN"
echo ""
echo -e "${RED}Press Ctrl+C to stop the server when done${NC}"

# Keep server running until user stops it
wait $SERVER_PID