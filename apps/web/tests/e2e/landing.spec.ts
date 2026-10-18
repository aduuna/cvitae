import type { Page } from '@playwright/test';
import { expect, test } from './mock-api';

/**
 * A visitor who is not signed in. The mock api signs everyone in (dev auth), so this serves
 * Firebase auth with a dummy project instead; with nothing saved in the browser, Firebase reports
 * signed out without a network call. Anything outside the app is blocked to be sure.
 */
async function asVisitor(page: Page): Promise<void> {
	await page.route(
		(url) => url.hostname !== 'localhost',
		(route) => route.abort()
	);
	// Registered after the mock api, so this handler answers first.
	await page.route('**/api/v1/client-config', (route) =>
		route.fulfill({
			json: {
				auth_mode: 'firebase',
				firebase: {
					api_key: 'test-api-key',
					auth_domain: 'example.firebaseapp.com',
					project_id: 'example',
					app_id: '1:1:web:1'
				},
				ai_models: [],
				default_ai_model: null,
				plans_enforced: false,
				plans: [],
				billing_enabled: false
			}
		})
	);
}

async function hasHorizontalScroll(page: Page): Promise<boolean> {
	return page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
}

/** Every picture loaded, including the lazy ones further down. */
async function expectImagesLoaded(page: Page): Promise<void> {
	const images = page.locator('main img');
	await expect(images.first()).toBeVisible();
	for (const image of await images.all()) {
		await image.scrollIntoViewIfNeeded();
		await expect
			.poll(() => image.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth))
			.toBeGreaterThan(0);
	}
}

const steps = [
	'Import your CV',
	'Keep a profile for each direction',
	'Tailor it to the job',
	'Edit the CV',
	'Export the PDF'
];

// The app's two supported widths, and a phone, where shared links are often opened.
for (const width of [1280, 768, 390]) {
	test.describe(`landing page at ${width}px`, () => {
		test.use({ viewport: { width, height: 800 } });

		test('shows what the app does, in order, without scrolling sideways', async ({ page }) => {
			await asVisitor(page);
			await page.goto('/');

			await expect(page).toHaveURL(/\/$/);
			await expect(
				page.getByRole('heading', { level: 1, name: 'One career, a CV for every job' })
			).toBeVisible();
			const flow = page.getByRole('region', {
				name: 'From the CV you have to the CV each job needs'
			});
			await expect(flow.getByRole('heading', { level: 3 })).toHaveText(steps);
			await expect(page.getByRole('img', { name: /^The CV editor/ })).toBeVisible();
			await expectImagesLoaded(page);
			expect(await hasHorizontalScroll(page)).toBe(false);
			await page.screenshot({ path: `test-results/landing-${width}.png`, fullPage: true });
		});
	});
}

test.describe('landing page links', () => {
	test.use({ viewport: { width: 1280, height: 800 } });

	test('signs in from the top bar', async ({ page }) => {
		await asVisitor(page);
		await page.goto('/');

		await page.getByRole('banner').getByRole('link', { name: 'Sign in' }).click();

		await expect(page).toHaveURL(/\/login$/);
		await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeVisible();
		await page.getByRole('link', { name: 'Chameleon vitae home' }).click();
		await expect(page).toHaveURL(/\/$/);
	});

	test('gets started from the bottom of the page', async ({ page }) => {
		await asVisitor(page);
		await page.goto('/');

		await page.getByRole('link', { name: 'See how it works' }).click();
		await expect(page).toHaveURL(/#how-it-works$/);
		await expect(page.getByRole('heading', { name: 'Import your CV' })).toBeInViewport();

		await page.getByRole('link', { name: 'Get started' }).last().click();
		await expect(page).toHaveURL(/\/login$/);
		await expect(page.getByRole('button', { name: 'Email me a sign-in link' })).toBeVisible();
	});

	test('reads well in the dark theme', async ({ page }) => {
		await page.emulateMedia({ colorScheme: 'dark' });
		await asVisitor(page);
		await page.goto('/');

		await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
		await expectImagesLoaded(page);
		await page.screenshot({ path: 'test-results/landing-dark.png', fullPage: true });
	});

	test('shows signed-in visitors the page with a way into the app', async ({ page }) => {
		await page.goto('/app/documents');
		await page
			.getByRole('navigation', { name: 'Main' })
			.getByRole('link', { name: 'Chameleon vitae' })
			.click();

		await expect(page).toHaveURL(/\/$/);
		await page.getByRole('banner').getByRole('link', { name: 'Open app' }).click();
		await expect(page).toHaveURL(/\/app\/documents$/);
	});

	test('serves the page as HTML that search engines can read without running it', async ({
		request
	}) => {
		const html = await (await request.get('/')).text();

		expect(html).toContain('<title>Chameleon vitae: a CV tailored to every job</title>');
		expect(html).toContain('One career,');
		expect(html).toContain('Import your CV');
		expect(html).toContain('<link rel="canonical" href="https://cvitae.aduuna.dev/"');
		expect(html).toContain('"alternateName":["cvitae","Chameleon CV"]');
		expect(await (await request.get('/robots.txt')).text()).toContain(
			'Sitemap: https://cvitae.aduuna.dev/sitemap.xml'
		);
		expect(await (await request.get('/sitemap.xml')).text()).toContain(
			'<loc>https://cvitae.aduuna.dev/</loc>'
		);
		expect((await request.get('/og.png')).headers()['content-type']).toBe('image/png');
	});

	test('in local development, signs out to the landing page and back in', async ({ page }) => {
		await page.goto('/app/documents');
		await page.getByRole('button', { name: 'Account' }).click();
		await page.getByRole('menuitem', { name: 'Sign out' }).click();

		await expect(page).toHaveURL(/\/$/);
		const headline = page.getByRole('heading', {
			level: 1,
			name: 'One career, a CV for every job'
		});
		await expect(headline).toBeVisible();
		await page.reload();
		await expect(headline).toBeVisible();

		await page.getByRole('banner').getByRole('link', { name: 'Sign in' }).click();
		await page.getByRole('button', { name: 'Continue with Google' }).click();

		await expect(page).toHaveURL(/\/app\/documents$/);
	});
});
