# AIR MVP - AI-native Relationship Management System

An AI-powered relationship management platform that helps business professionals maintain and leverage their professional networks.

## Features

- **Relationship Graph**: Automatically build and visualize your professional network
- **AI Insights**: Get pre-meeting briefings and relationship intelligence
- **Smart Integrations**: Connect Gmail, Calendar, and LinkedIn
- **Privacy-First**: You own your data with full export capabilities
- **Interest Detection**: AI-powered analysis of contact interests and preferences

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker and Docker Compose
- PostgreSQL (via Docker)

### Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd air-mvp
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start the development environment**
   ```bash
   docker-compose up -d
   ```

4. **Set up the backend**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

5. **Set up the frontend**
   ```bash
   cd frontend
   npm install
   ```

6. **Run the application**
   ```bash
   # Backend (from backend/ directory)
   uvicorn main:app --reload

   # Frontend (from frontend/ directory)
   npm start
   ```

## Architecture

### Backend Structure
```
backend/
├── api/           # FastAPI routes and middleware
├── models/        # Database models and schemas
├── services/      # Business logic layer
├── workers/       # Background job processing
├── lib/           # Shared utilities and clients
├── migrations/    # Database migrations
├── tests/         # Test suite
└── scripts/       # Utility scripts
```

### Key Technologies

- **Backend**: FastAPI, SQLAlchemy, Celery, Redis
- **AI**: LangChain, LangGraph, OpenAI GPT-4
- **Database**: PostgreSQL, Weaviate (vector DB)
- **Frontend**: React, TypeScript, TailwindCSS
- **Infrastructure**: Docker, Docker Compose

## Development Workflow

1. **Phase 1**: Foundation & Infrastructure Setup ✅
2. **Phase 2**: Core Integrations (Gmail, Calendar, LinkedIn)
3. **Phase 3**: Data Processing & AI Pipeline
4. **Phase 4**: Core Features Implementation
5. **Phase 5**: Frontend Development
6. **Phase 6**: Monetization & Analytics
7. **Phase 7**: Testing & Quality Assurance
8. **Phase 8**: DevOps & Deployment
9. **Phase 9**: Documentation & Launch Prep

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests: `pytest backend/tests/`
4. Run linting: `pre-commit run --all-files`
5. Submit a pull request

## License

MIT License - see LICENSE file for details. 