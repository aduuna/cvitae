import { defineConfig } from '@playwright/test';

/**
 * The built extension in Chromium, against a mock api (tests/e2e/server.ts). Extensions need
 * the full Chromium build, not the headless shell: `bunx playwright install chromium`.
 */
export default defineConfig({
	testDir: 'tests/e2e',
	globalSetup: './tests/e2e/global-setup.ts',
	timeout: 60_000,
	workers: 1,
	reporter: process.env.CI ? 'github' : 'list',
	use: { trace: 'retain-on-failure' }
});
