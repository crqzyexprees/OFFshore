# 1. Tauri shell with a Python sidecar backend

Date: 2026-11-09
Status: Accepted

## Context

The app started on Electron, which bundles Chromium (~150 MB) and ran a separate
Python process for PDF parsing, ML inference and SQLite. We wanted a lighter,
installable Linux app without rewriting the backend. Options considered:

- **pywebview** (Python opens a system-WebKit window): lean, but the GTK bindings
  (PyGObject) can't be bundled reliably, so it can't ship as a self-contained AppImage.
- **PySide6 / Qt WebEngine**: fully bundleable and renders like Chrome, but ~130–170 MB
  and no packaging/updater tooling.
- **Tauri + Rust rewrite of the backend**: smallest single binary, but Rust lacks a
  proven equivalent of pdfplumber, risking silently wrong parsed amounts.
- **Tauri + Python sidecar**: Tauri owns the window and packaging; Python stays headless.

## Decision

Tauri (Rust) runs the React UI and spawns the Python backend (`python -m backend
--sidecar`, PyInstaller-bundled in releases) as a child process. The backend binds a
random 127.0.0.1 port, prints `FINANCE_BACKEND_READY <port> <token>`, requires that
per-launch token on every request, allows only the app's origin via CORS, and exits
when its stdin closes (i.e. when the shell exits or crashes).

## Consequences

- Python code (parsers, classifier, DB) is unchanged and remains the single source of
  truth for domain logic.
- Three toolchains (Rust, Node, Python), but the Rust surface is ~250 lines.
- Two processes; lifecycle is handled by the stdin-EOF contract.
- UI renders with WebKitGTK, which has driver-specific bugs — see ADR 0003.
