//! Runs the Python backend (`python -m backend --sidecar`) as a child process.
//!
//! The backend binds a random localhost port, then prints
//! `FINANCE_BACKEND_READY <port> <token>` on stdout. We hold its stdin open for
//! as long as we live; when we exit or crash the pipe closes and it shuts down.

use std::io::{BufRead, BufReader};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::{Arc, Condvar, Mutex};
use std::time::Duration;

use serde::Serialize;
use tauri::AppHandle;

const READY_PREFIX: &str = "FINANCE_BACKEND_READY";
const START_TIMEOUT: Duration = Duration::from_secs(60);

#[derive(Clone, Serialize)]
pub struct BackendInfo {
    pub url: String,
    pub token: String,
}

pub struct Backend {
    status: Mutex<Option<Result<BackendInfo, String>>>,
    ready: Condvar,
    process: Mutex<Option<(Child, ChildStdin)>>,
}

impl Backend {
    pub fn spawn(app: &AppHandle) -> Arc<Self> {
        let backend = Arc::new(Self {
            status: Mutex::new(None),
            ready: Condvar::new(),
            process: Mutex::new(None),
        });

        let spawned = command(app).and_then(|mut cmd| {
            cmd.stdin(Stdio::piped())
                .stdout(Stdio::piped())
                .stderr(Stdio::inherit())
                .spawn()
                .map_err(|e| format!("could not start the backend: {e}"))
        });

        match spawned {
            Ok(mut child) => {
                let stdin = child.stdin.take().expect("stdin is piped");
                let stdout = child.stdout.take().expect("stdout is piped");
                *backend.process.lock().unwrap() = Some((child, stdin));
                let reader = backend.clone();
                std::thread::spawn(move || reader.read_stdout(stdout));
            }
            Err(e) => backend.finish(Err(e)),
        }
        backend
    }

    pub fn wait_ready(&self) -> Result<BackendInfo, String> {
        let status = self.status.lock().unwrap();
        let (status, _) = self
            .ready
            .wait_timeout_while(status, START_TIMEOUT, |s| s.is_none())
            .unwrap();
        status
            .clone()
            .unwrap_or_else(|| Err("the backend did not start in time".into()))
    }

    pub fn shutdown(&self) {
        let Some((mut child, stdin)) = self.process.lock().unwrap().take() else {
            return;
        };
        // Closing stdin asks the backend to exit cleanly; kill it if it lingers.
        drop(stdin);
        for _ in 0..30 {
            if let Ok(Some(_)) = child.try_wait() {
                return;
            }
            std::thread::sleep(Duration::from_millis(100));
        }
        let _ = child.kill();
        let _ = child.wait();
    }

    fn read_stdout(&self, stdout: ChildStdout) {
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            let mut parts = line.strip_prefix(READY_PREFIX).map(str::split_whitespace);
            match parts.as_mut().map(|p| (p.next(), p.next())) {
                Some((Some(port), Some(token))) => self.finish(Ok(BackendInfo {
                    url: format!("http://127.0.0.1:{port}"),
                    token: token.to_string(),
                })),
                _ => eprintln!("{line}"),
            }
        }
        // stdout closed: the process exited. Only matters if it never got ready.
        self.finish(Err("the backend exited during startup".into()));
    }

    fn finish(&self, result: Result<BackendInfo, String>) {
        let mut status = self.status.lock().unwrap();
        if status.is_none() {
            *status = Some(result);
            self.ready.notify_all();
        }
    }
}

/// Dev builds run the project's venv Python; release builds run the
/// PyInstaller bundle shipped in the app's resources.
#[cfg(debug_assertions)]
fn command(_app: &AppHandle) -> Result<Command, String> {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("..");
    let venv = root.join(".venv/bin/python");
    let python = if venv.exists() { venv } else { "python3".into() };
    let mut cmd = Command::new(python);
    cmd.args(["-m", "backend", "--sidecar"]).current_dir(root);
    Ok(cmd)
}

#[cfg(not(debug_assertions))]
fn command(app: &AppHandle) -> Result<Command, String> {
    use tauri::Manager;
    let dir = app
        .path()
        .resource_dir()
        .map_err(|e| e.to_string())?
        .join("sidecar");
    let mut cmd = Command::new(dir.join("finance-backend"));
    cmd.arg("--sidecar");
    Ok(cmd)
}
