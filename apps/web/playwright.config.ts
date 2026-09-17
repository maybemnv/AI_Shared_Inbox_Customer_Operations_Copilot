import fs from "node:fs";
import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

const rootDir = path.resolve(__dirname, "..", "..");
const pythonCandidates = [
  process.env.PYTHON,
  process.env.PYTHON_EXECUTABLE,
  path.join(rootDir, ".venv", process.platform === "win32" ? "Scripts" : "bin", process.platform === "win32" ? "python.exe" : "python"),
  process.platform === "win32" ? "python" : "python3",
].filter(Boolean) as string[];
const pythonPath = pythonCandidates.find((candidate) => !candidate.includes(path.sep) || fs.existsSync(candidate)) ?? "python";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: true,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3103",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "desktop",
      grep: /desktop completes/,
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } },
    },
    {
      name: "mobile",
      grep: /mobile keeps/,
      use: { ...devices["Pixel 5"], viewport: { width: 390, height: 844 } },
    },
    {
      name: "fixture",
      grep: /fixture routes|visible polling|secondary routes|draft failure simulation|explicit conversation selection|customer route requests/,
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } },
    },
  ],
  webServer: [
    {
      command: "node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3103",
      cwd: __dirname,
      env: {
        ...process.env,
        APP_ENV: "local-fixture",
        NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8103",
      },
      url: "http://127.0.0.1:3103/inbox",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: `"${pythonPath}" -m uvicorn app.main:app --host 127.0.0.1 --port 8103`,
      cwd: rootDir,
      env: { ...process.env, APP_ENV: "local-fixture" },
      url: "http://127.0.0.1:8103/readyz",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
