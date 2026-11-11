#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod backend;
mod graphics;
mod settings;

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

use tauri::{AppHandle, Manager, RunEvent, State};

use backend::{Backend, BackendInfo};
use settings::Settings;

/// How long the UI gets to report in before we assume the window is blank
/// (a WebKitGTK/driver problem) and restart in safe mode.
const UI_READY_TIMEOUT: Duration = Duration::from_secs(12);

struct UiReady(AtomicBool);

/// Waits for the Python backend and returns where to reach it.
#[tauri::command]
async fn backend_info(backend: State<'_, Arc<Backend>>) -> Result<BackendInfo, String> {
    let backend = backend.inner().clone();
    tauri::async_runtime::spawn_blocking(move || backend.wait_ready())
        .await
        .map_err(|e| e.to_string())?
}

/// Called by the frontend once it has rendered; disarms the safe-mode watchdog.
#[tauri::command]
fn ui_ready(state: State<'_, UiReady>) {
    state.0.store(true, Ordering::SeqCst);
}

#[tauri::command]
fn get_safe_mode() -> bool {
    Settings::load().safe_mode
}

#[tauri::command]
fn set_safe_mode(enabled: bool) -> Result<(), String> {
    let mut settings = Settings::load();
    settings.safe_mode = enabled;
    settings.save().map_err(|e| e.to_string())
}

#[tauri::command]
fn restart_app(app: AppHandle) {
    restart(&app)
}

fn restart(app: &AppHandle) -> ! {
    app.state::<Arc<Backend>>().shutdown();
    app.restart()
}

fn main() {
    let safe_mode =
        Settings::load().safe_mode || std::env::args().any(|arg| arg == "--safe-mode");
    // Must happen before Tauri initialises GTK/WebKit.
    graphics::apply_workarounds(safe_mode);

    let app = tauri::Builder::default()
        .manage(UiReady(AtomicBool::new(false)))
        .invoke_handler(tauri::generate_handler![
            backend_info,
            ui_ready,
            get_safe_mode,
            set_safe_mode,
            restart_app
        ])
        .setup(move |app| {
            app.manage(Backend::spawn(app.handle()));

            // In dev the first page load waits on Vite, so only arm this in release.
            if !safe_mode && !cfg!(debug_assertions) {
                let handle = app.handle().clone();
                std::thread::spawn(move || {
                    std::thread::sleep(UI_READY_TIMEOUT);
                    if handle.state::<UiReady>().0.load(Ordering::SeqCst) {
                        return;
                    }
                    eprintln!("[finance] UI did not load in {UI_READY_TIMEOUT:?}; restarting in safe mode");
                    let mut settings = Settings::load();
                    settings.safe_mode = true;
                    match settings.save() {
                        Ok(()) => restart(&handle),
                        Err(e) => eprintln!("[finance] could not save safe mode: {e}"),
                    }
                });
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building the Finance app");

    app.run(|app, event| {
        if let RunEvent::Exit = event {
            app.state::<Arc<Backend>>().shutdown();
        }
    });
}
