import type { Page } from '@playwright/test';
import type { CvDocument } from '../../src/lib/cv/types';
import { expect, starterContent, test, type MockApi } from './mock-api';

function seedDocument(api: MockApi): CvDocument {
	const content = starterContent();
	content.basics.name = 'Ama Owusu-Mensah';
	content.summary = 'Engineer with **9 years** of work.';
	content.sections[0]?.experience.push({
		id: 'role-1',
		org: 'Northwind Consulting',
		role: 'Lead data engineer',
		location: '',
		dates: { start: '2021-03', end: null },
		stack: ['Python', 'Spark'],
		bullets: [{ id: 'bullet-1', text: 'Built a platform', source_id: 'profile-bullet-1' }],
		engagements: []
	});
	const now = new Date().toISOString();
	const doc: CvDocument = {
		id: 'doc-1',
		name: 'Ama CV',
		template_id: 'classic',
		custom_layout: false,
		page_count: 1,
		profile_id: null,
		job_id: null,
		created_at: now,
		updated_at: now,
		content,
		layout: null
	};
	api.documents.push(doc);
	return doc;
}

/** Type at the end of a CodeMirror editor. */
async function typeAtEnd(page: Page, editor: string, text: string) {
	await page.getByRole('textbox', { name: editor }).click();
	await page.keyboard.press('ControlOrMeta+End');
	await page.keyboard.insertText(text);
}

function editingMode(page: Page) {
	return page.getByRole('radiogroup', { name: 'Editing mode' });
}

