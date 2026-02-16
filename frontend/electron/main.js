const { app, BrowserWindow, ipcMain, shell } = require("electron");
const path = require("path");
const PythonManager = require("./python-manager");

// Handle open-external requests from the renderer
ipcMain.handle("open-external", (_, url) => {
  return shell.openExternal(url);
});

const pythonManager = new PythonManager();
let mainWindow;

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 440,
    height: 640,
    resizable: true,
    minWidth: 380,
    minHeight: 500,
    titleBarStyle: "hiddenInset",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadFile(path.join(__dirname, "..", "src", "index.html"));
}

app.whenReady().then(async () => {
  try {
    console.log("Starting Python backend...");
    await pythonManager.start();
    console.log("Python backend started successfully");
  } catch (err) {
    console.error("Failed to start Python backend:", err.message);
    // Still open the window — the UI will show the error state
  }

  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("before-quit", () => {
  pythonManager.stop();
});

app.on("window-all-closed", () => {
  pythonManager.stop();
  if (process.platform !== "darwin") {
    app.quit();
  }
});
