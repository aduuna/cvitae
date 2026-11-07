import type { Page } from '@playwright/test';
import type { CvContent } from '../../src/lib/cv/types.ts';
import { expect, test, type MockApi } from './mock-api';

const PDF = {
	name: 'my-cv.pdf',
	mimeType: 'application/pdf',
	buffer: Buffer.from('%PDF-1.7\n%mock\n')
};

function seedCv(api: MockApi) {
	const content: CvContent = {
		schema_version: 1,
		basics: {
			name: 'Ama Owusu-Mensah',
			headline: 'Data engineer',
			email: '',
			phone: '',
			location: '',
			links: []
		},
		summary: '',
		sections: []
	};
	const stamp = new Date().toISOString();
	api.profiles.push({
		id: '00000000-0000-4000-8000-00000000aaaa',
		name: 'Data engineering',
		is_default: true,
		created_at: stamp,
		updated_at: stamp,
		content
	});
	api.documents.push({
		id: '00000000-0000-4000-8000-00000000dddd',
		name: 'Bank CV',
		template_id: 'classic',
		mode: 'structured',
		page_count: 1,
		profile_id: '00000000-0000-4000-8000-00000000aaaa',
		job_id: null,
		created_at: stamp,
		updated_at: stamp,
		content
	});
}

function readyTemplate(api: MockApi, name = 'Slate') {
	api.customTemplates.push({
		id: 'u-aaaaaaaaa2',
		name,
		description: 'Navy rules, tight spacing and a sans-serif header.',
		paper_sizes: ['a4', 'us-letter'],
		target_pages: 1,
		custom: true,
		status: 'ready',
		main_typ: '#import "/_lib/cv.typ": *\n#let cv = json("data.json")\n// Slate\n',
		upload_id: null
	});
}

async function hasHorizontalScroll(page: Page): Promise<boolean> {
	return page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
}

function addDialog(page: Page) {
	return page.getByRole('dialog', { name: 'Add your own template' });
}

async function openAddDialog(page: Page) {
	await page.goto('/app/templates');
	await page.getByRole('button', { name: /Add your own/ }).click();
	return addDialog(page);
}

