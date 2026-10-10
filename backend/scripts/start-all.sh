#!/bin/bash
# Start ALL backend services (API Server + Agent Worker + Celery Worker + Celery Beat)
#
# Usage:
#   ./scripts/start-all.sh              # start all 4 services (background, logs to files)
#   ./scripts/start-all.sh --prod       # production mode
#   ./scripts/start-all.sh --stop       # stop all services
#   ./scripts/start-all.sh --status     # check status of all services
#
# Each service logs to its own file under logs/:
#   logs/server.log
#   logs/agent-worker.log
#   logs/celery-worker.log
#   logs/celery-beat.log
#
# Each service is managed by its own PID file and can be restarted independently.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$BACKEND_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

MODE_ARGS=()
ACTION="start"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --prod|--production)
            MODE_ARGS+=(--prod)
            shift
            ;;
        --stop)
            ACTION="stop"
            shift
            ;;
        --status|--check)
            ACTION="status"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --prod      Run all services in production mode"
            echo "  --stop      Stop all running services"
            echo "  --status    Check status of all services"
            echo "  -h, --help  Show this help"
            echo ""
            echo "Services:"
            echo "  1. API Server       (uvicorn)           → logs/server.log"
            echo "  2. Agent Worker     (worker_main)       → logs/agent-worker.log"
            echo "  3. Celery Worker    (celery worker)     → logs/celery-worker.log"
            echo "  4. Celery Beat      (celery beat)       → logs/celery-beat.log"
            exit 0
            ;;
        *)
            echo -e "${YELLOW}Unknown option: $1${NC}"
            echo "Usage: $0 [--prod] [--stop] [--status]"
            exit 1
            ;;
    esac
done

echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     Secretary Backend Services           ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── STATUS ───────────────────────────────────────────────────────────
if [ "$ACTION" = "status" ]; then
    "$SCRIPT_DIR/start-server.sh" --check 2>/dev/null && true
    "$SCRIPT_DIR/start-agent-worker.sh" --check 2>/dev/null && true
    "$SCRIPT_DIR/start-celery-worker.sh" --check 2>/dev/null && true
    "$SCRIPT_DIR/start-celery-beat.sh" --check 2>/dev/null && true
    exit 0
fi

# ── STOP ALL ─────────────────────────────────────────────────────────
if [ "$ACTION" = "stop" ]; then
    echo -e "${YELLOW}Stopping all services...${NC}"
    echo ""
    "$SCRIPT_DIR/start-server.sh" --stop 2>/dev/null && true
    "$SCRIPT_DIR/start-agent-worker.sh" --stop 2>/dev/null && true
    "$SCRIPT_DIR/start-celery-worker.sh" --stop 2>/dev/null && true
    "$SCRIPT_DIR/start-celery-beat.sh" --stop 2>/dev/null && true
    echo ""
    echo -e "${GREEN}All services stopped.${NC}"
    exit 0
fi

# ── START ALL ────────────────────────────────────────────────────────
# Note: start-server.sh in prod mode disables in-process worker,
# so we always start the Agent Worker as a separate process here.
if [[ " ${MODE_ARGS[*]} " =~ " --prod " ]]; then
    export RUN_AGENT_WORKER_IN_PROCESS=false
fi

echo -e "${BLUE}[1/4] API Server${NC}"
"$SCRIPT_DIR/start-server.sh" "${MODE_ARGS[@]}"
echo ""

echo -e "${BLUE}[2/4] Agent Worker${NC}"
"$SCRIPT_DIR/start-agent-worker.sh" "${MODE_ARGS[@]}"
echo ""

echo -e "${BLUE}[3/4] Celery Worker${NC}"
"$SCRIPT_DIR/start-celery-worker.sh" "${MODE_ARGS[@]}"
echo ""

echo -e "${BLUE}[4/4] Celery Beat${NC}"
"$SCRIPT_DIR/start-celery-beat.sh" "${MODE_ARGS[@]}"
echo ""

echo -e "${CYAN}══════════════════════════════════════════${NC}"
echo -e "${GREEN}All 4 services started.${NC}"
echo ""
echo -e "Log files:"
echo -e "  ${BLUE}tail -f logs/server.log${NC}"
echo -e "  ${BLUE}tail -f logs/agent-worker.log${NC}"
echo -e "  ${BLUE}tail -f logs/celery-worker.log${NC}"
echo -e "  ${BLUE}tail -f logs/celery-beat.log${NC}"
echo ""
echo -e "All logs:  ${BLUE}tail -f logs/*.log${NC}"
echo -e "Stop all:  ${BLUE}$0 --stop${NC}"
echo -e "Status:    ${BLUE}$0 --status${NC}"
