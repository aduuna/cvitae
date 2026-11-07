import { readFile } from 'node:fs/promises';
import type { Page } from '@playwright/test';
import { expect, test } from './mock-api';

const EMAIL = 'dev@localhost';

function dataCard(page: Page) {
	return page.locator('section', { has: page.getByRole('heading', { name: 'Data' }) });
}

async function hasHorizontalScroll(page: Page): Promise<boolean> {
	return page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
}

/** Settings shows a placeholder card until the account has loaded. */
async function dataLoaded(page: Page) {
	await expect(page.getByRole('button', { name: 'Export data' })).toBeVisible();
}

async function openDeleteDialog(page: Page) {
	await dataLoaded(page);
	await dataCard(page).getByRole('button', { name: 'Delete account' }).click();
	return page.getByRole('dialog', { name: 'Delete account' });
}

test.describe('account export and deletion', () => {
	test('exports everything as a JSON file', async ({ page, api }) => {
		api.profiles.push({
			id: '00000000-0000-4000-8000-00000000aaaa',
			name: 'Data engineering',
			is_default: true,
			created_at: new Date().toISOString(),
			updated_at: new Date().toISOString(),
			content: {
				schema_version: 1,
				basics: { name: 'Ada', headline: '', email: '', phone: '', location: '', links: [] },
				summary: '',
				sections: []
			}
		});
		await page.goto('/app/settings');
		await dataLoaded(page);

		const download = page.waitForEvent('download');
		await dataCard(page).getByRole('button', { name: 'Export data' }).click();
		const file = await download;

		expect(file.suggestedFilename()).toBe('chameleon-vitae-export.json');
		const exported = JSON.parse(await readFile((await file.path()) as string, 'utf8'));
		expect(exported.account.email).toBe(EMAIL);
		expect(exported.profiles.map((profile: { name: string }) => profile.name)).toEqual([
			'Data engineering'
		]);
		await expect(page.getByRole('status')).toContainText('Your data was exported.');
		expect(api.exports).toBe(1);
	});

	test('deletes the account after typing the email, and signs out', async ({ page, api }) => {
		await page.goto('/app/settings');
		const dialog = await openDeleteDialog(page);
		await expect(dialog).toContainText('It cannot be undone.');

		const confirm = dialog.getByRole('button', { name: 'Delete account' });
		await expect(confirm).toBeDisabled();
		await dialog.getByLabel(`Type ${EMAIL} to confirm`).fill('someone@example.com');
		await expect(confirm).toBeDisabled();
		await dialog.getByLabel(`Type ${EMAIL} to confirm`).fill(EMAIL);
		await expect(confirm).toBeEnabled();
		await confirm.click();

		// Back on the home page, signed out, with the confirmation still showing.
		await expect(page).toHaveURL('/');
		await expect(page.getByRole('status')).toContainText(
			'Your account and everything in it was deleted.'
		);
		expect(api.accountDeleted).toBe(true);

		// The browser stays signed out: the app sends a visitor home.
		await page.goto('/app/documents');
		await expect(page).toHaveURL('/');
		await expect(page.getByRole('link', { name: 'Sign in' }).first()).toBeVisible();
	});

	test('cancelling the dialog keeps the account', async ({ page, api }) => {
		await page.goto('/app/settings');
		const dialog = await openDeleteDialog(page);
		await dialog.getByLabel(`Type ${EMAIL} to confirm`).fill(EMAIL);

		await dialog.getByRole('button', { name: 'Cancel' }).click();

		await expect(dialog).toBeHidden();
		await expect(page).toHaveURL('/app/settings');
		expect(api.accountDeleted).toBe(false);
	});

	test('Escape closes the dialog without deleting', async ({ page, api }) => {
		await page.goto('/app/settings');
		const dialog = await openDeleteDialog(page);

		await page.keyboard.press('Escape');

		await expect(dialog).toBeHidden();
		expect(api.accountDeleted).toBe(false);
	});

	test('says to cancel a running subscription first, and keeps the account', async ({
		page,
		api
	}) => {
		api.me.plan = 'pro';
		api.subscription = {
			status: 'active',
			current_period_end: '2026-11-10T00:00:00Z',
			manageable: true
		};
		await page.goto('/app/settings');
		const dialog = await openDeleteDialog(page);
		await dialog.getByLabel(`Type ${EMAIL} to confirm`).fill(EMAIL);

		await dialog.getByRole('button', { name: 'Delete account' }).click();

		await expect(page.getByRole('alert')).toContainText('Cancel your Pro subscription first');
		await expect(page).toHaveURL('/app/settings');
		await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
		expect(api.accountDeleted).toBe(false);
	});

	for (const width of [1280, 768]) {
		test(`the Data card and the dialog fit at ${width}px`, async ({ page }) => {
			await page.setViewportSize({ width, height: 900 });
			await page.goto('/app/settings');
			await dataLoaded(page);
			await dataCard(page).scrollIntoViewIfNeeded();
			expect(await hasHorizontalScroll(page)).toBe(false);
			await page.screenshot({ path: `test-results/settings-data-${width}.png`, fullPage: true });

			const dialog = await openDeleteDialog(page);
			await dialog.getByLabel(`Type ${EMAIL} to confirm`).fill(EMAIL);
			await expect(dialog).toBeInViewport({ ratio: 1 });
			expect(await hasHorizontalScroll(page)).toBe(false);
			await page.screenshot({ path: `test-results/settings-delete-${width}.png` });
		});
	}
});
