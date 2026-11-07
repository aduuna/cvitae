import type { Page } from '@playwright/test';
import type { CvContent } from '../../src/lib/cv/types.ts';
import { expect, test, type MockApi } from './mock-api';

const DOC = '00000000-0000-4000-8000-0000000000d1';
const JOB = '00000000-0000-4000-8000-0000000000b1';

function content(): CvContent {
	return {
		schema_version: 1,
		basics: {
			name: 'Ama Owusu-Mensah',
			headline: 'Data engineer',
			email: 'ama@example.com',
			phone: '',
			location: '',
			links: []
		},
		summary: 'Data engineer who builds batch and streaming pipelines.',
		sections: []
	};
}

/** One saved job, and a CV linked to it or not. */
function seed(api: MockApi, linked: boolean) {
	const now = new Date().toISOString();
	api.jobs.push({
		id: JOB,
		title: 'Senior Data Engineer',
		company: 'Lumen Payments',
		url: null,
		description: 'Senior Data Engineer\nLumen Payments\nSpark, Kafka and Airflow.',
		analysis: null,
		created_at: now,
		updated_at: now
	});
	api.documents.push({
		id: DOC,
		name: 'Data engineering CV',
		template_id: 'classic',
		mode: 'structured',
		page_count: 1,
		profile_id: null,
		job_id: linked ? JOB : null,
		created_at: now,
		updated_at: now,
		content: content()
	});
}

async function hasHorizontalScroll(page: Page): Promise<boolean> {
	return page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
}

test.describe('ATS score at 1280px', () => {
	test.use({ viewport: { width: 1280, height: 800 } });

	test('checks a CV against a saved job from the editor', async ({ page, api }) => {
		seed(api, false);
		await page.goto(`/app/documents/${DOC}`);

		await page.getByRole('button', { name: 'ATS score' }).click();
		const dialog = page.getByRole('dialog', { name: 'ATS score' });
		await expect(dialog.getByLabel('Job')).toHaveValue(JOB);
		await dialog.getByRole('button', { name: 'Check against this job' }).click();

		await expect(dialog.getByText('Strong match')).toBeVisible();
		await expect(dialog.getByText('For Senior Data Engineer at Lumen Payments')).toBeVisible();
		await expect(dialog.getByRole('heading', { name: 'Not in your profile (1)' })).toBeVisible();
		await expect(dialog.getByRole('heading', { name: 'Readability' })).toBeVisible();
		expect(api.documents[0]?.job_id).toBe(JOB);
		expect(await hasHorizontalScroll(page)).toBe(false);
		await page.screenshot({ path: 'test-results/ats-dialog-1280.png', animations: 'disabled' });

		// The footer's Close, after the header's.
		await dialog.getByRole('button', { name: 'Close' }).last().click();
		await expect(page.getByRole('button', { name: 'ATS score 83 of 100' })).toHaveText('ATS 83');
	});
});

test.describe('ATS score at 768px', () => {
	test.use({ viewport: { width: 768, height: 1024 } });

	test('the score sits in the top bar and its dialog fits', async ({ page, api }) => {
		seed(api, true);
		await page.goto(`/app/documents/${DOC}`);

		const button = page.getByRole('button', { name: 'ATS score 83 of 100' });
		// Just the score beside the icon, so the CV's name keeps its room.
		await expect(button).toHaveText('83', { useInnerText: true });
		expect(await hasHorizontalScroll(page)).toBe(false);
		await button.click();
		await expect(
			page.getByRole('dialog', { name: 'ATS score' }).getByText('Strong match')
		).toBeVisible();
		expect(await hasHorizontalScroll(page)).toBe(false);
		await page.screenshot({ path: 'test-results/ats-dialog-768.png', animations: 'disabled' });
	});
});
