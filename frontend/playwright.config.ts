import { defineConfig, devices } from '@playwright/test'

// E2E smoke config. Drives the real app: Django backend (8000) + Vite (5173).
// Backend must already be running with seed_demo data (see e2e/README or the
// `pretest:e2e` step). Playwright starts the Vite dev server itself.
const FRONTEND_PORT = 5173
const BACKEND_URL = process.env.E2E_BACKEND_URL || 'http://localhost:8000'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  // Vite dev server, pointed at the running Django backend.
  webServer: {
    command: 'npm run dev',
    port: FRONTEND_PORT,
    reuseExistingServer: true,
    timeout: 60_000,
    env: { VITE_API_URL: `${BACKEND_URL}/accounting` },
  },
})
