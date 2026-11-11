#!/usr/bin/env bash
# Builds release/Finance_*.AppImage, .rpm and .deb in an Ubuntu 22.04 container
# (podman), so the output runs on older distros than the one you build on.
# Dependency caches live in podman volumes, so rebuilds are much faster.
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE=finance-build:ubuntu22.04
podman build -t "$IMAGE" -f packaging/Containerfile packaging

# SELinux labelling is disabled for this container: linuxdeploy copies system
# files with their labels, which a later run's container may not access.
podman run --rm --security-opt label=disable \
    -v "$PWD:/src" \
    -v finance-build-node-modules:/src/node_modules \
    -v finance-build-target:/src/src-tauri/target \
    -v finance-build-cargo:/root/.cargo/registry \
    -v finance-build-venv:/opt/venv \
    -w /src "$IMAGE" packaging/build-in-container.sh
