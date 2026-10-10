#!/bin/bash
# Start ALL processes for local development (using background jobs)
#
# Usage:
#   ./scripts/start-all-dev.sh           # API + Celery Worker + Beat (Agent Worker in-process)
#   ./scripts/start-all-dev.sh --split   # API + Celery Worker + Beat + Agent Worker (separate)
#
# Press Ctrl+C to stop all processes.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$BACKEND_DIR"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SPLIT_AGENT=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --split)
            SPLIT_AGENT=true
            shift
            ;;
        *)
            echo -e "${YELLOW}Unknown option: $1${NC}"
            echo "Usage: $0 [--split]"
            exit 1
            ;;
    esac
done

# Activate venv if available and not already active
if [ -z "$VIRTUAL_ENV" ] && [ -d "venv" ]; then
    source venv/bin/activate
fi

# Track child PIDs for cleanup
PIDS=()

cleanup() {
    echo ""
    echo -e "${YELLOW}Stopping all processes...${NC}"
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done
    # Wait briefly, then force kill stragglers
    sleep 2
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
    echo -e "${GREEN}All processes stopped.${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

echo -e "${BLUE}=== Secretary Development Environment ===${NC}"
echo ""

# 1. API Server
if [ "$SPLIT_AGENT" = true ]; then
    export RUN_AGENT_WORKER_IN_PROCESS=false
    echo -e "${GREEN}[API Server]${NC} Starting (Agent Worker runs separately)..."
else
    export RUN_AGENT_WORKER_IN_PROCESS=true
    echo -e "${GREEN}[API Server]${NC} Starting (Agent Worker in-process)..."
fi

uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload &
PIDS+=($!)
echo -e "  PID: $!"

# 2. Celery Worker
echo -e "${GREEN}[Celery Worker]${NC} Starting..."
celery -A src.celery_app worker \
    --queues default,secretary,assistant \
    --concurrency 2 \
    --loglevel info \
    --hostname "dev-worker@%h" &
PIDS+=($!)
echo -e "  PID: $!"

# 3. Celery Beat
echo -e "${GREEN}[Celery Beat]${NC} Starting..."
celery -A src.celery_app beat --loglevel info &
PIDS+=($!)
echo -e "  PID: $!"

# 4. Agent Worker (only if --split)
if [ "$SPLIT_AGENT" = true ]; then
    echo -e "${GREEN}[Agent Worker]${NC} Starting (standalone)..."
    python -m src.ai_engine.worker_main &
    PIDS+=($!)
    echo -e "  PID: $!"
fi

echo ""
echo -e "${BLUE}All processes started. Press Ctrl+C to stop.${NC}"
echo -e "${BLUE}API Docs: http://localhost:8000/docs${NC}"
echo ""

# Wait for any child to exit (usually means something crashed)
wait -n "${PIDS[@]}" 2>/dev/null || true

# If we get here, a process died unexpectedly
echo -e "${RED}A process exited unexpectedly. Shutting down all...${NC}"
cleanup
