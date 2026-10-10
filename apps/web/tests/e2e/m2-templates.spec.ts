import { expect, test } from './mock-api';

test.describe('templates and settings', () => {
	test.use({ viewport: { width: 1280, height: 800 } });

	test('shows template previews and sets the default used for new CVs', async ({ page, api }) => {
		await page.goto('/app/templates');

		await expect(page.getByRole('img', { name: 'Preview of the Classic template' })).toBeVisible();
		await expect(page.getByRole('img', { name: 'Preview of the Compact template' })).toBeVisible();
		const compact = page.getByRole('listitem').filter({ hasText: 'Compact' });
		const classic = page.getByRole('listitem').filter({ hasText: 'Classic' });
		await expect(classic.getByText('Default')).toBeVisible();

		await compact.getByRole('button', { name: 'Set as default' }).click();

		await expect(compact.getByText('Default')).toBeVisible();
		await expect(classic.getByRole('button', { name: 'Set as default' })).toBeVisible();
		expect(api.me.default_template_id).toBe('compact');
		await page.screenshot({ path: 'test-results/templates-1280.png' });
	});

	test('renames the account in settings', async ({ page, api }) => {
		await page.goto('/app/settings');

		await expect(page.getByLabel('Email')).toHaveValue('dev@localhost');
		await page.getByLabel('Name').fill('Ada Lovelace');
		await page.getByRole('button', { name: 'Save name' }).click();

		await expect(page.getByText('Name saved.')).toBeVisible();
		expect(api.me.display_name).toBe('Ada Lovelace');
	});
});

test.describe('templates at 768px', () => {
	test.use({ viewport: { width: 768, height: 1024 } });

	test('fits without horizontal scroll', async ({ page }) => {
		await page.goto('/app/templates');

		await expect(page.getByRole('img', { name: 'Preview of the Classic template' })).toBeVisible();
		expect(
			await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
		).toBe(false);
		await page.screenshot({ path: 'test-results/templates-768.png' });
	});
});
