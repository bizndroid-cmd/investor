# Contributing Guide

## Branch Strategy

```
main            → Production (auto-deploys to AWS)
  └── staging   → Pre-production testing (optional)
      └── dev   → Integration branch
          └── feature/*   → New features
          └── hotfix/*    → Emergency production fixes
          └── bugfix/*    → Non-urgent bug fixes
```

## Workflow

### Starting a new feature:
```bash
git checkout dev
git pull origin dev
git checkout -b feature/your-feature-name
# ... make changes ...
git commit -m "feat: description of change"
git push -u origin feature/your-feature-name
# Create PR: feature/your-feature-name → dev
```

### Commit Message Convention:
```
feat: add new feature
fix: bug fix
docs: documentation changes
refactor: code restructuring (no behavior change)
perf: performance improvement
test: adding/fixing tests
chore: maintenance (deps, config, CI)
hotfix: urgent production fix
```

### Pull Request Process:
1. Create PR from `feature/*` → `dev`
2. Fill in the PR template (description, testing, screenshots)
3. Request review from at least 1 team member
4. All CI checks must pass (lint, build, tests)
5. Squash merge into `dev`
6. When ready for production: merge `dev` → `main`

### Release Process:
1. Update `VERSION` file with new version number
2. Update `CHANGELOG.md` with changes
3. Merge `dev` → `main`
4. Tag the release: `git tag v1.x.x && git push --tags`
5. Deploy triggers automatically (or manual via `./deploy.sh`)

## Development Setup

```bash
# Clone
git clone git@github.com:bizndroid-cmd/investor.git
cd investor

# Backend
pip install -r backend/requirements.txt
cp .env.example .env  # Edit with your keys

# Frontend
cd frontend && npm install

# Run locally
PYTHONPATH=. python -m uvicorn backend.main:app --reload --port 8000
cd frontend && npm run dev
```

## Environment Variables

All secrets go in `.env` (never committed). See `.env.production` for required variables.

## Database Migrations

```bash
# Create new migration
cd backend && alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

## Code Standards

- Python: Type hints required, async/await for all I/O
- TypeScript: Strict mode, no `any` types
- CSS: Tailwind utility classes only
- All API responses: Pydantic models (backend) / TypeScript interfaces (frontend)

## Security Rules

- Never commit secrets (API keys, tokens, passwords)
- All sensitive values via environment variables
- Use parameterized queries (SQLAlchemy ORM handles this)
- JWT tokens expire in 15 minutes (access) / 7 days (refresh)