for (const width of [1280, 768]) {
	test.describe(`editing modes at ${width}px`, () => {
		test.use({ viewport: { width, height: 900 } });

		test('edits the same CV as a form, as Markdown and as a Typst layout', async ({
			page,
			api
		}) => {
			const doc = seedDocument(api);
			// The top bar's badge needs room (1024px); the Typst panel says it at any width.
			const customLayout =
				width >= 1024
					? page.getByText('Custom layout', { exact: true })
					: page.getByText('This CV has its own layout.');
			await page.goto(`/app/documents/${doc.id}`);
			await expect(editingMode(page).getByRole('radio', { name: 'Form' })).toBeChecked();

			// Markdown: the form's content as text; a valid edit saves and keeps the bullet's identity.
			await editingMode(page).getByRole('radio', { name: 'Markdown' }).click();
			const markdown = page.getByRole('textbox', { name: 'CV as Markdown' });
			await expect(markdown).toContainText('# Ama Owusu-Mensah');
			await expect(markdown).toContainText('## Experience {experience}');
			await expect(markdown).toContainText('Stack: Python, Spark');
			await typeAtEnd(
				page,
				'CV as Markdown',
				'\n## Volunteering {custom}\n\n- Mentor at a coding club.'
			);
			await expect(page.getByText('Saved', { exact: true })).toBeVisible();
			await expect
				.poll(() => api.documents[0]?.content.sections.at(-1)?.custom[0]?.text)
				.toBe('Mentor at a coding club.');
			expect(api.documents[0]?.content.sections[0]?.experience[0]?.bullets[0]).toEqual({
				id: 'bullet-1',
				text: 'Built a platform',
				source_id: 'profile-bullet-1'
			});

			// An invalid line is reported and not saved; leaving asks first.
			await typeAtEnd(page, 'CV as Markdown', '\nloose text');
			await expect(page.getByText('Not saved: fix these lines first.')).toBeVisible();
			await expect(page.getByText('Start each line of a custom section with "- "')).toBeVisible();
			await editingMode(page).getByRole('radio', { name: 'Form' }).click();
			const leave = page.getByRole('dialog', { name: 'Leave Markdown?' });
			await leave.getByRole('button', { name: 'Keep editing' }).click();
			await expect(editingMode(page).getByRole('radio', { name: 'Markdown' })).toBeChecked();
			await editingMode(page).getByRole('radio', { name: 'Form' }).click();
			await leave.getByRole('button', { name: 'Discard changes' }).click();

			// Back in the form, with the section added in Markdown.
			await expect(editingMode(page).getByRole('radio', { name: 'Form' })).toBeChecked();
			await expect(page.getByRole('region', { name: 'Volunteering' })).toBeVisible();

			// Typst: the template's code until the first edit makes it this CV's own layout.
			await editingMode(page).getByRole('radio', { name: 'Typst' }).click();
			await expect(page.getByRole('textbox', { name: 'main.typ' })).toContainText('// classic');
			await expect(page.getByText('This is the Classic layout.')).toBeVisible();
			await typeAtEnd(page, 'main.typ', '\n#text[Custom]');
			await expect(customLayout).toBeVisible();
			await expect.poll(() => api.documents[0]?.layout).toContain('#text[Custom]');
			// The mock renderer writes "custom layout" on the page instead of the template id.
			await expect(page.getByRole('img', { name: 'Page 1 of 1' })).toHaveAttribute(
				'src',
				/custom%20layout/
			);

			await page.getByRole('tab', { name: 'data.json' }).click();
			await expect(page.getByRole('textbox', { name: 'data.json, read-only' })).toContainText(
				'"name": "Ama Owusu-Mensah"'
			);
			await page.getByRole('tab', { name: 'main.typ' }).click();
			await page.screenshot({ path: `test-results/editor-typst-${width}.png` });
			expect(
				await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
			).toBe(false);

			// Switching template replaces the custom layout, after asking.
			await page.getByRole('combobox', { name: 'Template' }).selectOption('compact');
			const switchDialog = page.getByRole('dialog', { name: 'Switch template?' });
			await expect(switchDialog).toContainText('Switching to Compact replaces your custom layout.');
			await switchDialog.getByRole('button', { name: 'Switch template' }).click();
			await expect(customLayout).toBeHidden();
			await expect.poll(() => api.documents[0]?.template_id).toBe('compact');
			expect(api.documents[0]?.layout).toBeNull();
			await expect(page.getByRole('textbox', { name: 'main.typ' })).toContainText('// compact');

			// Reset to template removes a custom layout.
			await typeAtEnd(page, 'main.typ', '\n// mine');
			await expect.poll(() => api.documents[0]?.layout).toContain('// mine');
			await page.getByRole('button', { name: 'Reset to template' }).click();
			await page
				.getByRole('dialog', { name: 'Reset layout?' })
				.getByRole('button', { name: 'Reset to template' })
				.click();
			await expect.poll(() => api.documents[0]?.layout).toBeNull();
			await expect(page.getByRole('textbox', { name: 'main.typ' })).not.toContainText('// mine');

			// The mode is remembered.
			await page.reload();
			await expect(editingMode(page).getByRole('radio', { name: 'Typst' })).toBeChecked();
		});

		test('shows why export stopped beside the preview, in any mode', async ({ page, api }) => {
			const doc = seedDocument(api);
			doc.content.summary = 'Engineer with [[years]] of work.';
			await page.goto(`/app/documents/${doc.id}`);
			await editingMode(page).getByRole('radio', { name: 'Markdown' }).click();

			await page.getByRole('button', { name: 'Export PDF' }).click();

			const preview = page.getByRole('region', { name: 'Preview' });
			await expect(
				preview.getByText('Export stopped: this CV has 1 placeholder to fill in.')
			).toBeVisible();
			await expect(page.getByRole('textbox', { name: 'CV as Markdown' })).toBeVisible();
			await page.screenshot({ path: `test-results/editor-placeholders-${width}.png` });
			await preview.getByRole('button', { name: 'Show placeholders' }).click();
			await preview.getByRole('list', { name: 'Placeholders' }).getByRole('button').first().click();
			await expect(editingMode(page).getByRole('radio', { name: 'Form' })).toBeChecked();
			await expect(page.getByRole('textbox', { name: 'Summary' })).toBeFocused();
		});
	});
}

