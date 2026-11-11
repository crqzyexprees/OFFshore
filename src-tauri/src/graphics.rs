//! Workarounds for WebKitGTK rendering bugs (blank window, startup crash),
//! mostly with NVIDIA's proprietary driver. See
//! https://v2.tauri.app/develop/debug/linux-graphics/
//!
//! Must run before GTK/WebKit initialise. Variables already set in the
//! environment are left alone, so they can always be overridden by hand.

use std::env;
use std::path::Path;

pub fn apply_workarounds(safe_mode: bool) {
    let nvidia = Path::new("/proc/driver/nvidia/version").exists();
    let wayland = env::var_os("WAYLAND_DISPLAY").is_some();
    let mut applied = Vec::new();

    if nvidia {
        if wayland {
            // Fixes the "Error 71 (Protocol error)" crash; no performance cost.
            set_default("__NV_DISABLE_EXPLICIT_SYNC", &mut applied);
        } else {
            // Fixes the blank window on X11.
            set_default("WEBKIT_DISABLE_DMABUF_RENDERER", &mut applied);
        }
    }

    if safe_mode {
        // Software rendering: slower, but works on any driver.
        set_default("WEBKIT_DISABLE_DMABUF_RENDERER", &mut applied);
        set_default("WEBKIT_DISABLE_COMPOSITING_MODE", &mut applied);
    }

    eprintln!(
        "[finance] graphics: nvidia={nvidia} wayland={wayland} safe_mode={safe_mode} set={applied:?}"
    );
}

fn set_default(key: &'static str, applied: &mut Vec<&'static str>) {
    if env::var_os(key).is_none() {
        env::set_var(key, "1");
        applied.push(key);
    }
}
