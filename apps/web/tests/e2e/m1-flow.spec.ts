import type { Page } from '@playwright/test';
import { expect, test } from './mock-api';

async function hasHorizontalScroll(page: Page): Promise<boolean> {
	return page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
}

async function buildProfile(page: Page) {
	await page.goto('/app/documents');
	await expect(page.getByText('Start with a profile')).toBeVisible();
	await page.getByRole('button', { name: 'New profile' }).last().click();
	await expect(page).toHaveURL(/\/app\/profiles\/new$/);
	await page.getByRole('tab', { name: 'Enter manually' }).click();
	await page.getByRole('button', { name: 'Create empty profile' }).click();
	await expect(page).toHaveURL(/\/app\/profiles\/[\w-]+$/);
	await expect(page).not.toHaveURL(/\/new$/);

	await page.getByRole('textbox', { name: 'Profile name' }).fill('Data engineering');
	await page.getByRole('textbox', { name: 'Name', exact: true }).fill('Ama Owusu-Mensah');
	await page.getByRole('textbox', { name: 'Headline' }).fill('Senior data engineer');
	await page.getByRole('textbox', { name: 'Summary' }).fill('Engineer with **9 years** of work.');

	const experience = page.getByRole('region', { name: 'Experience' });
	await experience.getByRole('button', { name: 'Add role' }).click();
	await experience.getByRole('textbox', { name: 'Organisation' }).fill('Northwind Consulting');
	await experience.getByRole('textbox', { name: 'Role', exact: true }).fill('Lead data engineer');
	await experience.getByRole('textbox', { name: 'Start' }).fill('2021-03');
	await experience.getByRole('textbox', { name: 'Tech stack' }).fill('Python, Spark');
	await experience.getByRole('textbox', { name: 'Bullet 1' }).fill('Built a platform');
	await experience.getByRole('button', { name: 'Add bullet' }).click();
	await experience
		.getByRole('textbox', { name: 'Bullet 2' })
		.fill('Served [[number of analysts]] analysts');
	await experience.getByRole('button', { name: 'Add client' }).click();
	await page.getByRole('textbox', { name: 'Name', exact: true }).nth(1).fill('Harbour Bank');
	return experience;
}

