const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  openPdfDialog: () => ipcRenderer.invoke("open-pdf-dialog"),
});
