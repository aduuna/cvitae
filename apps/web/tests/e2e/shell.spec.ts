import type { Page } from '@playwright/test';
import { expect, test } from './mock-api';

const sections = ['Documents', 'Profiles', 'Tailor', 'Templates', 'Settings'];

async function navWidth(page: Page): Promise<number> {
	const box = await page.getByRole('navigation', { name: 'Main' }).boundingBox();
	return Math.round(box?.width ?? 0);
}

async function hasHorizontalScroll(page: Page): Promise<boolean> {
	return page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
}

test.describe('app shell at 1280px', () => {
	test.use({ viewport: { width: 1280, height: 800 } });

	test('lands on Documents with the full side nav and top bar', async ({ page }) => {
		await page.goto('/');
		await expect(page).toHaveURL(/\/app\/documents$/);
		await expect(page.getByRole('heading', { level: 1, name: 'Documents' })).toBeVisible();
		await expect(page).toHaveTitle('Documents - Chameleon vitae');

		const nav = page.getByRole('navigation', { name: 'Main' });
		await expect(nav.getByRole('link')).toHaveText(sections);
		expect(await navWidth(page)).toBe(240);
		const topBar = await page.getByRole('banner').boundingBox();
		expect(Math.round(topBar?.height ?? 0)).toBe(48);
		expect(await hasHorizontalScroll(page)).toBe(false);
		await page.screenshot({ path: 'test-results/shell-1280.png' });
	});

	test('navigates between every section', async ({ page }) => {
		await page.goto('/app/documents');
		for (const name of sections) {
			await page.getByRole('link', { name }).click();
			await expect(page).toHaveURL(new RegExp(`/app/${name.toLowerCase()}$`));
			await expect(page.getByRole('heading', { level: 1, name })).toBeVisible();
			await expect(page.getByRole('link', { name })).toHaveAttribute('aria-current', 'page');
		}
	});

	test('collapses to the icon rail and remembers it across reloads', async ({ page }) => {
		await page.goto('/app/profiles');
		await page.getByRole('button', { name: 'Collapse side nav' }).click();
		await expect.poll(() => navWidth(page)).toBe(56);
		await page.reload();
		await expect.poll(() => navWidth(page)).toBe(56);
		await page.getByRole('button', { name: 'Expand side nav' }).click();
		await expect.poll(() => navWidth(page)).toBe(240);
	});

	test('is operable by keyboard from a skip link', async ({ page }) => {
		await page.goto('/app/documents');
		await expect(page.getByRole('heading', { level: 1, name: 'Documents' })).toBeVisible();
		await page.keyboard.press('Tab');
		await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
		await page.keyboard.press('Tab');
		await expect(page.getByRole('button', { name: 'Collapse side nav' })).toBeFocused();
		await page.keyboard.press('Tab');
		await expect(page.getByRole('link', { name: 'Documents' })).toBeFocused();
	});
});

test.describe('app shell at 768px', () => {
	test.use({ viewport: { width: 768, height: 1024 } });

	test('shows the icon rail without a toggle and keeps every section reachable', async ({
		page
	}) => {
		await page.goto('/app/templates');
		await expect(page.getByRole('heading', { level: 1, name: 'Templates' })).toBeVisible();
		expect(await navWidth(page)).toBe(56);
		await expect(page.getByRole('button', { name: /side nav/ })).toHaveCount(0);

		const nav = page.getByRole('navigation', { name: 'Main' });
		for (const name of sections) {
			await expect(nav.getByRole('link', { name })).toBeVisible();
		}
		expect(await hasHorizontalScroll(page)).toBe(false);
		await page.screenshot({ path: 'test-results/shell-768.png' });

		await nav.getByRole('link', { name: 'Settings' }).hover();
		await expect(page.getByText('Settings', { exact: true }).last()).toBeVisible();
		await nav.getByRole('link', { name: 'Settings' }).click();
		await expect(page.getByRole('heading', { level: 1, name: 'Settings' })).toBeVisible();
	});
});
