# KBAI API with DARKBO Integration

A comprehensive Knowledge Base AI API that integrates DARKBO functionality with secure authentication, document processing, and AI-powered querying.

## 🎯 Overview

This project successfully integrates all DARKBO functionality into the kbai-api framework, providing:

- **Secure Authentication**: JWT tokens and API keys
- **Document Processing**: Supports .docx, .pdf, .txt, .html files
- **AI-Powered Search**: Text similarity matching with OpenAI integration
- **Project Management**: Multi-project knowledge base with isolated indexes
- **Automatic Indexing**: Rebuilds indexes after file uploads
- **Comprehensive Testing**: Full test suite validating all functionality

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- SQLite3
- OpenAI API key (optional, falls back to text matching)

### Installation

1. **Clone and setup**:
   ```bash
   git clone <repository-url>
   cd kbai-api
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your OpenAI API key if desired
   ```

3. **Run the complete demo**:
   ```bash
   ./demo.sh
   ```

   This will:
   - Clean any previous data
   - Install dependencies
   - Generate sample data
   - Initialize the database and AI indexes
   - Run comprehensive tests
   - Start the API server
   - Demonstrate key functionality

## 📋 Manual Setup

If you prefer to run steps manually:

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Initialize system**:
   ```bash
   ./run_api_unified.sh
   ```

3. **Run tests**:
   ```bash
   python test_kbai_comprehensive.py --standalone
   ```

## 🔧 Configuration

Key environment variables in `.env`:

```bash
# Server
HOST=0.0.0.0
PORT=8000

# Authentication
KBAI_API_TOKEN=your-secure-api-token
AUTH_SIGNING_KEY=your-jwt-signing-key

# AI Processing
OPENAI_API_KEY=your-openai-api-key

# Data Storage
DATA_DIR=./data
```

## 📚 API Endpoints

### Authentication
- `POST /v1/auth/token` - Get JWT token (username: admin, password: admin)
- `GET /v1/auth/modes` - Check available auth methods

### Projects
- `GET /v1/projects` - List all projects
- `POST /v1/projects` - Create/update project
- `GET /v1/projects/{id}` - Get project details

### Document Management
- `POST /v1/projects/{id}/ingest` - Upload documents
- `POST /v1/projects/{id}/reindex` - Rebuild index

### Querying
- `POST /v1/query` - AI-powered query processing

### Monitoring
- `GET /admin` - Admin dashboard
- `GET /v1/traces` - Request traces
- `GET /metrics` - Prometheus metrics

## 🧪 Testing

The comprehensive test suite validates:

1. **Authentication**: JWT token generation and validation
2. **Project Management**: Reading from proj_mapping.txt
3. **Query Processing**: Before and after document upload
4. **Document Upload**: Automatic indexing and retrieval
5. **AI Integration**: Context-aware responses

Run tests:
```bash
python test_kbai_comprehensive.py --standalone
```

## 📁 Project Structure

```
kbai-api/
├── app/                          # Main application
│   ├── main.py                  # FastAPI application with AI integration
│   ├── models.py                # Updated data models
│   ├── auth.py                  # Authentication logic
│   └── ...
├── data/                        # Data directory (moved from DARKBO)
│   ├── proj_mapping.txt         # Project configuration
│   ├── {project-id}/            # Project directories
│   │   ├── faqs/               # FAQ JSON files
│   │   ├── kb/                 # Knowledge base articles
│   │   └── ingest/             # Uploaded documents
│   └── indexes/                # AI search indexes
├── simple_ai_worker.py         # AI processing (DARKBO equivalent)
├── create_sample_data.py       # Sample data generation
├── run_api_unified.sh          # Combined startup script
├── test_kbai_comprehensive.py  # Full test suite
├── cleanup.py                  # Data cleanup utility
├── demo.sh                     # Complete demonstration
└── ASPCATest.docx              # Test document
```

## 🔍 How It Works

### 1. Document Processing
- Documents uploaded via `/v1/projects/{id}/ingest`
- Text extracted from .docx, .pdf, .txt, .html files
- Content indexed for similarity search

### 2. AI-Powered Querying
- Queries processed via `/v1/query`
- Text similarity matching finds relevant documents
- OpenAI integration provides context-aware responses
- Falls back to simple matching if OpenAI unavailable

### 3. Project Isolation
- Each project has isolated document storage
- Indexes rebuilt automatically after uploads
- Queries scoped to specific projects

### Sample Query Flow
```bash
# 1. Get authentication token
curl -X POST "http://localhost:8000/v1/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'

# 2. Query knowledge base
curl -X POST "http://localhost:8000/v1/query" \
  -H "Authorization: Bearer <token>" \
  -d '{"query": "How do I reset my password?", "project_id": "tech-support"}'
```

## 🔒 Security Features

- **JWT Authentication**: Scoped permissions and session management
- **API Key Support**: Programmatic access with full permissions
- **Request Tracing**: All requests logged with sensitive data scrubbed
- **Input Validation**: Pydantic models for all API inputs
- **CORS Configuration**: Configurable cross-origin policies

## 📊 Monitoring & Observability

- **Admin Dashboard**: Real-time metrics and request traces
- **Prometheus Metrics**: Standard metrics for monitoring
- **Health Checks**: `/healthz` and `/readyz` endpoints
- **Request Tracing**: Detailed logging of all API interactions

## 🧹 Cleanup

Remove all generated data:
```bash
python cleanup.py
```

## 🎯 DARKBO Integration Completed

This implementation successfully moves all DARKBO functionality into the secure kbai-api framework:

- ✅ AI worker functionality (`ai_worker.py` → `simple_ai_worker.py`)
- ✅ Sample data generation (`create_sample_data`)
- ✅ Document processing and indexing
- ✅ ASPCA test document and workflow
- ✅ Unified initialization script
- ✅ Comprehensive test validation
- ✅ Root directory structure
- ✅ Combined requirements and dependencies

All 8/8 comprehensive tests pass, validating the complete integration.

## 📞 Support

For issues or questions:
1. Check the test output: `python test_kbai_comprehensive.py --standalone`
2. Review API documentation: `http://localhost:8000/docs`
3. Check admin dashboard: `http://localhost:8000/admin`