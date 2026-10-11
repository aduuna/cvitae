import type { Page } from '@playwright/test';
import { expect, test } from './mock-api';

function dataTheme(page: Page): Promise<string | undefined> {
	return page.evaluate(() => document.documentElement.dataset.theme);
}

function canvasColor(page: Page): Promise<string> {
	return page.evaluate(() => getComputedStyle(document.documentElement).backgroundColor);
}

test.describe('theme on a dark device', () => {
	test.use({ viewport: { width: 1280, height: 800 }, colorScheme: 'dark' });

	test('paints dark before the app starts', async ({ page }) => {
		// Without the app bundle only static/theme.js runs: the first paint must already be dark.
		await page.route('**/_app/**/*.js', (route) => route.abort());
		await page.goto('/app/documents');
		expect(await dataTheme(page)).toBe('dark');
		expect(await canvasColor(page)).toBe('rgb(10, 10, 10)');
	});

	test('a choice in Settings overrides the device and survives reloads', async ({ page }) => {
		await page.goto('/app/settings');
		const themes = page.getByRole('radiogroup', { name: 'Theme' });
		await expect(themes.getByRole('radio', { name: 'System' })).toBeChecked();
		expect(await dataTheme(page)).toBe('dark');
		await page.screenshot({ path: 'test-results/theme-dark-settings.png', fullPage: true });

		await themes.getByRole('radio', { name: 'Light' }).click();
		await expect.poll(() => dataTheme(page)).toBe('light');
		expect(await canvasColor(page)).toBe('rgb(244, 244, 245)');

		await page.reload();
		await expect(themes.getByRole('radio', { name: 'Light' })).toBeChecked();
		expect(await dataTheme(page)).toBe('light');

		await themes.getByRole('radio', { name: 'System' }).click();
		await expect.poll(() => dataTheme(page)).toBe('dark');
	});

	test('keeps CV previews on white paper', async ({ page }) => {
		await page.goto('/app/templates');
		const preview = page.getByRole('img', { name: /^Preview of the/ }).first();
		await expect(preview).toBeVisible();
		expect(await preview.evaluate((img) => getComputedStyle(img).backgroundColor)).toBe(
			'rgb(255, 255, 255)'
		);
		await page.screenshot({ path: 'test-results/theme-dark-templates.png' });
	});
});
