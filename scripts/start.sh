#!/bin/bash

# Secretary Project Startup Script
# Usage: ./scripts/start.sh [backend|celery|all|stop]

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if a command exists
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 is not installed"
        return 1
    fi
    return 0
}

# Check if a service is running on a port
check_port() {
    local port=$1
    if lsof -i:$port &> /dev/null; then
        return 0
    fi
    return 1
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    local errors=0

    # Check PostgreSQL
    if check_port 5432; then
        log_success "PostgreSQL is running on port 5432"
    else
        log_warn "PostgreSQL is not running on port 5432"
        log_info "Start PostgreSQL with: brew services start postgresql@15"
        ((errors++))
    fi

    # Check Redis
    if check_port 6379; then
        log_success "Redis is running on port 6379"
    else
        log_warn "Redis is not running on port 6379"
        log_info "Start Redis with: brew services start redis"
        ((errors++))
    fi

    # Check Python
    if check_command python3; then
        log_success "Python $(python3 --version 2>&1 | cut -d' ' -f2) is installed"
    else
        ((errors++))
    fi

    if [ $errors -gt 0 ]; then
        log_warn "Some prerequisites are missing. Continue anyway? (y/n)"
        read -r answer
        if [ "$answer" != "y" ]; then
            exit 1
        fi
    fi
}

# Start backend
start_backend() {
    log_info "Starting backend server..."

    cd "$BACKEND_DIR"

    # Check if venv exists
    if [ ! -d "venv" ]; then
        log_error "Python virtual environment not found. Create it with:"
        log_info "  cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
        return 1
    fi

    # Check if .env exists
    if [ ! -f ".env" ]; then
        log_warn ".env file not found. Copying from .env.example..."
        cp .env.example .env
    fi

    # Activate venv and start uvicorn
    source venv/bin/activate

    # Run database migrations
    log_info "Running database migrations..."
    alembic upgrade head 2>/dev/null || log_warn "Migrations skipped or failed"

    # Start uvicorn in background
    log_info "Starting uvicorn server on http://localhost:8000"
    uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload &
    BACKEND_PID=$!
    echo $BACKEND_PID > "$PROJECT_ROOT/.backend.pid"

    # Wait for backend to start
    sleep 2
    if check_port 8000; then
        log_success "Backend started successfully (PID: $BACKEND_PID)"
        log_info "API docs: http://localhost:8000/docs"
    else
        log_error "Backend failed to start"
        return 1
    fi
}

# Start Celery Worker (for background tasks like trending gifts update)
start_celery_worker() {
    log_info "Starting Celery worker..."

    cd "$BACKEND_DIR"

    # Check if venv exists
    if [ ! -d "venv" ]; then
        log_error "Python virtual environment not found"
        return 1
    fi

    source venv/bin/activate

    # Start Celery worker in background
    # All queues must match task_routes in celery_app.py
    log_info "Starting Celery worker for queues: default, trending_gifts, price_check, secretary, assistant, inventory"
    celery -A src.celery_app worker -Q default,trending_gifts,price_check,secretary,assistant,inventory --loglevel=info &
    CELERY_WORKER_PID=$!
    echo $CELERY_WORKER_PID > "$PROJECT_ROOT/.celery_worker.pid"

    sleep 2
    if kill -0 $CELERY_WORKER_PID 2>/dev/null; then
        log_success "Celery worker started successfully (PID: $CELERY_WORKER_PID)"
    else
        log_error "Celery worker failed to start"
        return 1
    fi
}

# Start Celery Beat (for scheduled tasks like daily trending gifts refresh)
start_celery_beat() {
    log_info "Starting Celery beat scheduler..."

    cd "$BACKEND_DIR"

    # Check if venv exists
    if [ ! -d "venv" ]; then
        log_error "Python virtual environment not found"
        return 1
    fi

    source venv/bin/activate

    # Start Celery beat in background
    log_info "Starting Celery beat for scheduled tasks (trending gifts daily update, etc.)"
    celery -A src.celery_app beat --loglevel=info &
    CELERY_BEAT_PID=$!
    echo $CELERY_BEAT_PID > "$PROJECT_ROOT/.celery_beat.pid"

    sleep 2
    if kill -0 $CELERY_BEAT_PID 2>/dev/null; then
        log_success "Celery beat started successfully (PID: $CELERY_BEAT_PID)"
        log_info "Scheduled tasks:"
        log_info "  - Price check: 03:00 daily"
        log_info "  - Trending gifts daily update: 03:00"
        log_info "  - Trending gifts cache refresh: 06:00, 18:00"
        log_info "  - Event hygiene: 03:00 daily"
        log_info "  - Event curation: every 15 minutes"
        log_info "  - Daily briefing: 08:30"
        log_info "  - Proactive insights: 06:00 daily"
        log_info "  - Inventory check: 20:00 daily"
    else
        log_error "Celery beat failed to start"
        return 1
    fi
}

