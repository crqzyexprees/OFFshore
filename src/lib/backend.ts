import { invoke, isTauri } from "@tauri-apps/api/core";

export interface BackendConnection {
  url: string;
  token: string | null;
}

export const inTauri = isTauri();

let connection: Promise<BackendConnection> | null = null;

/**
 * In the desktop app, the shell starts the Python backend on a random port and
 * tells us where it is (waiting until it's up). In the browser dev setup, Vite
 * proxies /api to a fixed port, so paths stay relative and no token is needed.
 */
export function connectBackend(): Promise<BackendConnection> {
  connection ??= inTauri
    ? invoke<BackendConnection>("backend_info").catch((e) => {
        connection = null; // allow a retry
        throw new Error(String(e));
      })
    : Promise.resolve({ url: import.meta.env.VITE_API_URL ?? "", token: null });
  return connection;
}

/** Tells the shell the window rendered, disarming its safe-mode watchdog. */
export function reportUiReady() {
  if (inTauri) invoke("ui_ready").catch(() => {});
}

export const shell = {
  getSafeMode: () => invoke<boolean>("get_safe_mode"),
  setSafeMode: (enabled: boolean) => invoke<void>("set_safe_mode", { enabled }),
  restart: () => invoke<void>("restart_app"),
};
