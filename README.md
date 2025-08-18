# Reddit Ghost Publisher

Automated Reddit content collection and Ghost CMS publishing system with AI-powered content processing.

## Overview

Reddit Ghost Publisher is a microservices-based system that:
- Collects trending posts from Reddit
- Processes content using AI (GPT-4o, BERTopic)
- Automatically publishes to Ghost CMS
- Provides comprehensive monitoring and observability

## Architecture

- **FastAPI Gateway**: API endpoints and request routing
- **Celery Workers**: Asynchronous task processing
- **PostgreSQL**: Primary data storage
- **Redis**: Message queue and caching
- **HashiCorp Vault**: Secrets management

## Quick Start

### Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd reddit-ghost-publisher
   ```

2. **Copy environment configuration**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start services with Docker Compose**
   ```bash
   docker-compose up -d
   ```

4. **Access the application**
   - API: http://localhost:8000
   - Grafana: http://localhost:3000 (admin/admin)
   - Prometheus: http://localhost:9090

### Production Deployment

1. **Set environment variables**
   ```bash
   export DATABASE_URL="postgresql://user:pass@host:5432/db"
   export REDIS_URL="redis://host:6379/0"
   export VAULT_URL="https://vault.example.com"
   export VAULT_TOKEN="your-vault-token"
   ```

2. **Deploy with production compose**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

## Configuration

### Environment Variables

Key configuration options (see `.env.example` for full list):

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `VAULT_URL`: HashiCorp Vault URL
- `VAULT_TOKEN`: Vault authentication token

### Secrets Management

Production secrets are stored in HashiCorp Vault:

```
secret/
├── reddit/
│   ├── client_id
│   ├── client_secret
│   └── refresh_token
├── openai/
│   └── api_key
└── ghost/
    ├── admin_key
    └── content_key
```

## API Endpoints

### Health Check
```bash
GET /health
```

### Manual Triggers
```bash
POST /api/v1/collect/trigger
POST /api/v1/process/trigger
POST /api/v1/publish/trigger
```

### Status Monitoring
```bash
GET /api/v1/status/queues
GET /api/v1/status/workers
```

### Metrics
```bash
GET /metrics  # Prometheus metrics
```

## Development

### Local Development

1. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

3. **Run tests**
   ```bash
   pytest --cov=app --cov-report=html
   ```

4. **Code formatting**
   ```bash
   black .
   isort .
   flake8 .
   ```

### Testing

- **Unit Tests**: `pytest tests/unit/`
- **Integration Tests**: `pytest tests/integration/`
- **End-to-End Tests**: `pytest tests/e2e/`
- **Load Tests**: `locust -f tests/load/locustfile.py`

## Monitoring

### Metrics

The system exposes Prometheus metrics for:
- API request rates and latencies
- Queue depths and processing rates
- External API usage (Reddit, OpenAI, Ghost)
- System resources (CPU, memory, disk)

### Dashboards

Grafana dashboards are available for:
- System Overview
- Application Metrics
- Queue Monitoring
- Business Metrics

### Alerting

Alerts are configured for:
- High queue depths
- API rate limit approaching
- High token usage
- System resource exhaustion

## Security

- TLS encryption with Let's Encrypt certificates
- JWT-based API authentication
- Secrets stored in HashiCorp Vault
- Rate limiting and CORS protection
- Regular security scanning with Bandit and Safety

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Support

For issues and questions:
- Create an issue on GitHub
- Check the documentation in `/docs`
- Review the troubleshooting guide