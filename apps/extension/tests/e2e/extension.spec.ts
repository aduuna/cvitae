import { join } from 'node:path';
import { chromium, expect, test as base, type BrowserContext, type Page } from '@playwright/test';
import { E2E_OUT_DIR, JOB_URL, jobPage, startServer, type MockApi } from './server.ts';

const extension = join(import.meta.dirname, '../..', E2E_OUT_DIR, 'chrome');

const test = base.extend<{ context: BrowserContext; extensionId: string }, { api: MockApi }>({
	api: [
		// eslint-disable-next-line no-empty-pattern -- Playwright reads a fixture's needs from this pattern
		async ({}, use) => {
			const api = await startServer();
			await use(api);
			await api.close();
		},
		{ scope: 'worker' }
	],
	// Asks for the api so the mock server runs before the extension starts calling it.
	context: async ({ api }, use) => {
		void api;
		const context = await chromium.launchPersistentContext('', {
			channel: 'chromium',
			args: [`--disable-extensions-except=${extension}`, `--load-extension=${extension}`]
		});
		// The job site, served from the test: the extension reads Greenhouse at install.
		await context.route(`${JOB_URL}**`, (route) =>
			route.fulfill({ contentType: 'text/html', body: jobPage() })
		);
		await use(context);
		await context.close();
	},
	extensionId: async ({ context }, use) => {
		const worker = context.serviceWorkers()[0] ?? (await context.waitForEvent('serviceworker'));
		await use(new URL(worker.url()).host);
	}
});

/** The page the extension opened, once it has. */
async function opened(context: BrowserContext, pattern: RegExp): Promise<Page> {
	const found = () => context.pages().find((page) => pattern.test(page.url()));
	await expect.poll(() => Boolean(found()), { timeout: 15_000 }).toBe(true);
	return found()!;
}

async function connect(context: BrowserContext): Promise<void> {
	const page = await opened(context, /\/app\/extension$/);
	await expect(page.locator('#status')).toHaveText('Connected to ama@example.com');
}

test('connects on install, offers to fill a job application, and fills it', async ({
	context,
	extensionId
}) => {
	expect(extensionId).toMatch(/^[a-p]{32}$/);
	await connect(context);

	const page = await context.newPage();
	await page.goto(JOB_URL);
	const prompt = page.locator('cvitae-prompt');
	// The CV tailored for this job is the one offered.
	await expect(prompt.getByText(/from your Harbour Bank CV/)).toBeVisible();
	await prompt.getByRole('button', { name: 'Fill fields' }).click();

	await expect(
		prompt.getByText('Filled 16 fields. Check each one before you submit.')
	).toBeVisible();
	await expect(page.locator('#first_name')).toHaveValue('Ama');
	await expect(page.locator('#email')).toHaveValue('ama@example.com');
	await expect(page.locator('#company-name-0')).toHaveValue('Northwind Consulting');
	await expect(page.locator('#start-date-month-0')).toHaveValue('3');
	await expect(page.locator('#start-date-year-0')).toHaveValue('2021');
	await expect(page.locator('#current-role-0')).toBeChecked();
	await expect(page.locator('#first_name')).toHaveAttribute('data-cvitae-filled', '');
	// Fields the user cannot see stay empty.
	for (const trap of ['#trap-email', '#trap-phone', '#trap-name']) {
		await expect(page.locator(trap)).toHaveValue('');
	}

	await prompt.getByRole('button', { name: 'Undo fill' }).click();
	await expect(page.locator('#first_name')).toHaveValue('');
});

test('attaches the CV as a PDF and reads the job ad, as the side panel does', async ({
	context
}) => {
	await connect(context);
	const page = await context.newPage();
	await page.goto(JOB_URL);
	await expect(page.locator('cvitae-prompt')).toBeVisible();

	const worker = context.serviceWorkers()[0]!;
	const result = await worker.evaluate(async (url) => {
		const [tab] = await chrome.tabs.query({ url: `${url}*` });
		if (!tab?.id) throw new Error('no tab');
		const target = { tabId: tab.id };
		type Cvitae = {
			scan(): { files: { id: string }[] };
			attach(id: string, file: { name: string; type: string; base64: string }): boolean;
			job(): { title: string; company: string; from: string } | null;
		};
		const [scan] = await chrome.scripting.executeScript({
			target,
			func: () => (globalThis as unknown as { __cvitae: Cvitae }).__cvitae.scan().files
		});
		const files = scan?.result as { id: string }[];
		const [attached] = await chrome.scripting.executeScript({
			target,
			func: (id: string, base64: string) =>
				(globalThis as unknown as { __cvitae: Cvitae }).__cvitae.attach(id, {
					name: 'Ama-Owusu-Mensah-CV-Harbour-Bank.pdf',
					type: 'application/pdf',
					base64
				}),
			args: [files[0]!.id, btoa('%PDF-1.7\n')]
		});
		const [job] = await chrome.scripting.executeScript({
			target,
			func: () => (globalThis as unknown as { __cvitae: Cvitae }).__cvitae.job()
		});
		return { files: files.length, attached: attached?.result, job: job?.result };
	}, JOB_URL);

	expect(result).toMatchObject({
		files: 1,
		attached: true,
		job: { title: 'Data Engineer', company: 'Harbour Bank', from: 'posting' }
	});
	const file = await page.locator('#resume').evaluate((input: HTMLInputElement) => ({
		name: input.files?.[0]?.name,
		type: input.files?.[0]?.type,
		size: input.files?.[0]?.size
	}));
	expect(file).toEqual({
		name: 'Ama-Owusu-Mensah-CV-Harbour-Bank.pdf',
		type: 'application/pdf',
		size: 9
	});
});

test('does not offer to fill when the user turned the offer off', async ({ context }) => {
	await connect(context);
	const worker = context.serviceWorkers()[0]!;
	await worker.evaluate(() => chrome.storage.local.set({ offer: false }));

	const page = await context.newPage();
	await page.goto(JOB_URL);
	await page.waitForTimeout(2000);

	await expect(page.locator('cvitae-prompt')).toHaveCount(0);
});

test('the side panel page loads and shows the account', async ({ context, extensionId }) => {
	await connect(context);
	const errors: string[] = [];
	const panel = await context.newPage();
	panel.on('pageerror', (error) => errors.push(error.message));
	panel.on('console', (message) => {
		if (message.type() === 'error') errors.push(message.text());
	});

	await panel.goto(`chrome-extension://${extensionId}/sidepanel.html`);

	await expect(panel.getByRole('combobox', { name: 'Fill from' })).toHaveValue('profile:p1');
	await expect(panel.getByText('Connected to ama@example.com.')).toBeVisible();
	// The panel is its own active tab here, which no extension may read.
	await expect(panel.getByText('The extension cannot work on this page.')).toBeVisible();
	expect(errors).toEqual([]);
});
