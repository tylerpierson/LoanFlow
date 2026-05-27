const { app, BrowserWindow, dialog } = require("electron");
const path = require("path");
const { spawn } = require("child_process");

let backendProcess = null;

function getBackendPath() {
  const analyzerName =
    process.platform === "win32" ? "loneflow_analyzer.exe" : "loneflow_analyzer";

  if (app.isPackaged) {
    return path.join(
      process.resourcesPath,
      "backend",
      "loneflow_analyzer",
      analyzerName
    );
  }

  return path.join(
    __dirname,
    "../backend/dist/loneflow_analyzer",
    analyzerName
  );
}

function startBackend() {
  const backendPath = getBackendPath();

  console.log("Starting backend from:", backendPath);

  backendProcess = spawn(backendPath, [], {
    cwd: path.dirname(backendPath),
    windowsHide: true,
  });

  backendProcess.stdout.on("data", (data) => {
    console.log(`[Backend]: ${data}`);
  });

  backendProcess.stderr.on("data", (data) => {
    console.error(`[Backend Error]: ${data}`);
  });

  backendProcess.on("error", (error) => {
    console.error("Failed to start backend:", error);

    dialog.showErrorBox(
      "Backend failed to start",
      `LoanFlow could not start the document analyzer.\n\n${error.message}`
    );
  });

  backendProcess.on("close", (code) => {
    console.log(`Backend exited with code ${code}`);
  });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1400,
    height: 950,
    title: "LoanFlow",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.loadFile(path.join(__dirname, "../frontend/dist/index.html"));
}

app.whenReady().then(() => {
  startBackend();

  setTimeout(() => {
    createWindow();
  }, 3000);
});

app.on("window-all-closed", () => {
  if (backendProcess) {
    backendProcess.kill();
  }

  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  if (backendProcess) {
    backendProcess.kill();
  }
});