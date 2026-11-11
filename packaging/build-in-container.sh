#!/usr/bin/env bash
# Runs inside the build container (see build-linux.sh).
set -euo pipefail

echo "==> Frontend dependencies"
npm ci

echo "==> Python backend (PyInstaller)"
[ -x /opt/venv/bin/python ] || python3.12 -m venv /opt/venv
/opt/venv/bin/pip install -q -r backend/requirements.txt -r packaging/requirements-build.txt
/opt/venv/bin/python -m backend.prediction.fetch  # pinned + checksummed; skipped if present
rm -rf build/sidecar
/opt/venv/bin/pyinstaller --noconfirm --log-level WARN \
    --distpath build/sidecar --workpath /tmp/pyinstaller packaging/finance-backend.spec

echo "==> Tauri app (AppImage, rpm, deb)"
# linuxdeploy is itself an AppImage; there's no FUSE in the container.
export APPIMAGE_EXTRACT_AND_RUN=1
rm -rf src-tauri/target/release/bundle  # never ship stale files from a previous build
npx tauri build --config src-tauri/tauri.release.conf.json

rm -rf release && mkdir -p release
cp src-tauri/target/release/bundle/appimage/*.AppImage \
   src-tauri/target/release/bundle/rpm/*.rpm \
   src-tauri/target/release/bundle/deb/*.deb release/
echo "==> Done:" && ls -lh release/
