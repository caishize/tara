#!/bin/bash
# Start development server for Secretary backend

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Secretary Backend Development Server ===${NC}\n"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Warning: Virtual environment not found${NC}"
    echo "Run: python -m venv venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment if not already activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${BLUE}Activating virtual environment...${NC}"
    source .venv/bin/activate
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo "Creating .env from .env.example..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}Created .env file. Please update it with your settings.${NC}"
    else
        echo -e "${YELLOW}Please create .env file manually${NC}"
    fi
fi

# Check database connection
echo -e "${BLUE}Checking database connection...${NC}"
python -c "
import asyncio
from src.db.session import engine

async def check_db():
    try:
        async with engine.connect() as conn:
            await conn.execute('SELECT 1')
        print('✓ Database connection successful')
        return True
    except Exception as e:
        print(f'✗ Database connection failed: {e}')
        return False

if not asyncio.run(check_db()):
    exit(1)
" || {
    echo -e "${YELLOW}Database not accessible. Please ensure PostgreSQL is running.${NC}"
    exit 1
}

# Run migrations
echo -e "${BLUE}Running database migrations...${NC}"
cd src && alembic upgrade head && cd ..
echo -e "${GREEN}✓ Migrations complete${NC}\n"

# Start server
PORT=${1:-8000}
RELOAD=${2:-"reload"}

echo -e "${GREEN}Starting development server on port ${PORT}...${NC}"
echo -e "${BLUE}API Docs: http://localhost:${PORT}/docs${NC}"
echo -e "${BLUE}Health Check: http://localhost:${PORT}/health${NC}\n"

if [ "$RELOAD" = "reload" ]; then
    uvicorn src.main:app --host 0.0.0.0 --port $PORT --reload
else
    uvicorn src.main:app --host 0.0.0.0 --port $PORT
fi
