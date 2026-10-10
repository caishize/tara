#!/bin/bash
# Start the Agent Worker as a standalone process
#
# Usage:
#   ./scripts/start-agent-worker.sh              # Start in dev mode (background)
#   ./scripts/start-agent-worker.sh --prod        # Start in prod mode
#   ./scripts/start-agent-worker.sh --fg          # Foreground mode (attach to terminal)
#   ./scripts/start-agent-worker.sh --check       # Check if worker is running
#   ./scripts/start-agent-worker.sh --stop        # Stop the running worker
#
# On each start, any existing worker process is killed first.
# Logs are written to logs/agent-worker.log (unless --fg is used).
#
# Environment variables:
#   WORKER_MAX_CONCURRENT_TASKS - Max parallel tasks (default: 3)
#   WORKER_TASK_TIMEOUT_SECONDS - Per-task timeout (default: 300)
#   SDK_CLIENT_POOL_ENABLED     - Enable SDK client pooling (default: true)
#   SDK_CLIENT_POOL_MAX_CLIENTS - Max pooled clients (default: 50)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$BACKEND_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Defaults
MODE="dev"
FOREGROUND=false
ACTION="start"
PIDFILE="$BACKEND_DIR/.agent-worker.pid"
LOGFILE="$BACKEND_DIR/logs/agent-worker.log"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --prod|--production)
            MODE="prod"
            shift
            ;;
        --fg|--foreground)
            FOREGROUND=true
            shift
            ;;
        --check)
            ACTION="check"
            shift
            ;;
        --stop)
            ACTION="stop"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --prod          Run in production mode"
            echo "  --fg            Run in foreground (attach to terminal)"
            echo "  --check         Check if worker is running"
            echo "  --stop          Stop the running worker (SIGTERM)"
            echo "  -h, --help      Show this help"
            exit 0
            ;;
        *)
            echo -e "${YELLOW}Unknown option: $1${NC}"
            echo "Usage: $0 [--prod] [--fg] [--check] [--stop]"
            exit 1
            ;;
    esac
done

# ── Helpers ───────────────────────────────────────────────────────────
_is_running() {
    local pid="$1"
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

_get_running_pid() {
    if [ -f "$PIDFILE" ]; then
        local pid
        pid=$(cat "$PIDFILE" 2>/dev/null)
        if _is_running "$pid"; then
            echo "$pid"
            return 0
        fi
        rm -f "$PIDFILE"
    fi
    return 1
}

_kill_existing() {
    local pid
    pid=$(_get_running_pid) || return 0
    echo -e "${YELLOW}Stopping existing Agent Worker (PID $pid)...${NC}"
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 30); do
        if ! _is_running "$pid"; then break; fi
        sleep 1
    done
    if _is_running "$pid"; then
        echo -e "${RED}Force killing (PID $pid)...${NC}"
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PIDFILE"
    echo -e "${GREEN}Existing process stopped.${NC}"
}

# ── ACTION: check ────────────────────────────────────────────────────
if [ "$ACTION" = "check" ]; then
    pid=$(_get_running_pid) && {
        echo -e "${GREEN}Agent Worker is running (PID $pid)${NC}"
        exit 0
    }
    echo -e "${YELLOW}Agent Worker is NOT running${NC}"
    exit 1
fi

# ── ACTION: stop ─────────────────────────────────────────────────────
if [ "$ACTION" = "stop" ]; then
    _kill_existing
    exit 0
fi

# ── ACTION: start ────────────────────────────────────────────────────

# Activate venv if available and not already active
if [ -z "$VIRTUAL_ENV" ] && [ -d "venv" ]; then
    source venv/bin/activate
fi

# Kill any existing instance first
_kill_existing

# Ensure the API server does NOT also start an in-process worker
export RUN_AGENT_WORKER_IN_PROCESS=false

echo -e "${BLUE}=== Secretary Agent Worker ===${NC}"
echo -e "Mode:            ${GREEN}${MODE}${NC}"
echo -e "Max Concurrent:  ${GREEN}${WORKER_MAX_CONCURRENT_TASKS:-3}${NC}"
echo -e "Task Timeout:    ${GREEN}${WORKER_TASK_TIMEOUT_SECONDS:-300}s${NC}"
echo -e "SDK Pool:        ${GREEN}${SDK_CLIENT_POOL_ENABLED:-true}${NC}"

if [ "$FOREGROUND" = true ]; then
    echo -e "Log:             ${GREEN}(stdout)${NC}"
    echo ""
    echo $$ > "$PIDFILE"
    trap 'rm -f "$PIDFILE"' EXIT
    exec python -m src.ai_engine.worker_main
else
    mkdir -p "$(dirname "$LOGFILE")"
    echo -e "Log:             ${GREEN}${LOGFILE}${NC}"
    echo -e "PID file:        ${GREEN}${PIDFILE}${NC}"
    echo ""

    nohup python -m src.ai_engine.worker_main >> "$LOGFILE" 2>&1 &
    local_pid=$!
    echo "$local_pid" > "$PIDFILE"

    sleep 1
    if _is_running "$local_pid"; then
        echo -e "${GREEN}Agent Worker started (PID $local_pid).${NC}"
        echo -e "Tail log: ${BLUE}tail -f $LOGFILE${NC}"
    else
        echo -e "${RED}Agent Worker failed to start. Check $LOGFILE${NC}"
        rm -f "$PIDFILE"
        exit 1
    fi
fi
