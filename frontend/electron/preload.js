const { contextBridge, ipcRenderer } = require("electron");

// Expose a safe API to the renderer process
contextBridge.exposeInMainWorld("electronAPI", {
  platform: process.platform,
  openExternal: (url) => ipcRenderer.invoke("open-external", url),
});
