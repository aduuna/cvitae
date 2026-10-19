import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { chromium, expect, test, type BrowserContext, type Page } from '@playwright/test';
import { E2E_OUT_DIR, JOB_URL, startServer } from '../e2e/server.ts';
import { careersPage } from './careers.ts';
import { marqueeTile, screenLayout, SCREEN, smallTile, WINDOW, type Screen } from './layouts.ts';

/**
 * The Chrome Web Store images, from the real extension against the mock api: run
 * `bun run store:assets`, then upload what is in store/. JPEG, as the store takes no alpha.
 */

const extension = join(import.meta.dirname, '../..', E2E_OUT_DIR, 'chrome');
const out = join(import.meta.dirname, '../../store');
/** A second ad, not saved yet in the mock account, for saving a job. */
const OTHER_JOB_URL = 'https://job-boards.greenhouse.io/harbour/jobs/4099999';

/** The page's address as a browser shows it, without the scheme. */
function address(page: Page): string {
	const url = new URL(page.url());
	return `${url.host}${url.pathname}`;
}

async function capture(page: Page): Promise<string> {
	return `data:image/png;base64,${(await page.screenshot()).toString('base64')}`;
}

/** Render a layout at its exact size and save it as JPEG. */
async function render(context: BrowserContext, html: string, file: string, size = SCREEN) {
	const page = await context.newPage();
	await page.setViewportSize(size);
	await page.setContent(html, { waitUntil: 'load' });
	await page.evaluate(() => document.fonts.ready);
	await page.screenshot({ path: join(out, file), type: 'jpeg', quality: 92, scale: 'css' });
	await page.close();
}

async function sitePage(context: BrowserContext, url: string, width: number): Promise<Page> {
	const page = await context.newPage();
	await page.setViewportSize({ width, height: WINDOW.height });
	await page.goto(url);
	return page;
}

test('store assets', async () => {
	test.setTimeout(120_000);
	mkdirSync(out, { recursive: true });
	const api = await startServer();
	const context = await chromium.launchPersistentContext('', {
		channel: 'chromium',
		deviceScaleFactor: 2,
		args: [`--disable-extensions-except=${extension}`, `--load-extension=${extension}`]
	});
	context.setDefaultTimeout(10_000);
	await context.route(`${JOB_URL}**`, (route) =>
		route.fulfill({ contentType: 'text/html', body: careersPage() })
	);
	await context.route(`${OTHER_JOB_URL}**`, (route) =>
		route.fulfill({ contentType: 'text/html', body: careersPage('Analytics Engineer') })
	);
	const worker = context.serviceWorkers()[0] ?? (await context.waitForEvent('serviceworker'));
	const id = new URL(worker.url()).host;

	// Installing opened the (mock) Extension page, which connects.
	await expect
		.poll(() => context.pages().some((p) => p.url().endsWith('/app/extension')))
		.toBe(true);
	const connect = context.pages().find((p) => p.url().endsWith('/app/extension'))!;
	await expect(connect.locator('#status')).toHaveText('Connected to ama@example.com');
	// No offer box over the page while the panel is in the pictures.
	await worker.evaluate(() => chrome.storage.local.set({ offer: false }));

	const site = await sitePage(context, JOB_URL, WINDOW.page);
	const panel = await context.newPage();
	await panel.setViewportSize({ width: WINDOW.panel, height: WINDOW.height });
	// The panel works on the tab whose address is kept in its local storage (the job's, at first),
	// as it would on the tab beside it.
	await panel.addInitScript((url) => {
		const tab = localStorage.getItem('storeTab') ?? url;
		const query = chrome.tabs.query.bind(chrome.tabs);
		chrome.tabs.query = (async () => query({ url: tab })) as typeof chrome.tabs.query;
	}, JOB_URL);
	await panel.goto(`chrome-extension://${id}/sidepanel.html`);
	await expect(panel.getByText(/The CV you tailored for/)).toBeVisible();

	const shot = async (page: Page, caption: string, detail: string): Promise<Screen> => ({
		caption,
		detail,
		page: await capture(page),
		panel: await capture(panel),
		address: address(page)
	});

	await panel.getByRole('button', { name: 'Fill form' }).click();
	await expect(panel.getByRole('button', { name: /^Fill \d+ fields$/ })).toBeVisible();
	const review = await shot(
		site,
		'See what goes where before anything is filled',
		'Untick a field to leave it, or change its text first. Nothing is ever submitted for you.'
	);

	await panel.getByRole('button', { name: /^Fill \d+ fields$/ }).click();
	await expect(panel.getByText(/^Filled \d+ fields/)).toBeVisible();
	await panel.getByRole('button', { name: 'Attach CV' }).click();
	await expect(panel.getByText(/^Attached /)).toBeVisible();
	await panel.getByText(/^Attached /).scrollIntoViewIfNeeded();
	await site.locator('#resume').scrollIntoViewIfNeeded();
	const attach = await shot(
		site,
		'Attach the CV you tailored for this job',
		'The CV made for the job on the page is chosen for you, and goes into the form as a PDF.'
	);

	await panel.getByRole('button', { name: 'Show details' }).click();
	await panel.getByText('Lead data engineer at Northwind Consulting').scrollIntoViewIfNeeded();
	const details = await shot(
		site,
		'Copy what a form asks for, detail by detail',
		'For fields a site builds in its own way, every detail from your profile has a copy button.'
	);

	// A job ad not saved yet, in another tab; the panel opens on it.
	const other = await sitePage(context, OTHER_JOB_URL, WINDOW.page);
	await panel.evaluate((url) => localStorage.setItem('storeTab', url), OTHER_JOB_URL);
	await panel.reload();
	await panel.getByRole('button', { name: 'Save job ad' }).click();
	await expect(panel.getByRole('textbox', { name: 'Company' })).toHaveValue('Harbour Bank');
	await panel.getByRole('button', { name: 'Save job', exact: true }).scrollIntoViewIfNeeded();
	const save = await shot(
		other,
		'Save the job ad, then tailor a CV for it',
		'The ad goes to Chameleon vitae, which tailors your CV to it without inventing anything.'
	);
	await panel.close();

	// The offer on the page itself.
	await worker.evaluate(() => chrome.storage.local.set({ offer: true }));
	const page = await sitePage(context, JOB_URL, WINDOW.full);
	const prompt = page.locator('cvitae-prompt');
	await prompt.getByRole('button', { name: 'Fill fields' }).click();
	await expect(prompt.getByText(/^Filled \d+ fields/)).toBeVisible();
	const offer: Screen = {
		caption: 'Fill an application in one click',
		detail:
			'On job sites a small offer appears beside the form. Your profile is read only if you choose to fill.',
		page: await capture(page),
		address: address(page)
	};

	for (const [index, screen] of [review, offer, attach, save, details].entries()) {
		await render(context, screenLayout(screen), `screenshot-${index + 1}.jpg`);
	}
	await render(context, smallTile(), 'promo-small.jpg', { width: 440, height: 280 });
	await render(context, marqueeTile(), 'promo-marquee.jpg', { width: 1400, height: 560 });

	await context.close();
	await api.close();
});