for (const viewport of [
	{ width: 1280, height: 800 },
	{ width: 768, height: 1024 }
]) {
	test.describe(`bring your own template at ${viewport.width}px`, () => {
		test.use({ viewport });

		test('uploads a PDF, previews the draft, saves it and uses it in the editor', async ({
			page,
			api
		}) => {
			seedCv(api);
			await page.goto('/app/templates');

			await expect(page.getByRole('heading', { name: 'Built-in templates' })).toBeVisible();
			await expect(page.getByRole('heading', { name: 'Your templates' })).toBeVisible();
			await page.getByRole('button', { name: /Add your own/ }).click();

			const dialog = addDialog(page);
			await expect(dialog).toContainText('runs on Claude');
			await expect(dialog).toContainText('The text of that CV is not copied');
			await expect(dialog.getByRole('button', { name: 'Make template' })).toBeDisabled();
			await page.screenshot({ path: `test-results/byo-choose-${viewport.width}.png` });

			// A PDF at a time; progress shows while Claude works.
			await dialog.getByTestId('dropzone-input').setInputFiles(PDF);
			await expect(dialog.getByText('my-cv.pdf')).toBeVisible();
			await dialog.getByRole('button', { name: 'Make template' }).click();
			await expect(dialog.getByRole('progressbar')).toBeVisible();
			await expect(dialog.getByText("Reading your CV's design")).toBeVisible();
			await page.screenshot({ path: `test-results/byo-running-${viewport.width}.png` });

			// The draft: a preview of the user's profile in the new template, and a name to keep.
			const preview = dialog.getByRole('img', { name: 'Preview of the new template' });
			await expect(preview).toBeVisible();
			expect(decodeURIComponent((await preview.getAttribute('src')) ?? '')).toContain(
				'Ama Owusu-Mensah'
			);
			await expect(dialog.getByLabel('Template name')).toHaveValue('Slate');
			await expect(dialog).toContainText('Made with Claude Haiku');
			expect(api.aiCalls.at(-1)).toEqual({ task: 'template', model: 'claude-haiku' });
			expect(await hasHorizontalScroll(page)).toBe(false);
			await page.screenshot({ path: `test-results/byo-review-${viewport.width}.png` });

			await dialog.getByLabel('Template name').fill('Slate navy');
			await dialog.getByRole('button', { name: 'Save template' }).click();
			await expect(addDialog(page)).toHaveCount(0);
			expect(api.customTemplates.map((t) => [t.name, t.status])).toEqual([['Slate navy', 'ready']]);

			// Its card, after the built-in ones, with the live preview.
			const card = page.getByRole('listitem').filter({ hasText: 'Slate navy' });
			await expect(
				card.getByRole('img', { name: 'Preview of the Slate navy template' })
			).toBeVisible();
			await expect(page.getByText('Template saved.')).toBeVisible();
			expect(await hasHorizontalScroll(page)).toBe(false);
			await page.screenshot({ path: `test-results/byo-cards-${viewport.width}.png` });

			// Set as default, then the editor lists it after the built-in ones and switches to it.
			await card.getByRole('button', { name: 'Set as default' }).click();
			await expect(card.getByText('Default')).toBeVisible();
			expect(api.me.default_template_id).toBe(api.customTemplates[0]?.id);

			await page.getByRole('link', { name: 'Documents' }).click();
			await page.getByRole('link', { name: 'Bank CV' }).click();
			const picker = page.getByRole('combobox', { name: 'Template' });
			await expect(picker.locator('option')).toHaveText(['Classic', 'Compact', 'Slate navy']);
			await picker.selectOption({ label: 'Slate navy' });
			const customId = api.customTemplates[0]!.id;
			await expect.poll(() => api.documents[0]?.template_id).toBe(customId);
			const pageImage = page.getByRole('img', { name: 'Page 1 of 1' });
			await expect
				.poll(async () => decodeURIComponent((await pageImage.getAttribute('src')) ?? ''))
				.toContain(customId);
			expect(await hasHorizontalScroll(page)).toBe(false);
			await page.screenshot({ path: `test-results/byo-editor-${viewport.width}.png` });

			// The CV can go back to a built-in template and return.
			await picker.selectOption('classic');
			await expect.poll(() => api.documents[0]?.template_id).toBe('classic');
			await picker.selectOption({ label: 'Slate navy' });
			await expect.poll(() => api.documents[0]?.template_id).toBe(customId);
		});

		test('lists it in the pickers for a new CV and for tailoring', async ({ page, api }) => {
			seedCv(api);
			readyTemplate(api);

			await page.goto('/app/documents');
			await page.getByRole('button', { name: 'New CV' }).first().click();
			await expect(
				page.getByRole('dialog', { name: 'New CV' }).getByLabel('Template').locator('option')
			).toHaveText(['Classic', 'Compact', 'Slate']);

			await page.goto('/app/tailor');
			await expect(page.getByLabel('Template').locator('option')).toHaveText([
				'Classic',
				'Compact',
				'Slate'
			]);
		});

		test('renames, reads the source of, and deletes a template', async ({ page, api }) => {
			seedCv(api);
			readyTemplate(api);
			api.documents[0]!.template_id = 'u-aaaaaaaaa2';
			api.me.default_template_id = 'u-aaaaaaaaa2';
			await page.goto('/app/templates');
			const card = page.getByRole('listitem').filter({ hasText: 'Slate' });
			await expect(card.getByText('Default')).toBeVisible();

			await card.getByRole('button', { name: 'Actions for Slate' }).click();
			await page.getByRole('menuitem', { name: 'Rename' }).click();
			await page.getByRole('dialog', { name: 'Rename template' }).getByLabel('Name').fill('Ink');
			await page.getByRole('button', { name: 'Rename template' }).click();
			await expect(page.getByRole('heading', { name: 'Ink' })).toBeVisible();
			expect(api.customTemplates[0]?.name).toBe('Ink');

			// Read only: the Typst is there, and it cannot be typed into.
			await page.getByRole('button', { name: 'Actions for Ink' }).click();
			await page.getByRole('menuitem', { name: 'View source' }).click();
			const source = page.getByRole('dialog', { name: 'Source of Ink' });
			await expect(source.locator('.cm-content')).toContainText('#import "/_lib/cv.typ": *');
			await expect(source.getByRole('textbox', { name: 'Source of Ink' })).toHaveAttribute(
				'aria-readonly',
				'true'
			);
			expect(await hasHorizontalScroll(page)).toBe(false);
			await page.screenshot({ path: `test-results/byo-source-${viewport.width}.png` });
			await source.getByRole('button', { name: 'Close' }).last().click();

			// Deleting says where its CVs go, and does it.
			await page.getByRole('button', { name: 'Actions for Ink' }).click();
			await page.getByRole('menuitem', { name: 'Delete' }).click();
			const confirm = page.getByRole('dialog', { name: 'Delete template' });
			await expect(confirm).toContainText('CVs that use it switch to your default template');
			await confirm.getByRole('button', { name: 'Delete template' }).click();
			await expect(page.getByRole('heading', { name: 'Ink' })).toHaveCount(0);
			expect(api.customTemplates).toEqual([]);
			expect(api.documents[0]?.template_id).toBe('classic');
			expect(api.me.default_template_id).toBe('classic');
			await expect(
				page.getByRole('listitem').filter({ hasText: 'Classic' }).getByText('Default')
			).toBeVisible();
		});
	});
}

