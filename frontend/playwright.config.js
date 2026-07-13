// Playwright E2E 测试配置
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.spec.js',
  timeout: 30 * 1000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    actionTimeout: 10 * 1000,
    navigationTimeout: 15 * 1000,
  },
  // 不启动 webServer：依赖用户机器上已经在跑的 dev/fastapi 服务
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
})