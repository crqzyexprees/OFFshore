//! App-shell settings, read before the window exists (so not via Tauri's path API).
//! Stored in `~/.config/app.splitlens/settings.json`.

use std::fs;
use std::io;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};

const APP_ID: &str = "app.splitlens";
/// Where the app kept its settings when it was called Finance.
const FINANCE_APP_ID: &str = "dev.offshore.finance";

#[derive(Default, Serialize, Deserialize)]
#[serde(default)]
pub struct Settings {
    /// Software rendering; set automatically if the window fails to load.
    pub safe_mode: bool,
}

impl Settings {
    pub fn load() -> Self {
        path(APP_ID)
            .and_then(|p| fs::read(p).ok())
            .or_else(|| path(FINANCE_APP_ID).and_then(|p| fs::read(p).ok()))
            .and_then(|bytes| serde_json::from_slice(&bytes).ok())
            .unwrap_or_default()
    }

    pub fn save(&self) -> io::Result<()> {
        let path = path(APP_ID).ok_or_else(|| io::Error::other("no config directory"))?;
        if let Some(dir) = path.parent() {
            fs::create_dir_all(dir)?;
        }
        fs::write(path, serde_json::to_vec_pretty(self)?)
    }
}

fn path(app_id: &str) -> Option<PathBuf> {
    let base = env_dir("XDG_CONFIG_HOME")
        .or_else(|| env_dir("HOME").map(|home| home.join(".config")))?;
    Some(base.join(app_id).join("settings.json"))
}

fn env_dir(key: &str) -> Option<PathBuf> {
    std::env::var_os(key)
        .map(PathBuf::from)
        .filter(|p| p.is_absolute())
}
