#!/usr/bin/env bash
# scripts/bootstrap.sh — one-command project setup
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Secretary Harness Bootstrap ==="

echo "[1/6] Installing backend dependencies..."
cd "$PROJECT_ROOT/backend"
if [ ! -d "venv" ]; then
  python3 -m venv venv
  echo "  Created virtual environment"
fi
source venv/bin/activate
pip install -q -r requirements.txt
echo "  Backend dependencies installed"

echo "[2/6] Setting up environment..."
cd "$PROJECT_ROOT/backend"
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "  Copied .env.example → .env (edit with your credentials)"
else
  echo "  .env already exists, skipping"
fi

echo "[3/6] Installing mobile dependencies..."
cd "$PROJECT_ROOT/mobile"
if command -v flutter &>/dev/null; then
  flutter pub get
  echo "  Flutter dependencies installed"
else
  echo "  Flutter not found, skipping mobile setup"
fi

echo "[4/6] Setting up pre-commit hooks..."
cd "$PROJECT_ROOT"
if command -v pre-commit &>/dev/null; then
  pre-commit install
  echo "  Pre-commit hooks installed"
elif [ -f .pre-commit-config.yaml ]; then
  pip install pre-commit && pre-commit install
  echo "  Pre-commit installed and hooks set up"
else
  echo "  No pre-commit config found, skipping"
fi

echo "[5/6] Running database migrations..."
cd "$PROJECT_ROOT/backend"
source venv/bin/activate
if alembic upgrade head 2>/dev/null; then
  echo "  Migrations applied successfully"
else
  echo "  Migrations skipped (database not available)"
fi

echo "[6/6] Verifying setup..."
cd "$PROJECT_ROOT/backend"
source venv/bin/activate
if python -c "from src.main import app; print('  FastAPI app loads OK')"; then
  echo "  Backend verification passed"
else
  echo "  Backend verification failed — check .env and dependencies"
fi

echo ""
echo "Setup complete. Available commands:"
echo "  cd backend && uvicorn src.main:app --reload   — Start backend"
echo "  cd backend && pytest                          — Run backend tests"
echo "  cd mobile && flutter run                      — Start mobile app"
echo "  ./scripts/start.sh all                        — Start all services"
echo "  cd backend && black --check src/ && flake8 src/ && mypy src/  — Lint"
