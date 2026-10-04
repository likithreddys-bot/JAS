import { defineConfig, devices } from "@playwright/test";

// Uses a system Chromium when CHROMIUM_PATH is set (e.g. in a sandbox without a Playwright download).
const executablePath = process.env.CHROMIUM_PATH || undefined;
const launchOptions = {
  executablePath,
  // Software WebGL so the 3D core renders in headless CI.
  args: ["--enable-unsafe-swiftshader", "--use-angle=swiftshader", "--ignore-gpu-blocklist"],
};

export default defineConfig({
  testDir: "tests",
  timeout: 60_000,
  fullyParallel: true,
  reporter: [["list"]],
  use: { baseURL: "http://localhost:4174", launchOptions },
  webServer: {
    command: "npm run build && npx vite preview --port 4174 --strictPort",
    url: "http://localhost:4174",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 }, launchOptions } },
    { name: "phone", use: { ...devices["Pixel 7"], launchOptions } },
  ],
});
