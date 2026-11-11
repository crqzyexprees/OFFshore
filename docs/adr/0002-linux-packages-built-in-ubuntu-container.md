# 2. Linux packages built in an Ubuntu 22.04 container

Date: 2026-11-09
Status: Accepted

## Context

The app must run on several personal machines. An AppImage only runs on systems
whose glibc is at least as new as the build machine's; the dev machine is Fedora 44
(very new glibc). Fedora's libraries also break linuxdeploy's bundled `strip`.

## Decision

`npm run app:build` (`packaging/build-linux.sh`) builds inside a podman Ubuntu 22.04
container and produces an AppImage, `.rpm` and `.deb` in `release/`. Dependency caches
live in podman volumes. SELinux labelling is disabled for the build container because
linuxdeploy copies files with labels a later run's container can't access.

## Consequences

- Output runs on distros with glibc ≥ 2.35 (~2022 onward).
- The first build is slow (image + toolchains); rebuilds take a few minutes.
- Requires podman on the build machine.
