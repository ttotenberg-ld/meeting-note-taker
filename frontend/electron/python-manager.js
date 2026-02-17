const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const http = require("http");

class PythonManager {
  constructor() {
    this.process = null;
    this._resolveLocations();
  }

  /**
   * Determine whether we're running in dev mode (venv) or packaged mode
   * (PyInstaller binary bundled inside Electron's resources).
   */
  _resolveLocations() {
    // Check for packaged binary first (Electron Builder extraResources)
    const resourcesPath = process.resourcesPath; // set by Electron in packaged app
    const bundledBinary = path.join(
      resourcesPath || "",
      "backend",
      "meeting-note-taker-backend"
    );

    if (resourcesPath && fs.existsSync(bundledBinary)) {
      // Packaged mode
      this.mode = "bundled";
      this.executable = bundledBinary;
      // Backend data dir: ~/Library/Application Support/Meeting Note-Taker/
      const { app } = require("electron");
      this.backendDataDir = path.join(app.getPath("userData"), "backend-data");
      // Ensure data dir exists
      if (!fs.existsSync(this.backendDataDir)) {
        fs.mkdirSync(this.backendDataDir, { recursive: true });
      }
    } else {
      // Dev mode — use venv python
      this.mode = "dev";
      this.backendDir = path.join(__dirname, "..", "..", "backend");
      this.executable = path.join(this.backendDir, "venv", "bin", "python");
    }
  }

  start() {
    return new Promise((resolve, reject) => {
      if (this.mode === "bundled") {
        // Run the PyInstaller binary directly — it starts uvicorn internally
        this.process = spawn(this.executable, [], {
          cwd: this.backendDataDir,
          env: {
            ...process.env,
            BACKEND_DATA_DIR: this.backendDataDir,
          },
        });
      } else {
        // Dev mode — run via venv python + uvicorn
        this.process = spawn(
          this.executable,
          ["-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
          {
            cwd: this.backendDir,
            env: { ...process.env },
          }
        );
      }

      this.process.stdout.on("data", (data) => {
        console.log(`[Python] ${data.toString().trim()}`);
      });

      this.process.stderr.on("data", (data) => {
        const output = data.toString().trim();
        console.log(`[Python] ${output}`);
        // uvicorn logs to stderr by default
        if (output.includes("Application startup complete")) {
          resolve();
        }
      });

      this.process.on("error", (err) => {
        reject(new Error(`Failed to start Python backend: ${err.message}`));
      });

      this.process.on("close", (code) => {
        if (code !== null && code !== 0) {
          console.error(`Python process exited with code ${code}`);
        }
        this.process = null;
      });

      // Poll for health endpoint as a fallback
      const startTime = Date.now();
      const pollHealth = () => {
        if (Date.now() - startTime > 15000) {
          reject(new Error("Python backend startup timeout (15s)"));
          return;
        }

        const req = http.get("http://127.0.0.1:8000/api/health", (res) => {
          if (res.statusCode === 200) {
            resolve();
          } else {
            setTimeout(pollHealth, 500);
          }
        });
        req.on("error", () => {
          setTimeout(pollHealth, 500);
        });
        req.end();
      };

      setTimeout(pollHealth, 1000);
    });
  }

  stop() {
    if (this.process) {
      this.process.kill("SIGTERM");
      this.process = null;
    }
  }
}

module.exports = PythonManager;
