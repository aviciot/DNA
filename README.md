# DNA ISO Certification Dashboard

## Overview
Modern SPA dashboard for managing ISO certification workflows with AI-assisted document completion and customer tracking.

🎯 **Current Status:** Foundation complete and ready for use!

## Features
- ✅ Secure JWT authentication with role-based access control
- ✅ Modern, responsive UI with gradient design
- ✅ WebSocket chat with Claude 4.5 AI assistant
- ✅ Real-time dashboard statistics
- ✅ PostgreSQL with two-schema architecture
- ✅ Docker-based deployment
- 🚧 ISO template management (coming soon)
- 🚧 Customer workflow tracking (coming soon)
- 🚧 AI-powered document analysis (coming soon)

## Architecture
- **Frontend:** Next.js 14+ with TypeScript, Tailwind CSS v3
- **Backend:** FastAPI with WebSocket support, async operations
- **Auth:** Dedicated authentication service with JWT
- **Database:** PostgreSQL 16 with schemas (auth, dna_app)
- **AI:** Claude 4.5 Sonnet integration via streaming

## Quick Start

### Prerequisites
- Docker Desktop (Windows/Mac) or Docker Engine + docker-compose (Linux)
- Claude API key from [Anthropic Console](https://console.anthropic.com/)

### Installation

1. **Clone or navigate to project directory:**
```bash
cd "C:\Users\acohen.SHIFT4CORP\Desktop\PythonProjects\MCP Performance\DNA"
```

2. **Configuration:**
   - ✅ Anthropic API key is already configured (copied from omni2)
   - No additional setup needed!

3. **Start services:**
   - **Windows:** Double-click `start.bat`
   - **Linux/Mac:** Run `docker-compose up -d`

4. **Wait for initialization (30-60 seconds)**

5. **Access the dashboard:**
   - Open browser: [http://localhost:3003](http://localhost:3003)
   - Login with defaults:
     - Email: `admin@dna.local`
     - Password: `admin123`

### Access Points
- **Frontend Dashboard:** [http://localhost:3003](http://localhost:3003)
- **Backend API:** [http://localhost:8400](http://localhost:8400)
  - Docs: [http://localhost:8400/docs](http://localhost:8400/docs)
- **Auth Service:** [http://localhost:8401](http://localhost:8401)
  - Docs: [http://localhost:8401/docs](http://localhost:8401/docs)
- **Database:** localhost:5432 (dna / dna_user / dna_password_dev)

## Project Structure
```
DNA/
├── dashboard/
│   ├── frontend/          # Next.js SPA
│   │   ├── src/
│   │   │   ├── app/           # Pages (login, dashboard)
│   │   │   ├── lib/           # API client
│   │   │   ├── stores/        # State management
│   │   │   └── types/         # TypeScript definitions
│   │   └── package.json
│   └── backend/           # FastAPI backend
│       └── app/
│           ├── main.py       # API entry point
│           ├── chat.js       # Claude WebSocket service
│           ├── auth.py       # Auth middleware
│           └── config.py     # Configuration
├── auth_service/          # JWT authentication service
│   ├── main.py
│   ├── routes/           # Login, logout, verify
│   ├── services/         # Token, password, user services
│   └── models/           # Pydantic schemas
├── db/init/              # Database initialization
│   └── 01-init.sql       # Schema + seed data
├── docker-compose.yml    # Service orchestration
├── .env                  # Environment configuration
├── rules.md              # Architecture documentation
└── progress.md           # Development progress tracker
```

## User Roles
- **admin:** Full access to all features, templates, configuration, AI chat
- **viewer:** Read-only access to customers, documents, and reports

## API Documentation

### Authentication Endpoints (Port 8401)
```
POST   /api/v1/auth/login    - Login with email/password
POST   /api/v1/auth/logout   - Logout and revoke token
POST   /api/v1/auth/refresh  - Refresh access token
GET    /api/v1/auth/verify   - Verify token validity
GET    /api/v1/users/me      - Get current user info
```

### Backend Endpoints (Port 8400)
```
GET    /api/v1/dashboard/stats  - Dashboard statistics
GET    /api/v1/config/admin     - Admin configuration (admin only)
WS     /ws/chat?token=<jwt>     - WebSocket chat with Claude
GET    /health                  - Health check
```

## Development

### Frontend Development (Local)
```bash
cd dashboard/frontend
npm install
npm run dev
# Accessible at http://localhost:3003
```

### Backend Development (Local)
```bash
cd dashboard/backend
pip install -r requirements.txt
python -m app.main
# Accessible at http://localhost:8400
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f dna-frontend
docker-compose logs -f dna-backend
docker-compose logs -f dna-auth
docker-compose logs -f dna-postgres
```

### Stop Services
```bash
docker-compose down           # Stop services
docker-compose down -v        # Stop and remove volumes (reset database)
```

## Security Features
- ✅ JWT token authentication with refresh tokens
- ✅ Bcrypt password hashing (12 rounds)
- ✅ HTTP-only secure cookie support
- ✅ CORS protection with whitelisted origins
- ✅ SQL injection prevention (parameterized queries)
- ✅ XSS protection with CSP headers
- ✅ Token expiration and automatic refresh
- ✅ Role-based access control (RBAC)

## Database Schema

### auth schema
- `users` - User accounts with roles
- `sessions` - Active JWT sessions
- `roles` - Role definitions and permissions

### dna_app schema
- `iso_templates` - ISO certificate templates
- `customers` - Customer information
- `documents` - Document tracking and completion
- `ai_tasks` - AI-generated tasks and alerts
- `conversations` - Chat history with Claude

## Troubleshooting

### Services won't start
```bash
# Check Docker is running
docker --version

# Check for port conflicts (DNA uses 3003, 8400, 8401, 5432)
netstat -ano | findstr "3003 8400 8401 5432"

# Reset everything
docker-compose down -v
docker-compose up -d --build
```

### Database connection errors
- Wait 30-60 seconds for PostgreSQL initialization
- Check logs: `docker-compose logs dna-postgres`
- Verify credentials in `.env` file

### Authentication errors
- Ensure JWT secret keys match in auth service and backend
- Check auth service is running: `curl http://localhost:8401/health`
- Clear browser localStorage and try again

### Claude API errors
- ✅ API key is already configured from omni2 project
- Check API key is still valid at [Anthropic Console](https://console.anthropic.com/)
- Review backend logs: `docker-compose logs dna-backend`

## Documentation
- **rules.md** - Complete architecture, connections, and technical rules (ALWAYS keep updated!)
- **progress.md** - Current development status and roadmap (ALWAYS keep updated!)
- **NO other markdown files allowed per project rules**

## Next Steps (Planned Features)
1. Draggable chat widget with conversation history
2. ISO template builder and management
3. Customer onboarding workflow
4. Document completion tracking with AI
5. AI-powered missing information detection
6. Automated email requests to customers
7. Review escalation workflow
8. Admin configuration panel
9. Dev mode debugging tools

## Tech Stack
- **Frontend:** Next.js 14, React 18, TypeScript 5, Tailwind CSS 3, Zustand
- **Backend:** FastAPI 0.104, Python 3.11, AsyncPG, Claude SDK
- **Database:** PostgreSQL 16, asyncpg driver
- **Auth:** JWT (python-jose), bcrypt, httpOnly cookies
- **Deployment:** Docker, docker-compose
- **AI:** Anthropic Claude 4.5 Sonnet via streaming API

## License
Proprietary - All rights reserved

## Support
For questions or issues:
1. Check [progress.md](progress.md) for known issues
2. Review logs: `docker-compose logs`
3. Verify configuration in `.env` file
4. Contact development team

---

**Built with ❤️ for ISO certification excellence**
