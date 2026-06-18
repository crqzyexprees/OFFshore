const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const http = require("http");

const API_PORT = process.env.FINANCE_API_PORT || "18765";
const API_URL = `http://127.0.0.1:${API_PORT}`;
const isDev = !app.isPackaged;

let mainWindow = null;
let pythonProcess = null;

function waitForBackend(maxAttempts = 60) {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const check = () => {
      http
        .get(`${API_URL}/health`, (res) => {
          if (res.statusCode === 200) resolve();
          else retry();
        })
        .on("error", retry);
    };
    const retry = () => {
      attempts += 1;
      if (attempts >= maxAttempts) {
        reject(new Error("Python backend failed to start"));
        return;
      }
      setTimeout(check, 500);
    };
    check();
  });
}

function startPythonBackend() {
  const projectRoot = path.join(__dirname, "..");
  const pythonCmd =
    process.env.PYTHON ||
    (require("fs").existsSync(path.join(__dirname, "..", ".venv", "bin", "python"))
      ? path.join(__dirname, "..", ".venv", "bin", "python")
      : "python3");

  pythonProcess = spawn(pythonCmd, ["-m", "backend"], {
    cwd: projectRoot,
    env: { ...process.env, FINANCE_API_PORT: API_PORT },
    stdio: "inherit",
  });

  pythonProcess.on("error", (err) => {
    console.error("Failed to start Python backend:", err);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 750,
    minWidth: 800,
    minHeight: 600,
    title: "Finance",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (isDev) {
    mainWindow.loadURL("http://localhost:1420");
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }
}

ipcMain.handle("open-pdf-dialog", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    filters: [{ name: "PDF", extensions: ["pdf"] }],
    properties: ["openFile"],
  });
  if (result.canceled || result.filePaths.length === 0) return null;
  return result.filePaths[0];
});

app.whenReady().then(async () => {
  startPythonBackend();
  try {
    await waitForBackend();
    createWindow();
  } catch (err) {
    console.error(err);
    app.quit();
  }
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
