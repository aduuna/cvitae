import type { Page } from '@playwright/test';
import type { CvContent } from '../../src/lib/cv/types.ts';
import { expect, test, type MockApi } from './mock-api';

const AD = 'Senior Data Engineer\nLumen Payments\nSpark, Kafka and Airflow.';

/** Free's limit is two profiles, so `count = 2` reaches it. */
function seedProfiles(api: MockApi, count = 1) {
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
		sections: []
	};
	for (const [i, suffix] of ['aaaa', 'bbbb'].slice(0, count).entries()) {
		api.profiles.push({
			id: `00000000-0000-4000-8000-00000000${suffix}`,
			name: i === 0 ? 'Data engineering' : 'Platform engineering',
			is_default: i === 0,
			created_at: new Date().toISOString(),
			updated_at: new Date().toISOString(),
			content
		});
	}
}

function nav(page: Page) {
	return page.getByRole('navigation', { name: 'Main' });
}

async function hasHorizontalScroll(page: Page): Promise<boolean> {
	return page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
}

test.describe('M4: plans and billing', () => {
	test('blocks tailoring at the AI usage limit, and the side nav stays quiet', async ({
		page,
		api
	}) => {
		seedProfiles(api);
		api.aiRuns = 20;
		await page.goto('/app/tailor');

		await expect(page.getByRole('status')).toContainText(
			"You have used all of this month's AI usage. Upgrade to Pro for 7 times as much."
		);
		await expect(nav(page)).not.toContainText(/AI usage|%/);
		await page.getByLabel('Job description').fill(AD);
		await expect(page.getByRole('button', { name: 'Tailor CV' })).toBeDisabled();
		expect(api.aiCalls).toEqual([]);
		await page.screenshot({ path: 'test-results/tailor-limit-1280.png' });

		await page.getByRole('button', { name: 'See plans' }).click();
		await expect(page).toHaveURL(/\/app\/settings\?tab=billing$/);
		await expect(page.getByRole('heading', { name: 'Billing' })).toBeInViewport();
	});

	test('says by each new-profile option why it is off at the profile limit', async ({
		page,
		api
	}) => {
		seedProfiles(api, 2);
		await page.goto('/app/profiles/new');

		await page.locator('input[type="file"]').setInputFiles({
			name: 'cv.pdf',
			mimeType: 'application/pdf',
			buffer: Buffer.from('%PDF-1.7')
		});
		const button = page.getByRole('button', { name: 'Import CV' });
		await expect(button).toBeDisabled();
		await expect(button).toHaveAccessibleDescription(
			'Importing a CV makes a new profile. You have 2 profiles, the most on Free. Delete one or upgrade to Pro for 10. See plans'
		);
		await page.getByRole('tab', { name: 'Enter manually' }).click();
		const empty = page.getByRole('button', { name: 'Create empty profile' });
		await expect(empty).toBeDisabled();
		await expect(empty).toHaveAccessibleDescription(
			'You have 2 profiles, the most on Free. Delete one or upgrade to Pro for 10. See plans'
		);
		await page.screenshot({ path: 'test-results/import-limit-1280.png' });
	});

	test('upgrades to Pro through Paystack, and the limits change', async ({ page, api }) => {
		seedProfiles(api, 2);
		await page.goto('/app/profiles');
		await expect(page.getByRole('button', { name: 'New profile' })).toBeDisabled();
		await expect(page.getByRole('status')).toContainText(
			'You have 2 profiles, the most on Free. Delete one or upgrade to Pro for 10.'
		);

		await page.goto('/app/settings');
		const billing = page.locator('#billing');
		await expect(billing.getByRole('meter', { name: 'Profiles' })).toHaveAttribute(
			'aria-valuetext',
			'2 of 2'
		);
		await expect(billing.getByText('4 CVs and 2 profiles.')).toBeVisible();
		await expect(
			billing.getByText('Pro includes 100 CVs, 10 profiles and 7 times the AI usage', {
				exact: false
			})
		).toBeVisible();
		await billing.getByRole('button', { name: 'Upgrade to Pro' }).click();

		// Paystack sends the user back with a reference, which is verified.
		await expect(page.getByText('You are on Pro now.')).toBeVisible();
		await expect(page).toHaveURL(/\/app\/settings\?tab=billing$/);
		await expect(billing.getByText('Renews on 10 November.')).toBeVisible();
		await expect(billing.getByRole('meter', { name: 'AI usage this month' })).toHaveAttribute(
			'aria-valuetext',
			'0%'
		);
		await expect(nav(page).getByText('Pro', { exact: true })).toBeVisible();
		await expect(billing.getByRole('button', { name: 'Upgrade to Pro' })).toHaveCount(0);
		expect(api.checkouts).toBe(1);

		await page.goto('/app/profiles');
		await expect(page.getByRole('button', { name: 'New profile' })).toBeEnabled();
		await expect(page.getByRole('status')).toHaveCount(0);

		// Pro models can be chosen now.
		await page.goto('/app/tailor');
		await page.getByLabel('Job description').fill(AD);
		await page.getByRole('combobox', { name: 'AI model' }).selectOption('claude-sonnet');
		await page.getByRole('button', { name: 'Tailor CV' }).click();
		await expect(
			page.getByText('Generated with Claude Sonnet for', { exact: false })
		).toBeVisible();

		// Managing the subscription opens Paystack's page.
		await page.route('https://paystack.test/**', (route) =>
			route.fulfill({ contentType: 'text/html', body: '<h1>Manage subscription</h1>' })
		);
		await page.goto('/app/settings');
		await page.locator('#billing').getByRole('button', { name: 'Manage subscription' }).click();
		await expect(page).toHaveURL('https://paystack.test/manage/subscriptions/SUB_1');
	});

	test('billing fits at 768px', async ({ page, api }) => {
		seedProfiles(api);
		api.aiRuns = 3;
		await page.setViewportSize({ width: 768, height: 1024 });
		await page.goto('/app/settings?tab=billing');

		await expect(page.locator('#billing').getByText('15%')).toBeVisible();
		expect(await hasHorizontalScroll(page)).toBe(false);
		await page.screenshot({ path: 'test-results/settings-billing-768.png', fullPage: true });
	});
});
