import type { Page } from '@playwright/test';
import type { CvContent } from '../../src/lib/cv/types.ts';
import { expect, test, type MockApi } from './mock-api';

const AD = 'Senior Data Engineer\nLumen Payments\nSpark, Kafka and Airflow.';

function profileContent(): CvContent {
	const section = (kind: 'experience' | 'skills', title: string) => ({
		id: `sec-${kind}`,
		kind,
		title,
		experience: [],
		projects: [],
		education: [],
		skills: [],
		certifications: [],
		custom: []
	});
	const content: CvContent = {
		schema_version: 1,
		basics: {
			name: 'Ama Owusu-Mensah',
			headline: '',
			email: '',
			phone: '',
			location: '',
			links: []
		},
		summary: '',
		sections: [section('experience', 'Experience'), section('skills', 'Skills')]
	};
	content.sections[0]?.experience.push({
		id: 'exp-1',
		org: 'Northwind Consulting',
		role: 'Lead data engineer',
		location: '',
		dates: { start: '2021-03', end: null },
		stack: [],
		bullets: [
			{ id: 'b-1', text: 'Lead a team of **5 engineers**.', source_id: null },
			{ id: 'b-2', text: 'Moved **140** jobs to Spark.', source_id: null }
		],
		engagements: []
	});
	return content;
}

function seedProfile(api: MockApi) {
	api.profiles.push({
		id: '00000000-0000-4000-8000-00000000aaaa',
		name: 'Data engineering',
		is_default: true,
		created_at: new Date().toISOString(),
		updated_at: new Date().toISOString(),
		content: profileContent()
	});
}

async function hasHorizontalScroll(page: Page): Promise<boolean> {
	return page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
}

/** Imports pasted text and waits for the review screen. */
async function importPastedText(page: Page) {
	await page.goto('/app/profiles/new');
	await page.getByRole('tab', { name: 'Paste a CV' }).click();
	await page.getByLabel('CV text').fill('Ama Owusu-Mensah, lead data engineer at Northwind.');
	await page.getByRole('button', { name: 'Import CV' }).click();
	await expect(page.getByLabel('Profile name')).toHaveValue('Data engineering');
}

