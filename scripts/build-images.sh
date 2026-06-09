#!/usr/bin/env bash
# Build and push lawapp backend image to GHCR.
# Usage: bash scripts/build-images.sh [tag]
# Requires: docker login ghcr.io -u serverax
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

SHA=$(git rev-parse --short HEAD)
TAG="${1:-$SHA}"
IMAGE="ghcr.io/serverax/lawapp/backend"

echo "Building $IMAGE:$TAG"
docker build -t "$IMAGE:$TAG" -t "$IMAGE:latest" -f Dockerfile .

echo "Pushing $IMAGE:$TAG"
docker push "$IMAGE:$TAG"
docker push "$IMAGE:latest"

echo "Verifying pull-back..."
docker pull "$IMAGE:$TAG" > /dev/null
echo "DONE: $IMAGE:$TAG"
