#!/bin/bash
#
# Docker-based migration management script.
#
# This script runs Alembic commands through Docker Compose, making it easy
# to manage database migrations from the host system.
#
# Usage:
#     ./scripts/migrate.sh upgrade head           # Apply all migrations
#     ./scripts/migrate.sh downgrade -1          # Rollback one migration
#     ./scripts/migrate.sh revision --autogenerate -m "Add users table"
#     ./scripts/migrate.sh current               # Show current revision
#     ./scripts/migrate.sh history               # Show migration history
#     ./scripts/migrate.sh show <revision>       # Show specific migration
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    print_error "docker-compose is not installed or not in PATH"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    print_error "docker-compose.yml not found. Please run this script from the project root."
    exit 1
fi

# Check if backend service is running
if ! docker-compose ps backend | grep -q "Up"; then
    print_warning "Backend service is not running. Starting it now..."
    docker-compose up -d backend
    sleep 5
fi

# If no arguments provided, show usage
if [ $# -eq 0 ]; then
    echo "Docker-based migration management script."
    echo ""
    echo "Usage:"
    echo "    $0 upgrade head           # Apply all migrations"
    echo "    $0 downgrade -1          # Rollback one migration"
    echo "    $0 revision --autogenerate -m \"Add users table\""
    echo "    $0 current               # Show current revision"
    echo "    $0 history               # Show migration history"
    echo "    $0 show <revision>       # Show specific migration"
    echo ""
    exit 1
fi

# Run the alembic command through docker-compose
print_info "Running: alembic $*"
docker-compose exec backend alembic "$@"

exit_code=$?

if [ $exit_code -eq 0 ]; then
    print_info "Migration command completed successfully"
else
    print_error "Migration command failed with exit code $exit_code"
fi

exit $exit_code 