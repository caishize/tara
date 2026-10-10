#!/bin/bash
# Start the API Server (FastAPI/uvicorn)
#
# Usage:
#   ./scripts/start-server.sh              # development (auto-reload, agent worker in-process)
#   ./scripts/start-server.sh --prod       # production  (no reload, no in-process worker)
#   ./scripts/start-server.sh --port 8080  # custom port
#   ./scripts/start-server.sh --fg         # foreground mode (no log file, attach to terminal)
#
# On each start, any existing API server process (from a previous run) is killed first.
# Logs are written to logs/server.log (unless --fg is used).
#
# Environment variables:
#   PORT                        - Server port (default: 8000)
#   WORKERS                     - Number of uvicorn workers (default: 1 dev, 4 prod)
#   RUN_AGENT_WORKER_IN_PROCESS - "true" to embed Agent Worker (default: true in dev)

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
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-}"
FOREGROUND=false
ACTION="start"
PIDFILE="$BACKEND_DIR/.server.pid"
LOGFILE="$BACKEND_DIR/logs/server.log"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --prod|--production)
            MODE="prod"
            shift
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --workers)
            WORKERS="$2"
            shift 2
            ;;
        --fg|--foreground)
            FOREGROUND=true
            shift
            ;;
        --stop)
            ACTION="stop"
            shift
            ;;
        --check)
            ACTION="check"
            shift
            ;;
        *)
            echo -e "${YELLOW}Unknown option: $1${NC}"
            echo "Usage: $0 [--prod] [--port PORT] [--workers N] [--fg] [--stop] [--check]"
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
    echo -e "${YELLOW}Stopping existing API server (PID $pid)...${NC}"
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 15); do
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
        echo -e "${GREEN}API Server is running (PID $pid)${NC}"
        exit 0
    }
    echo -e "${YELLOW}API Server is NOT running${NC}"
    exit 1
fi

# ── ACTION: stop ─────────────────────────────────────────────────────
if [ "$ACTION" = "stop" ]; then
    _kill_existing
    exit 0
fi

# ── Activate venv ────────────────────────────────────────────────────
if [ -z "$VIRTUAL_ENV" ] && [ -d "venv" ]; then
    source venv/bin/activate
fi

# ── Kill any existing instance ───────────────────────────────────────
_kill_existing

# ── Prepare settings ─────────────────────────────────────────────────
if [ "$MODE" = "prod" ]; then
    WORKERS="${WORKERS:-4}"
    export RUN_AGENT_WORKER_IN_PROCESS="${RUN_AGENT_WORKER_IN_PROCESS:-false}"
    export DEBUG="${DEBUG:-false}"
else
    WORKERS="${WORKERS:-1}"
    export RUN_AGENT_WORKER_IN_PROCESS="${RUN_AGENT_WORKER_IN_PROCESS:-true}"
fi

echo -e "${BLUE}=== Secretary API Server ===${NC}"
echo -e "Mode:       ${GREEN}${MODE}${NC}"
echo -e "Port:       ${GREEN}${PORT}${NC}"
echo -e "Workers:    ${GREEN}${WORKERS}${NC}"
echo -e "In-process: ${GREEN}${RUN_AGENT_WORKER_IN_PROCESS}${NC}"

# ── Build command ────────────────────────────────────────────────────
CMD_ARGS=(
    uvicorn src.main:app
    --host 0.0.0.0
    --port "$PORT"
)

if [ "$MODE" = "prod" ]; then
    CMD_ARGS+=(--workers "$WORKERS" --log-level info)
else
    CMD_ARGS+=(--reload)
fi

# ── Start ────────────────────────────────────────────────────────────
if [ "$FOREGROUND" = true ]; then
    echo -e "Log:        ${GREEN}(stdout)${NC}"
    echo ""
    echo $$ > "$PIDFILE"
    trap 'rm -f "$PIDFILE"' EXIT
    exec "${CMD_ARGS[@]}"
else
    mkdir -p "$(dirname "$LOGFILE")"
    echo -e "Log:        ${GREEN}${LOGFILE}${NC}"
    echo -e "PID file:   ${GREEN}${PIDFILE}${NC}"
    echo ""

    nohup "${CMD_ARGS[@]}" >> "$LOGFILE" 2>&1 &
    local_pid=$!
    echo "$local_pid" > "$PIDFILE"

    sleep 1
    if _is_running "$local_pid"; then
        echo -e "${GREEN}API server started (PID $local_pid).${NC}"
        echo -e "Tail log: ${BLUE}tail -f $LOGFILE${NC}"
    else
        echo -e "${RED}API server failed to start. Check $LOGFILE${NC}"
        rm -f "$PIDFILE"
        exit 1
    fi
fi
