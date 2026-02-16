const { spawn } = require("child_process");
const path = require("path");
const http = require("http");

class PythonManager {
  constructor() {
    this.process = null;
    this.backendDir = path.join(__dirname, "..", "..", "backend");
  }

  start() {
    return new Promise((resolve, reject) => {
      const venvPython = path.join(this.backendDir, "venv", "bin", "python");

      this.process = spawn(
        venvPython,
        ["-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
        {
          cwd: this.backendDir,
          env: { ...process.env },
        }
      );

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