test.describe('M1 flows at 1280px', () => {
	test.use({ viewport: { width: 1280, height: 800 } });

	test('builds a profile by hand, reorders it and keeps it after a reload', async ({
		page,
		api
	}) => {
		const experience = await buildProfile(page);

		// Keyboard reorder: the second bullet moves up and keeps focus.
		await experience.getByRole('textbox', { name: 'Bullet 2' }).press('Alt+ArrowUp');
		await expect(experience.getByRole('textbox', { name: 'Bullet 1' }).first()).toHaveValue(
			'Served [[number of analysts]] analysts'
		);
		await expect(experience.getByRole('textbox', { name: 'Bullet 1' }).first()).toBeFocused();
		// Drag reorder: Skills (third section) above Education.
		await page
			.getByRole('button', { name: 'Move section 3 of 3' })
			.dragTo(page.getByRole('region', { name: 'Education' }), { targetPosition: { x: 40, y: 4 } });
		await expect(page.getByText('Saved', { exact: true })).toBeVisible();
		await page.screenshot({ path: 'test-results/profile-1280.png' });

		await page.reload();
		await expect(page.getByRole('textbox', { name: 'Profile name' })).toHaveValue(
			'Data engineering'
		);
		const titles = page.getByRole('textbox', { name: 'Section title' });
		await expect(titles).toHaveCount(3);
		expect(
			await titles.evaluateAll((els) => els.map((el) => (el as HTMLInputElement).value))
		).toEqual(['Experience', 'Skills', 'Education']);
		const role = api.profiles[0]?.content.sections[0]?.experience[0];
		expect(role?.stack).toEqual(['Python', 'Spark']);
		expect(role?.bullets.map((bullet) => bullet.text)).toEqual([
			'Served [[number of analysts]] analysts',
			'Built a platform'
		]);
		expect(role?.engagements[0]?.name).toBe('Harbour Bank');
	});

	test('creates three CVs, edits one with live preview, restores a version and exports', async ({
		page,
		api
	}) => {
		await buildProfile(page);
		await expect(page.getByText('Saved', { exact: true })).toBeVisible();

		await page.goto('/app/documents');
		for (const name of ['Bank CV', 'Retail CV', 'Startup CV']) {
			await page.getByRole('button', { name: 'New CV' }).first().click();
			const dialog = page.getByRole('dialog', { name: 'New CV' });
			await expect(dialog.getByRole('combobox', { name: 'Profile' })).toHaveValue(/.+/);
			await dialog.getByRole('textbox', { name: 'Name' }).fill(name);
			await dialog.getByRole('button', { name: 'Create CV' }).click();
			await expect(page).toHaveURL(/\/app\/documents\/[\w-]+$/);
			await page.goto('/app/documents');
		}
		await expect(page.getByRole('list', { name: 'CVs' }).getByRole('link')).toHaveText([
			'Startup CV',
			'Retail CV',
			'Bank CV'
		]);
		expect(await hasHorizontalScroll(page)).toBe(false);
		await page.screenshot({ path: 'test-results/documents-1280.png' });

		// Live preview.
		await page.getByRole('link', { name: 'Bank CV' }).click();
		const pageImage = page.getByRole('img', { name: 'Page 1 of 1' });
		await expect(pageImage).toBeVisible();
		const first = await pageImage.getAttribute('src');
		await page.getByRole('textbox', { name: 'Headline' }).fill('Lead engineer for banks');
		await expect(pageImage).not.toHaveAttribute('src', first ?? '');
		expect(decodeURIComponent((await pageImage.getAttribute('src')) ?? '')).toContain(
			'Lead engineer for banks'
		);

		// Save a version, then switch template.
		await page.getByRole('button', { name: 'Version history' }).click();
		await page.getByRole('button', { name: 'Save version' }).click();
		await expect(page.getByRole('list', { name: 'Versions' })).toContainText('Version 1');
		await page.getByRole('dialog').getByRole('button', { name: 'Close' }).last().click();
		await page.getByRole('combobox', { name: 'Template' }).selectOption('compact');
		await expect
			.poll(async () => decodeURIComponent((await pageImage.getAttribute('src')) ?? ''))
			.toContain('compact');
		expect(api.documents.find((doc) => doc.name === 'Bank CV')?.template_id).toBe('compact');
		await page.screenshot({ path: 'test-results/editor-1280.png' });

		// A later edit, then restore version 1.
		await page.getByRole('textbox', { name: 'Headline' }).fill('A worse headline');
		await expect(page.getByText('Saved', { exact: true })).toBeVisible();
		await page.getByRole('button', { name: 'Version history' }).click();
		await page.getByRole('button', { name: 'Restore version 1' }).click();
		await expect(page.getByRole('dialog')).toHaveCount(0);
		await expect(page.getByRole('textbox', { name: 'Headline' })).toHaveValue(
			'Lead engineer for banks'
		);

		// Export is stopped by the placeholder; the banner leads to it; export anyway downloads.
		await page.getByRole('button', { name: 'Export PDF' }).click();
		await expect(
			page.getByText('Export stopped: this CV has 1 placeholder to fill in.')
		).toBeVisible();
		await page.getByRole('button', { name: 'Show placeholders' }).click();
		await page.getByRole('list', { name: 'Placeholders' }).getByRole('button').first().click();
		await expect(
			page
				.getByRole('region', { name: 'Experience' })
				.getByRole('textbox', { name: 'Bullet 2' })
				.first()
		).toBeFocused();
		await page.getByRole('button', { name: 'More export options' }).click();
		const download = page.waitForEvent('download');
		await page.getByRole('menuitem', { name: 'Export anyway' }).click();
		expect((await download).suggestedFilename()).toBe('Ama-Owusu-Mensah-CV.pdf');
		expect(api.previewCalls).toBeGreaterThan(2);
	});

	test('renames, duplicates and deletes CVs from the list', async ({ page }) => {
		await buildProfile(page);
		await expect(page.getByText('Saved', { exact: true })).toBeVisible();
		await page.goto('/app/documents');
		await page.getByRole('button', { name: 'New CV' }).first().click();
		await page.getByRole('dialog').getByRole('button', { name: 'Create CV' }).click();
		await expect(page).toHaveURL(/\/app\/documents\/[\w-]+$/);
		await page.goto('/app/documents');

		await page.getByRole('button', { name: 'Actions for Data engineering CV' }).click();
		await page.getByRole('menuitem', { name: 'Rename' }).click();
		await page.getByRole('dialog').getByRole('textbox', { name: 'Name' }).fill('Bank CV');
		await page.getByRole('button', { name: 'Rename CV' }).click();
		await expect(page.getByRole('link', { name: 'Bank CV' })).toBeVisible();

		await page.getByRole('button', { name: 'Actions for Bank CV' }).click();
		await page.getByRole('menuitem', { name: 'Duplicate' }).click();
		await expect(page.getByRole('link', { name: 'Bank CV (copy)' })).toBeVisible();

		await page.getByRole('button', { name: 'Actions for Bank CV (copy)' }).click();
		await page.getByRole('menuitem', { name: 'Delete' }).click();
		await page.getByRole('dialog').getByRole('button', { name: 'Delete CV' }).click();
		await expect(page.getByRole('link', { name: 'Bank CV (copy)' })).toHaveCount(0);
		await expect(page.getByRole('link', { name: 'Bank CV' })).toBeVisible();
	});
});

test.describe('editor at 768px', () => {
	test.use({ viewport: { width: 768, height: 1024 } });

	test('keeps form and preview side by side without horizontal scroll', async ({ page }) => {
		await buildProfile(page);
		await expect(page.getByText('Saved', { exact: true })).toBeVisible();
		await page.goto('/app/documents');
		await page.getByRole('button', { name: 'New CV' }).first().click();
		await page.getByRole('dialog').getByRole('button', { name: 'Create CV' }).click();

		await expect(page.getByRole('img', { name: 'Page 1 of 1' })).toBeVisible();
		await expect(page.getByRole('textbox', { name: 'Headline' })).toBeEditable();
		await expect(page.getByRole('separator', { name: 'Resize edit panel' })).toBeVisible();
		expect(await hasHorizontalScroll(page)).toBe(false);
		await page.screenshot({ path: 'test-results/editor-768.png' });
	});
});

test.describe('editor under 768px', () => {
	test.use({ viewport: { width: 700, height: 1000 } });

	test('stacks the preview behind a toggle and makes the form read-only', async ({ page }) => {
		await buildProfile(page);
		await expect(page.getByText('Saved', { exact: true })).toBeVisible();
		await page.goto('/app/documents');
		await page.getByRole('button', { name: 'New CV' }).first().click();
		await page.getByRole('dialog').getByRole('button', { name: 'Create CV' }).click();

		await expect(page.getByText('Editing needs a wider screen.')).toBeVisible();
		await expect(page.getByRole('textbox', { name: 'Headline' })).toBeDisabled();
		await page.getByRole('radio', { name: 'Preview' }).click();
		await expect(page.getByRole('img', { name: 'Page 1 of 1' })).toBeVisible();
		await expect(page.getByRole('button', { name: 'Export PDF' })).toBeEnabled();
	});
});
