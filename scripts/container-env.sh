#!/usr/bin/env bash
# Resolve the container engine based on FUZZFORGE_ENGINE env var.
# Usage: source scripts/container-env.sh
# Exports: CONTAINER_CMD

if [ "${FUZZFORGE_ENGINE}" = "podman" ]; then
    if [ -n "${SNAP}" ]; then
        echo "Using Podman with isolated storage (Snap detected)"
        CONTAINER_CMD="podman --root ~/.fuzzforge/containers/storage --runroot ~/.fuzzforge/containers/run"
    else
        echo "Using Podman"
        CONTAINER_CMD="podman"
    fi
else
    echo "Using Docker"
    CONTAINER_CMD="docker"
fi

export CONTAINER_CMD