test.describe('bring your own template: refusals and limits', () => {
	test.use({ viewport: { width: 1280, height: 800 } });

	test('refuses a DOCX before anything runs', async ({ page, api }) => {
		const dialog = await openAddDialog(page);
		await dialog.getByTestId('dropzone-input').setInputFiles({
			name: 'cv.docx',
			mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
			buffer: Buffer.from('docx')
		});
		await expect(dialog.getByRole('alert')).toContainText('A DOCX does not keep how a CV looks');
		await expect(dialog.getByRole('button', { name: 'Make template' })).toBeDisabled();
		expect(api.aiCalls).toEqual([]);
	});

	test('says when the server refuses a file, and when a template cannot be made', async ({
		page,
		api
	}) => {
		const dialog = await openAddDialog(page);
		await dialog.getByTestId('dropzone-input').setInputFiles(PDF);

		api.templateFailure = {
			status: 422,
			code: 'validation_failed',
			message: 'This file is not a PDF. Upload a PDF file.'
		};
		await dialog.getByRole('button', { name: 'Make template' }).click();
		await expect(dialog.getByRole('alert')).toContainText('This file is not a PDF');
		await expect(dialog.getByRole('button', { name: 'Make template' })).toBeEnabled();

		api.templateFailure = {
			status: 422,
			code: 'template_failed',
			message:
				'We could not turn this CV into a template that renders correctly. Try a PDF with a simpler layout, or a different CV.',
			details: { issues: ['compile_error'] }
		};
		await dialog.getByRole('button', { name: 'Make template' }).click();
		await expect(dialog.getByRole('alert')).toContainText('Try a PDF with a simpler layout');
		expect(api.customTemplates).toEqual([]);

		api.templateFailure = {
			status: 504,
			code: 'provider_timeout',
			message:
				'Claude could not finish this template. Wait a minute and try again, or try a PDF with a simpler layout.'
		};
		await dialog.getByRole('button', { name: 'Make template' }).click();
		await expect(dialog.getByRole('alert')).toContainText('Wait a minute and try again');
	});

	test('discarding a draft deletes it', async ({ page, api }) => {
		const dialog = await openAddDialog(page);
		await dialog.getByTestId('dropzone-input').setInputFiles(PDF);
		await dialog.getByRole('button', { name: 'Make template' }).click();
		await expect(dialog.getByLabel('Template name')).toBeVisible();
		expect(api.customTemplates).toHaveLength(1);

		await dialog.getByRole('button', { name: 'Discard' }).click();
		await expect(addDialog(page)).toHaveCount(0);
		expect(api.customTemplates).toEqual([]);
		await expect(page.getByRole('button', { name: /Add your own/ })).toBeEnabled();
	});

	test('closing a draft asks before it is lost', async ({ page, api }) => {
		const dialog = await openAddDialog(page);
		await dialog.getByTestId('dropzone-input').setInputFiles(PDF);
		await dialog.getByRole('button', { name: 'Make template' }).click();
		await expect(dialog.getByLabel('Template name')).toBeVisible();

		await page.keyboard.press('Escape');
		const confirm = page.getByRole('dialog', { name: 'Discard this template?' });
		await expect(confirm).toBeVisible();
		await confirm.getByRole('button', { name: 'Keep reviewing' }).click();
		await expect(dialog.getByLabel('Template name')).toBeVisible();
		expect(api.customTemplates).toHaveLength(1);

		await page.keyboard.press('Escape');
		await page.getByRole('button', { name: 'Discard template' }).click();
		await expect(addDialog(page)).toHaveCount(0);
		expect(api.customTemplates).toEqual([]);
	});

	test('a Free user at the limit sees why and cannot add another', async ({ page, api }) => {
		readyTemplate(api);
		await page.goto('/app/templates');

		await expect(page.locator('#template-blocked')).toContainText(
			'You have 1 custom template, the most on Free.'
		);
		await expect(page.getByRole('button', { name: /Add your own/ })).toBeDisabled();
		await expect(page.getByRole('button', { name: 'See plans' })).toBeVisible();
	});

	test('keeps the card away at the AI usage limit, and offers nothing without Claude', async ({
		page,
		api
	}) => {
		api.aiRuns = 20;
		await page.goto('/app/templates');
		await expect(page.locator('#template-blocked')).toContainText(
			"You have used all of this month's AI usage"
		);
		await expect(page.getByRole('button', { name: /Add your own/ })).toBeDisabled();

		api.aiRuns = 0;
		api.claude = false;
		await page.reload();
		await expect(page.getByRole('heading', { name: 'Built-in templates' })).toBeVisible();
		await expect(page.getByRole('button', { name: /Add your own/ })).toHaveCount(0);
		await expect(page.getByRole('heading', { name: 'Your templates' })).toHaveCount(0);
	});

	test('settings counts custom templates', async ({ page, api }) => {
		readyTemplate(api);
		await page.goto('/app/settings?tab=billing');
		await expect(page.getByRole('meter', { name: 'Custom templates' })).toHaveAttribute(
			'aria-valuetext',
			'1 of 1'
		);
	});
});
