/// <reference types="vite/client" />

interface ElectronAPI {
  openPdfDialog: () => Promise<string | null>;
}

interface Window {
  electronAPI?: ElectronAPI;
}