test.describe('M3 at 1280px', () => {
	test.use({ viewport: { width: 1280, height: 800 } });

	test('imports pasted text, reviews the draft and saves it as a profile', async ({
		page,
		api
	}) => {
		await page.goto('/app/profiles/new');
		await page.getByRole('tab', { name: 'Paste a CV' }).click();
		await page.getByLabel('CV text').fill('Ama Owusu-Mensah, lead data engineer at Northwind.');
		await page.getByRole('button', { name: 'Import CV' }).click();

		await expect(
			page.getByText('Imported from pasted text. Check every entry before using it.')
		).toBeVisible();
		await expect(page.getByText('Extracted with MiMo Flash.', { exact: false })).toBeVisible();
		await expect(page.getByLabel('Profile name')).toHaveValue('Data engineering');
		await page.screenshot({ path: 'test-results/import-review-1280.png' });

		await page.getByRole('button', { name: 'Save profile' }).click();

		await expect(page).toHaveURL(/\/app\/profiles\/[\w-]+$/);
		expect(api.profiles.map((p) => p.name)).toEqual(['Data engineering']);
		expect(api.aiCalls).toEqual([{ task: 'import', model: 'mimo-flash' }]);
	});

	test('asks to save an unsaved import before leaving, and saves on the way', async ({
		page,
		api
	}) => {
		await importPastedText(page);
		const settings = page.getByRole('navigation', { name: 'Main' }).getByRole('link', {
			name: 'Settings'
		});
		const prompt = page.getByRole('dialog', { name: 'Save the imported profile?' });

		await settings.click();
		await prompt.getByRole('button', { name: 'Keep reviewing' }).click();
		await expect(prompt).toBeHidden();
		await expect(page).toHaveURL(/\/app\/profiles\/new$/);
		await expect(page.getByLabel('Profile name')).toHaveValue('Data engineering');

		await settings.click();
		await prompt.getByRole('button', { name: 'Save profile' }).click();
		await expect(page).toHaveURL(/\/app\/settings$/);
		expect(api.profiles.map((p) => p.name)).toEqual(['Data engineering']);
		expect(api.aiCalls).toHaveLength(1);
	});

	test('leaves an unsaved import without saving when asked to discard it', async ({
		page,
		api
	}) => {
		await importPastedText(page);

		await page
			.getByRole('navigation', { name: 'Main' })
			.getByRole('link', { name: 'Tailor' })
			.click();
		await page
			.getByRole('dialog', { name: 'Save the imported profile?' })
			.getByRole('button', { name: 'Discard' })
			.click();

		await expect(page).toHaveURL(/\/app\/tailor$/);
		expect(api.profiles).toEqual([]);
	});

	test('a long import review scrolls inside the page, never the window', async ({ page }) => {
		await importPastedText(page);
		await page.getByRole('main').evaluate((main) => main.scrollTo(0, main.scrollHeight));

		expect(
			await page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight)
		).toBe(0);
	});

	test('the browser asks before closing a tab with an unsaved import', async ({ page }) => {
		await importPastedText(page);
		const asked = new Promise<string>((done) =>
			page.once('dialog', (dialog) => {
				done(dialog.type());
				void dialog.dismiss();
			})
		);

		await page.close({ runBeforeUnload: true });

		expect(await asked).toBe('beforeunload');
	});

	test('imports a file, keeps it, and imports it again with another model', async ({
		page,
		api
	}) => {
		await page.goto('/app/profiles/new');
		await page.locator('input[type="file"]').setInputFiles({
			name: 'Ama CV.pdf',
			mimeType: 'application/pdf',
			buffer: Buffer.from('%PDF-1.7')
		});
		await page.getByRole('button', { name: 'Import CV' }).click();
		await expect(page.getByText('Imported from Ama CV.pdf.', { exact: false })).toBeVisible();
		await page.getByRole('button', { name: 'Discard' }).click();

		await expect(page.getByRole('heading', { name: 'Or import an earlier upload' })).toBeVisible();
		await page.getByLabel('AI model').selectOption({ label: 'Gemini Flash-Lite' });
		await page.getByRole('button', { name: 'Import again' }).click();

		await expect(
			page.getByText('Extracted with Gemini Flash-Lite.', { exact: false })
		).toBeVisible();
		expect(api.aiCalls.map((call) => call.model)).toEqual(['mimo-flash', 'gemini-flash-lite']);
		expect(api.uploads).toHaveLength(1);
	});

	test('lists the 3 newest distinct uploads, and all of them on request', async ({ page, api }) => {
		const upload = (n: number, filename: string) => ({
			id: `00000000-0000-4000-8000-00000000000${n}`,
			filename,
			mime_type: 'application/pdf',
			size_bytes: 2048,
			created_at: new Date(Date.now() - n * 60_000).toISOString()
		});
		api.uploads.push(
			upload(1, 'cv.pdf'),
			upload(2, 'cv.pdf'),
			upload(3, 'design.pdf'),
			upload(4, 'data.pdf'),
			upload(5, 'old.pdf')
		);
		await page.goto('/app/profiles/new');
		const list = page
			.getByRole('region', { name: 'Or import an earlier upload' })
			.getByRole('listitem');

		await expect(list).toHaveCount(3);
		await expect(list.first()).toContainText('cv.pdf');
		await page.getByRole('button', { name: 'Show all 5 uploads' }).click();
		await expect(list).toHaveCount(5);
		await page.getByRole('tab', { name: 'Paste a CV' }).click();
		await expect(list).toHaveCount(0);
	});

	test('tailors a CV, regenerates with another model and opens it', async ({ page, api }) => {
		seedProfile(api);
		await page.goto('/app/tailor');

		await page.getByLabel('Job description').fill(AD);
		await page.getByRole('button', { name: 'Tailor CV' }).click();

		for (const name of ['Preview', 'Changes (2)', 'Gaps (2)']) {
			await expect(page.getByRole('heading', { level: 2, name })).toBeVisible();
		}
		await expect(
			page.getByText('Generated with MiMo Flash for Senior Data Engineer')
		).toBeVisible();
		await expect(page.getByRole('img', { name: 'Page 1 of 1' })).toBeVisible();
		await expect(
			page.getByText('Only add these if they are true.', { exact: false })
		).toBeVisible();
		expect(await hasHorizontalScroll(page)).toBe(false);
		await page.screenshot({ path: 'test-results/tailor-review-1280.png' });

		const first = api.documents[0]?.id;
		await page.getByRole('button', { name: 'Regenerate with' }).click();
		await expect(page.getByRole('menuitem', { name: 'MiMo Flash' })).toHaveCount(0);
		// Free plan: the Pro models are listed but cannot be chosen.
		await expect(page.getByRole('menuitem', { name: 'Gemini Flash (Pro)' })).toBeDisabled();
		await page.getByRole('menuitem', { name: 'Gemini Flash-Lite' }).click();
		await expect(
			page.getByText('Generated with Gemini Flash-Lite for', { exact: false })
		).toBeVisible();
		expect(api.documents.map((doc) => doc.id)).not.toContain(first);
		expect(api.documents).toHaveLength(1);
		expect(api.aiCalls).toEqual([
			{ task: 'tailor', model: 'mimo-flash' },
			{ task: 'tailor', model: 'gemini-flash-lite' }
		]);

		await page.getByRole('button', { name: 'Open in editor' }).click();
		await expect(page).toHaveURL(new RegExp(`/app/documents/${api.documents[0]?.id}$`));
	});

	test('tailors again from a saved job and discards the result', async ({ page, api }) => {
		seedProfile(api);
		await page.goto('/app/tailor');
		await page.getByLabel('Job description').fill(AD);
		await page.getByRole('button', { name: 'Tailor CV' }).click();
		await page.getByRole('button', { name: 'Discard' }).click();

		await expect(page.getByRole('heading', { name: 'Saved jobs' })).toBeVisible();
		expect(api.documents).toHaveLength(0);
		await page.getByRole('button', { name: 'Tailor again' }).click();
		const form = page.locator('form');
		await expect(form.getByText('Senior Data Engineer at Lumen Payments')).toBeVisible();
		await expect(form.getByText('The saved description is used.', { exact: false })).toBeVisible();
		await page.getByRole('button', { name: 'Tailor CV' }).click();

		await expect(page.getByRole('button', { name: 'Open in editor' })).toBeVisible();
		expect(api.jobs).toHaveLength(1);
	});

	test('the default model in settings is preselected for a new profile', async ({ page, api }) => {
		await page.goto('/app/settings');
		await page.getByLabel('Default AI model').selectOption({ label: 'Claude Haiku' });
		await expect(page.getByText('New imports and tailoring use Claude Haiku.')).toBeVisible();
		expect(api.me.preferred_ai_model).toBe('claude-haiku');

		await page.getByRole('link', { name: 'Profiles' }).click();
		await page.getByRole('button', { name: 'New profile' }).first().click();

		await expect(page.getByLabel('AI model')).toHaveValue('claude-haiku');
	});
});

test.describe('M3 at 768px', () => {
	test.use({ viewport: { width: 768, height: 1024 } });

	test('the review screen uses tabs and fits', async ({ page, api }) => {
		seedProfile(api);
		await page.goto('/app/tailor');
		await page.getByLabel('Job description').fill(AD);
		await page.getByRole('button', { name: 'Tailor CV' }).click();

		await expect(page.getByRole('tab', { name: 'Preview' })).toBeVisible();
		await page.getByRole('tab', { name: 'Gaps (2)' }).click();
		await expect(page.getByText('Snowflake')).toBeVisible();
		expect(await hasHorizontalScroll(page)).toBe(false);
		await page.screenshot({ path: 'test-results/tailor-review-768.png' });
	});
});