test.describe('editing under 768px', () => {
	test.use({ viewport: { width: 600, height: 900 } });

	test('shows why export stopped above both views', async ({ page, api }) => {
		const doc = seedDocument(api);
		doc.content.summary = 'Engineer with [[years]] of work.';
		await page.goto(`/app/documents/${doc.id}`);

		await page.getByRole('button', { name: 'Export PDF' }).click();
		const notice = page.getByText('Export stopped: this CV has 1 placeholder to fill in.');
		await expect(notice).toBeVisible();
		await page
			.getByRole('radiogroup', { name: 'View' })
			.getByRole('radio', { name: 'Preview' })
			.click();

		await expect(notice).toBeVisible();
		await expect(page.getByRole('img', { name: 'Page 1 of 1' })).toBeVisible();
	});
});

test.describe('a CV with a custom layout', () => {
	test.use({ viewport: { width: 1280, height: 900 } });

	test('exports a PDF and is still edited in the form, whose content the layout reads', async ({
		page,
		api
	}) => {
		const doc = seedDocument(api);
		doc.layout = '#let mine = 1\n';
		doc.custom_layout = true;
		await page.goto(`/app/documents/${doc.id}`);
		await expect(page.getByText('Custom layout', { exact: true })).toBeVisible();

		const summary = page.getByRole('textbox', { name: 'Summary' });
		await summary.fill('Engineer with **10 years** of work.');
		await expect(page.getByText('Saved', { exact: true })).toBeVisible();
		await expect
			.poll(() => api.documents[0]?.content.summary)
			.toBe('Engineer with **10 years** of work.');
		// Saving the content keeps the layout.
		expect(api.documents[0]?.layout).toBe('#let mine = 1\n');
		await expect(page.getByRole('img', { name: 'Page 1 of 1' })).toHaveAttribute(
			'src',
			/custom%20layout/
		);

		const download = page.waitForEvent('download');
		await page.getByRole('button', { name: 'Export PDF' }).click();
		expect((await download).suggestedFilename()).toBe('Ama-Owusu-Mensah-CV.pdf');
	});

	test('starts from the template the CV uses, including one of the user own', async ({
		page,
		api
	}) => {
		api.customTemplates.push({
			id: 'u-aaaaaaaaa2',
			name: 'Slate',
			description: 'Navy rules.',
			paper_sizes: ['a4', 'us-letter'],
			target_pages: 1,
			custom: true,
			status: 'ready',
			main_typ: '#import "/_lib/cv.typ": *\n// Slate\n',
			upload_id: null
		});
		const doc = seedDocument(api);
		doc.template_id = 'u-aaaaaaaaa2';
		await page.goto(`/app/documents/${doc.id}`);

		await editingMode(page).getByRole('radio', { name: 'Typst' }).click();

		await expect(page.getByRole('textbox', { name: 'main.typ' })).toContainText('// Slate');
		await expect(page.getByText('This is the Slate layout.')).toBeVisible();
	});

	test('keeps the ATS score where the content is, and Edit with AI in the form', async ({
		page,
		api
	}) => {
		const doc = seedDocument(api);
		await page.goto(`/app/documents/${doc.id}`);
		const ats = page.getByRole('button', { name: /ATS score/ });
		const ai = page.getByRole('button', { name: 'Edit with AI' });
		await expect(ai).toBeVisible();

		await editingMode(page).getByRole('radio', { name: 'Markdown' }).click();
		await expect(ats).toBeVisible();
		await expect(ai).toBeHidden();

		await editingMode(page).getByRole('radio', { name: 'Typst' }).click();
		await expect(ats).toBeVisible();

		await editingMode(page).getByRole('radio', { name: 'Form' }).click();
		await expect(ai).toBeVisible();
	});

	test('opens the form field of a part clicked in the preview, from Markdown too', async ({
		page,
		api
	}) => {
		const doc = seedDocument(api);
		await page.goto(`/app/documents/${doc.id}`);
		await editingMode(page).getByRole('radio', { name: 'Markdown' }).click();
		const preview = page.getByRole('img', { name: 'Page 1 of 1' });
		await expect(preview).toBeVisible();
		const box = (await preview.boundingBox())!;
		const name = {
			x: box.x + (60 / 595.28) * box.width,
			y: box.y + (54 / 841.89) * box.height
		};

		// Valid Markdown: the click goes straight to the form field.
		await page.mouse.click(name.x, name.y);
		await expect(editingMode(page).getByRole('radio', { name: 'Form' })).toBeChecked();
		await expect(page.getByRole('textbox', { name: 'Name', exact: true }).first()).toBeFocused();

		// Markdown with an error asks first, then still opens the field.
		await editingMode(page).getByRole('radio', { name: 'Markdown' }).click();
		await typeAtEnd(page, 'CV as Markdown', '\nloose text');
		await expect(page.getByText('Not saved: fix these lines first.')).toBeVisible();
		await page.mouse.click(name.x, name.y);
		await page
			.getByRole('dialog', { name: 'Leave Markdown?' })
			.getByRole('button', { name: 'Discard changes' })
			.click();
		await expect(editingMode(page).getByRole('radio', { name: 'Form' })).toBeChecked();
		await expect(page.getByRole('textbox', { name: 'Name', exact: true }).first()).toBeFocused();
	});
});

