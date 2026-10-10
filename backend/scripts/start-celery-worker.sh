#!/bin/bash
# Start Celery Worker
#
# Usage:
#   ./scripts/start-celery-worker.sh                  # all queues (background)
#   ./scripts/start-celery-worker.sh --queue assistant # specific queue only
#   ./scripts/start-celery-worker.sh --prod            # production settings
#   ./scripts/start-celery-worker.sh --fg              # foreground mode
#   ./scripts/start-celery-worker.sh --stop            # stop running worker
#
# On each start, any existing Celery worker (from a previous run) is killed first.
# Logs are written to logs/celery-worker.log (unless --fg is used).
#
# Environment variables:
#   CELERY_CONCURRENCY - Worker concurrency (default: 2 dev, 4 prod)
#   CELERY_QUEUES      - Comma-separated queue names (default: all)
#   CELERY_LOG_LEVEL   - Log level (default: info)

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
CONCURRENCY="${CELERY_CONCURRENCY:-}"
QUEUES="${CELERY_QUEUES:-default,secretary,assistant}"
LOG_LEVEL="${CELERY_LOG_LEVEL:-info}"
PIDFILE="$BACKEND_DIR/.celery-worker.pid"
LOGFILE="$BACKEND_DIR/logs/celery-worker.log"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --prod|--production)
            MODE="prod"
            shift
            ;;
        --queue|-Q)
            QUEUES="$2"
            shift 2
            ;;
        --concurrency|-c)
            CONCURRENCY="$2"
            shift 2
            ;;
        --log-level)
            LOG_LEVEL="$2"
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
            echo "Usage: $0 [--prod] [--queue QUEUES] [--concurrency N] [--log-level LEVEL] [--fg] [--stop]"
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
    echo -e "${YELLOW}Stopping existing Celery Worker (PID $pid)...${NC}"
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
        echo -e "${GREEN}Celery Worker is running (PID $pid)${NC}"
        exit 0
    }
    echo -e "${YELLOW}Celery Worker is NOT running${NC}"
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

if [ "$MODE" = "prod" ]; then
    CONCURRENCY="${CONCURRENCY:-4}"
else
    CONCURRENCY="${CONCURRENCY:-2}"
fi

echo -e "${BLUE}=== Secretary Celery Worker ===${NC}"
echo -e "Mode:        ${GREEN}${MODE}${NC}"
echo -e "Queues:      ${GREEN}${QUEUES}${NC}"
echo -e "Concurrency: ${GREEN}${CONCURRENCY}${NC}"
echo -e "Log Level:   ${GREEN}${LOG_LEVEL}${NC}"

CMD_ARGS=(
    celery -A src.celery_app worker
    --queues "$QUEUES"
    --concurrency "$CONCURRENCY"
    --loglevel "$LOG_LEVEL"
    --hostname "worker@%h"
)

if [ "$FOREGROUND" = true ]; then
    echo -e "Log:         ${GREEN}(stdout)${NC}"
    echo ""
    echo $$ > "$PIDFILE"
    trap 'rm -f "$PIDFILE"' EXIT
    exec "${CMD_ARGS[@]}"
else
    mkdir -p "$(dirname "$LOGFILE")"
    echo -e "Log:         ${GREEN}${LOGFILE}${NC}"
    echo -e "PID file:    ${GREEN}${PIDFILE}${NC}"
    echo ""

    nohup "${CMD_ARGS[@]}" >> "$LOGFILE" 2>&1 &
    local_pid=$!
    echo "$local_pid" > "$PIDFILE"

    sleep 2
    if _is_running "$local_pid"; then
        echo -e "${GREEN}Celery Worker started (PID $local_pid).${NC}"
        echo -e "Tail log: ${BLUE}tail -f $LOGFILE${NC}"
    else
        echo -e "${RED}Celery Worker failed to start. Check $LOGFILE${NC}"
        rm -f "$PIDFILE"
        exit 1
    fi
fi
