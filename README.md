# KBAI API

A professional Knowledge Base AI API built with FastAPI, featuring JWT authentication, request tracing, project management, and a comprehensive dashboard.

## ✨ Features

- **🔐 JWT Authentication** - Secure token-based authentication with session management
- **📊 Request Tracing** - Comprehensive logging of all API requests and responses
- **📈 Metrics & Monitoring** - Prometheus metrics and performance monitoring
- **🗂️ Project Management** - Create and manage knowledge base projects
- **❓ FAQ Management** - Add, update, and manage frequently asked questions
- **📚 Knowledge Base** - Store and organize knowledge base articles
- **📁 File Ingestion** - Upload and process various file formats
- **🎯 Query Processing** - AI-powered query processing (extensible)
- **📱 Admin Dashboard** - Web-based administration interface
- **🏗️ SQLite Database** - Simple, reliable SQLite3 database storage

## 🚀 Quick Start

### Prerequisites

- Python 3.8+ 
- SQLite3

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd kbai-api
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment** (optional)
   ```bash
   cp .env.example .env
   # Edit .env with your preferred settings
   ```

4. **Initialize the database**
   ```bash
   ./init_db.sh
   ```

5. **Start the API server**
   ```bash
   ./run_api.sh
   ```

The API will be available at `http://localhost:8000`

## 📚 API Documentation

Once the server is running, you can access:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc  
- **Admin Dashboard**: http://localhost:8000/admin

## 🔑 Authentication

### Getting a Token

```bash
curl -X POST http://localhost:8000/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin",
    "client_name": "my-client",
    "scopes": ["read:basic", "write:projects"],
    "ttl_seconds": 3600
  }'
```

### Using the Token

```bash
curl -H "Authorization: Bearer <your-token>" \
  http://localhost:8000/v1/test/ping
```

## 🗄️ Database

The API uses SQLite3 for data storage with the following tables:

- **sessions** - JWT session management
- **traces** - Request/response logging and monitoring

The database is automatically created and initialized by the `init_db.sh` script.

## 🛠️ Configuration

### Environment Variables

All configuration is done through environment variables. See `.env.example` for available options:

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | Server port |
| `HOST` | `0.0.0.0` | Server host |
| `TRACE_DB_PATH` | `./app/kbai_api.db` | Database file path |
| `AUTH_SIGNING_KEY` | `dev-signing-key-change-me` | JWT signing key |
| `MAX_REQUEST_BYTES` | `65536` | Maximum request body size |
| `ALLOWED_ORIGINS` | `*` | CORS allowed origins |

## 🏗️ Project Structure

```
kbai-api/
├── app/                    # Main application directory
│   ├── main.py            # FastAPI application
│   ├── models.py          # Pydantic models
│   ├── auth.py            # Authentication logic
│   ├── storage.py         # Database operations
│   ├── middleware.py      # Request middleware
│   ├── templates/         # HTML templates
│   └── schema.sql         # Database schema
├── init_db.sh             # Database initialization script
├── run_api.sh             # Application run script
├── requirements.txt       # Python dependencies
├── .env.example          # Environment configuration example
└── README.md             # This file
```

## 📊 API Endpoints

### Authentication
- `POST /v1/auth/token` - Get JWT token

### Testing
- `GET /v1/test/ping` - Test authenticated access

### Observability
- `GET /v1/traces` - List request traces
- `GET /v1/metrics/summary` - Get metrics summary
- `GET /metrics` - Prometheus metrics
- `GET /healthz` - Health check
- `GET /readyz` - Readiness check

### Projects
- `GET /v1/projects` - List all projects
- `POST /v1/projects` - Create/update project
- `GET /v1/projects/{id}` - Get project details
- `DELETE /v1/projects/{id}` - Deactivate project

### FAQs
- `GET /v1/projects/{id}/faqs` - List project FAQs
- `POST /v1/projects/{id}/faqs:batch_upsert` - Batch upsert FAQs
- `DELETE /v1/projects/{id}/faqs/{faq_id}` - Delete FAQ

### Knowledge Base
- `GET /v1/projects/{id}/kb` - List KB articles
- `POST /v1/projects/{id}/kb:batch_upsert` - Batch upsert articles
- `DELETE /v1/projects/{id}/kb/{kb_id}` - Delete article

### File Management
- `POST /v1/projects/{id}/ingest` - Upload files
- `POST /v1/projects/{id}/reindex` - Trigger reindexing

### Querying
- `POST /v1/query` - Query knowledge base

## 🔧 Development

### Running in Development Mode

```bash
# Enable auto-reload for development
RELOAD=true ./run_api.sh
```

### Database Management

```bash
# Reinitialize database (WARNING: destroys all data)
./init_db.sh

# Connect to database directly
sqlite3 ./app/kbai_api.db
```

## 🔒 Security

- JWT tokens are used for authentication
- All requests are logged and traced
- Sensitive headers are scrubbed from logs
- Request body size limits prevent abuse
- CORS is configurable for security

## 📈 Monitoring

The API includes comprehensive monitoring:

- **Request Tracing**: Every request is logged with timing, status, and metadata
- **Prometheus Metrics**: Built-in metrics for monitoring and alerting
- **Health Checks**: `/healthz` and `/readyz` endpoints for health monitoring
- **Dashboard**: Web-based admin interface for monitoring and management

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

[Add your license information here]

## 🆘 Support

For support and questions:

1. Check the API documentation at `/docs`
2. Review the logs in the database traces
3. Open an issue in the repository

---

**Note**: Change the default authentication credentials and JWT signing key in production!