test.describe('what leaving or switching does to unsaved and replaced work', () => {
	test.use({ viewport: { width: 1280, height: 900 } });

	test('keeps the layout a template switch replaces in version history', async ({ page, api }) => {
		const doc = seedDocument(api);
		doc.layout = '#let mine = 1\n';
		doc.custom_layout = true;
		await page.goto(`/app/documents/${doc.id}`);

		await page.getByRole('combobox', { name: 'Template' }).selectOption('compact');
		await page
			.getByRole('dialog', { name: 'Switch template?' })
			.getByRole('button', { name: 'Switch template' })
			.click();
		await expect.poll(() => api.documents[0]?.layout).toBeNull();
		await expect(page.getByText('Custom layout', { exact: true })).toBeHidden();

		await page.getByRole('button', { name: 'Version history' }).click();
		await expect(page.getByRole('list', { name: 'Versions' })).toContainText(
			'Kept before a change'
		);
		await page.getByRole('button', { name: 'Restore version 1' }).click();

		await expect(page.getByText('Custom layout', { exact: true })).toBeVisible();
		expect(api.documents[0]?.layout).toBe('#let mine = 1\n');
	});

	test('asks before leaving Markdown that has errors, in the app and on closing the tab', async ({
		page,
		api
	}) => {
		const doc = seedDocument(api);
		await page.goto(`/app/documents/${doc.id}`);
		await editingMode(page).getByRole('radio', { name: 'Markdown' }).click();
		await typeAtEnd(page, 'CV as Markdown', '\nloose text');
		await expect(page.getByText('Not saved: fix these lines first.')).toBeVisible();

		await page.getByRole('link', { name: 'Profiles' }).click();
		const leave = page.getByRole('dialog', { name: 'Leave this page?' });
		await leave.getByRole('button', { name: 'Keep editing' }).click();
		await expect(page).toHaveURL(/\/app\/documents\/doc-1$/);
		await expect(page.getByRole('textbox', { name: 'CV as Markdown' })).toContainText('loose text');

		const prompt = page.waitForEvent('dialog');
		await page.close({ runBeforeUnload: true });
		const closing = await prompt;
		expect(closing.type()).toBe('beforeunload');
		await closing.dismiss();

		await page.getByRole('link', { name: 'Profiles' }).click();
		await leave.getByRole('button', { name: 'Discard changes' }).click();
		await expect(page).toHaveURL(/\/app\/profiles/);
	});

	test('does not ask when there is nothing unsaved', async ({ page, api }) => {
		const doc = seedDocument(api);
		await page.goto(`/app/documents/${doc.id}`);
		await editingMode(page).getByRole('radio', { name: 'Markdown' }).click();
		await typeAtEnd(page, 'CV as Markdown', '\n## Volunteering {custom}\n\n- Mentor.');
		await expect(page.getByText('Saved', { exact: true })).toBeVisible();

		await page.getByRole('link', { name: 'Profiles' }).click();

		await expect(page).toHaveURL(/\/app\/profiles/);
		await expect(page.getByRole('dialog')).toHaveCount(0);
	});
});
