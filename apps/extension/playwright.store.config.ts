import { defineConfig } from '@playwright/test';

/** Makes the Chrome Web Store images in store/ (tests/store/assets.spec.ts). */
export default defineConfig({
	testDir: 'tests/store',
	globalSetup: './tests/e2e/global-setup.ts',
	workers: 1,
	reporter: 'list'
});
