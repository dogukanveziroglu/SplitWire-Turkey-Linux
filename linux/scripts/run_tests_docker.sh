#!/bin/bash
#
# Run SplitWire tests inside an isolated Docker container.
#
# Usage:
#   ./scripts/run_tests_docker.sh              # Unit tests only (safe)
#   ./scripts/run_tests_docker.sh unit         # Unit tests only
#   ./scripts/run_tests_docker.sh integration  # Integration tests (privileged)
#   ./scripts/run_tests_docker.sh all          # All tests (privileged)
#   ./scripts/run_tests_docker.sh phase4       # Specific phase (DNS)
#   ./scripts/run_tests_docker.sh phase5       # Specific phase (ByeDPI)
#   ./scripts/run_tests_docker.sh phase6       # Specific phase (WireGuard)
#   ./scripts/run_tests_docker.sh phase7       # Specific phase (Zapret)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
IMAGE_NAME="splitwire-test"
# Use runc if default runtime is nvidia (avoids missing nvidia-container-runtime)
RUNTIME_FLAG=""
if docker info 2>/dev/null | grep -q "Default Runtime: nvidia"; then
    RUNTIME_FLAG="--runtime=runc"
fi

cd "$PROJECT_DIR"

# Build the image if it doesn't exist or if --build is passed
if [[ "$1" == "--build" ]] || ! docker image inspect "$IMAGE_NAME" &>/dev/null; then
    echo "Building test image..."
    docker build -f Dockerfile.test -t "$IMAGE_NAME" .
    [[ "$1" == "--build" ]] && shift
fi

MODE="${1:-unit}"

case "$MODE" in
    unit)
        echo "Running unit tests (safe, no privileges)..."
        docker run --rm $RUNTIME_FLAG "$IMAGE_NAME" \
            pytest tests/ -m "not integration" -q
        ;;
    integration)
        echo "Running integration tests (privileged, isolated network)..."
        docker run --rm $RUNTIME_FLAG \
            --privileged \
            --cap-add=NET_ADMIN \
            --cap-add=NET_RAW \
            --tmpfs /run \
            --tmpfs /run/lock \
            "$IMAGE_NAME" \
            pytest tests/ -m "integration" -v --timeout=120
        ;;
    all)
        echo "Running ALL tests (privileged)..."
        docker run --rm $RUNTIME_FLAG \
            --privileged \
            --cap-add=NET_ADMIN \
            --cap-add=NET_RAW \
            --tmpfs /run \
            --tmpfs /run/lock \
            "$IMAGE_NAME" \
            pytest tests/ -v --timeout=120
        ;;
    phase4|phase5|phase6|phase7)
        PHASE="${MODE//phase/}"
        echo "Running Phase $PHASE tests (privileged)..."
        docker run --rm $RUNTIME_FLAG \
            --privileged \
            --cap-add=NET_ADMIN \
            --cap-add=NET_RAW \
            --tmpfs /run \
            --tmpfs /run/lock \
            "$IMAGE_NAME" \
            pytest tests/ -m "phase${PHASE}" -v --timeout=120
        ;;
    *)
        echo "Usage: $0 [unit|integration|all|phase4|phase5|phase6|phase7]"
        exit 1
        ;;
esac
