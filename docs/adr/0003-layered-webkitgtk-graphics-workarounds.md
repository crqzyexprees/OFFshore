# 3. Layered workarounds for WebKitGTK graphics bugs

Date: 2026-11-09
Status: Accepted

## Context

WebKitGTK can show a blank window or crash on some drivers, mostly NVIDIA's
proprietary driver. Some target machines have NVIDIA GPUs.

## Decision

1. On startup, if `/proc/driver/nvidia/version` exists: set
   `__NV_DISABLE_EXPLICIT_SYNC=1` on Wayland, `WEBKIT_DISABLE_DMABUF_RENDERER=1` on X11.
2. **Safe mode**: if the UI doesn't call `ui_ready` within 12 s (release builds), persist
   `safe_mode` and restart with software rendering. Also a Settings toggle and `--safe-mode`.
3. Ship `.rpm`/`.deb` (system WebKit) alongside the AppImage as a fallback.
4. UI avoids `backdrop-filter` and other effects that break without GPU compositing.

Environment variables the user already set are never overridden.

## Consequences

- Worst case on a bad driver is one slow first launch, then software rendering.
- The NVIDIA path is untested on real NVIDIA hardware as of this ADR.
