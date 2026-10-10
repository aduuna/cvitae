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

test.describe('M3 at 1280px', () => {
	test.use({ viewport: { width: 1280, height: 800 } });

	test('imports pasted text, reviews the draft and saves it as a profile', async ({
		page,
		api
	}) => {
		await page.goto('/app/import');
		await page.getByRole('tab', { name: 'Paste text' }).click();
		await page.getByLabel('CV text').fill('Ama Owusu-Mensah, lead data engineer at Northwind.');
		await page.getByRole('button', { name: 'Import CV' }).click();

		await expect(
			page.getByText('Imported from pasted text. Check every entry before using it.')
		).toBeVisible();
		await expect(page.getByText('Extracted with MiMo Flash.', { exact: false })).toBeVisible();
		await expect(page.getByLabel('Profile name')).toHaveValue('Ama Owusu-Mensah');
		await page.screenshot({ path: 'test-results/import-review-1280.png' });

		await page.getByRole('button', { name: 'Save profile' }).click();

		await expect(page).toHaveURL(/\/app\/profiles\/[\w-]+$/);
		expect(api.profiles.map((p) => p.name)).toEqual(['Ama Owusu-Mensah']);
		expect(api.aiCalls).toEqual([{ task: 'import', model: 'mimo-flash' }]);
	});

	test('imports a file, keeps it, and imports it again with another model', async ({
		page,
		api
	}) => {
		await page.goto('/app/import');
		await page.locator('input[type="file"]').setInputFiles({
			name: 'Ama CV.pdf',
			mimeType: 'application/pdf',
			buffer: Buffer.from('%PDF-1.7')
		});
		await page.getByRole('button', { name: 'Import CV' }).click();
		await expect(page.getByText('Imported from Ama CV.pdf.', { exact: false })).toBeVisible();
		await page.getByRole('button', { name: 'Discard' }).click();

		await expect(page.getByRole('heading', { name: 'Earlier uploads' })).toBeVisible();
		await page.getByLabel('AI model').selectOption({ label: 'Gemini Flash-Lite' });
		await page.getByRole('button', { name: 'Import again' }).click();

		await expect(
			page.getByText('Extracted with Gemini Flash-Lite.', { exact: false })
		).toBeVisible();
		expect(api.aiCalls.map((call) => call.model)).toEqual(['mimo-flash', 'gemini-flash-lite']);
		expect(api.uploads).toHaveLength(1);
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
		await page.getByRole('menuitem', { name: 'Gemini Flash (Pro)' }).click();
		await expect(page.getByText('Generated with Gemini Flash for', { exact: false })).toBeVisible();
		expect(api.documents.map((doc) => doc.id)).not.toContain(first);
		expect(api.documents).toHaveLength(1);
		expect(api.aiCalls).toEqual([
			{ task: 'tailor', model: 'mimo-flash' },
			{ task: 'tailor', model: 'gemini-flash' }
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

	test('the default model in settings is preselected on Import', async ({ page, api }) => {
		await page.goto('/app/settings');
		await page.getByLabel('Default AI model').selectOption({ label: 'Claude Haiku' });
		await expect(page.getByText('New imports and tailoring use Claude Haiku.')).toBeVisible();
		expect(api.me.preferred_ai_model).toBe('claude-haiku');

		await page.getByRole('link', { name: 'Import' }).click();

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