# Stop all services
stop_services() {
    log_info "Stopping services..."

    # Stop backend
    if [ -f "$PROJECT_ROOT/.backend.pid" ]; then
        BACKEND_PID=$(cat "$PROJECT_ROOT/.backend.pid")
        if kill -0 $BACKEND_PID 2>/dev/null; then
            kill $BACKEND_PID
            log_success "Backend stopped (PID: $BACKEND_PID)"
        fi
        rm -f "$PROJECT_ROOT/.backend.pid"
    fi

    # Stop Celery worker
    if [ -f "$PROJECT_ROOT/.celery_worker.pid" ]; then
        CELERY_WORKER_PID=$(cat "$PROJECT_ROOT/.celery_worker.pid")
        if kill -0 $CELERY_WORKER_PID 2>/dev/null; then
            kill $CELERY_WORKER_PID
            log_success "Celery worker stopped (PID: $CELERY_WORKER_PID)"
        fi
        rm -f "$PROJECT_ROOT/.celery_worker.pid"
    fi

    # Stop Celery beat
    if [ -f "$PROJECT_ROOT/.celery_beat.pid" ]; then
        CELERY_BEAT_PID=$(cat "$PROJECT_ROOT/.celery_beat.pid")
        if kill -0 $CELERY_BEAT_PID 2>/dev/null; then
            kill $CELERY_BEAT_PID
            log_success "Celery beat stopped (PID: $CELERY_BEAT_PID)"
        fi
        rm -f "$PROJECT_ROOT/.celery_beat.pid"
    fi

    # Kill any remaining processes on ports
    if check_port 8000; then
        log_info "Killing process on port 8000..."
        lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    fi

    # Kill any remaining Celery processes
    pkill -f "celery.*src.celery_app" 2>/dev/null || true

    log_success "All services stopped"
}

# Show status
show_status() {
    log_info "Service Status:"
    echo ""

    if check_port 5432; then
        echo -e "  PostgreSQL (5432):   ${GREEN}Running${NC}"
    else
        echo -e "  PostgreSQL (5432):   ${RED}Stopped${NC}"
    fi

    if check_port 6379; then
        echo -e "  Redis (6379):        ${GREEN}Running${NC}"
    else
        echo -e "  Redis (6379):        ${RED}Stopped${NC}"
    fi

    if check_port 8000; then
        echo -e "  Backend (8000):      ${GREEN}Running${NC}"
    else
        echo -e "  Backend (8000):      ${RED}Stopped${NC}"
    fi

    # Check Celery worker
    if [ -f "$PROJECT_ROOT/.celery_worker.pid" ] && kill -0 $(cat "$PROJECT_ROOT/.celery_worker.pid") 2>/dev/null; then
        echo -e "  Celery Worker:       ${GREEN}Running${NC}"
    else
        echo -e "  Celery Worker:       ${RED}Stopped${NC}"
    fi

    # Check Celery beat
    if [ -f "$PROJECT_ROOT/.celery_beat.pid" ] && kill -0 $(cat "$PROJECT_ROOT/.celery_beat.pid") 2>/dev/null; then
        echo -e "  Celery Beat:         ${GREEN}Running${NC}"
    else
        echo -e "  Celery Beat:         ${RED}Stopped${NC}"
    fi

    echo ""
}

# Print usage
print_usage() {
    echo "Secretary Project Startup Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  all       Start all services (backend + celery)"
    echo "  backend   Start backend only (API server)"
    echo "  celery    Start Celery worker and beat (for background tasks)"
    echo "  stop      Stop all services"
    echo "  status    Show service status"
    echo "  help      Show this help message"
    echo ""
    echo "Background Tasks (Celery):"
    echo "  - Price check: 03:00 daily"
    echo "  - Trending gifts update: 03:00 / cache refresh: 06:00, 18:00"
    echo "  - Event hygiene: 03:00 / curation: every 15 min"
    echo "  - Daily briefing: 08:30 / proactive insights: 06:00"
    echo "  - Inventory check: 20:00 daily"
    echo ""
    echo "Examples:"
    echo "  $0              # Start all services"
    echo "  $0 backend      # Start backend only"
    echo "  $0 celery       # Start Celery only"
    echo "  $0 stop         # Stop all services"
    echo "  $0 status       # Show status"
}

# Main
main() {
    local command="${1:-all}"

    case "$command" in
        all)
            check_prerequisites
            start_backend
            start_celery_worker
            start_celery_beat
            echo ""
            log_success "All services started!"
            echo ""
            log_info "Backend API:  http://localhost:8000"
            log_info "API Docs:     http://localhost:8000/docs"
            log_info "Celery:       Worker + Beat (background tasks)"
            echo ""
            log_info "Press Ctrl+C or run '$0 stop' to stop all services"
            wait
            ;;
        backend)
            check_prerequisites
            start_backend
            log_info "Press Ctrl+C or run '$0 stop' to stop"
            wait
            ;;
        celery)
            check_prerequisites
            start_celery_worker
            start_celery_beat
            log_info "Press Ctrl+C or run '$0 stop' to stop"
            wait
            ;;
        stop)
            stop_services
            ;;
        status)
            show_status
            ;;
        help|--help|-h)
            print_usage
            ;;
        *)
            log_error "Unknown command: $command"
            print_usage
            exit 1
            ;;
    esac
}

# Handle Ctrl+C
trap 'echo ""; stop_services; exit 0' INT TERM

main "$@"
