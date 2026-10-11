import type { Page } from '@playwright/test';
import type { CvContent } from '../../src/lib/cv/types.ts';
import { expect, test, type MockApi } from './mock-api';

const AD = 'Senior Data Engineer\nLumen Payments\nSpark, Kafka and Airflow.';

function seedProfile(api: MockApi) {
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
	api.profiles.push({
		id: '00000000-0000-4000-8000-00000000aaaa',
		name: 'Data engineering',
		is_default: true,
		created_at: new Date().toISOString(),
		updated_at: new Date().toISOString(),
		content
	});
}

function nav(page: Page) {
	return page.getByRole('navigation', { name: 'Main' });
}

async function hasHorizontalScroll(page: Page): Promise<boolean> {
	return page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
}

test.describe('M4: plans and billing', () => {
	test('shows AI runs in the side nav and blocks tailoring at the limit', async ({ page, api }) => {
		seedProfile(api);
		api.aiRuns = 5;
		await page.goto('/app/tailor');

		await expect(nav(page).getByText('5 of 5 AI runs')).toBeVisible();
		await expect(page.getByRole('status')).toContainText(
			'You have used all 5 AI runs this month. Upgrade to Pro for 150.'
		);
		await page.getByLabel('Job description').fill(AD);
		await expect(page.getByRole('button', { name: 'Tailor CV' })).toBeDisabled();
		expect(api.aiCalls).toEqual([]);
		await page.screenshot({ path: 'test-results/tailor-limit-1280.png' });

		await page.getByRole('button', { name: 'See plans' }).click();
		await expect(page).toHaveURL(/\/app\/settings\?tab=billing$/);
		await expect(page.getByRole('heading', { name: 'Billing' })).toBeInViewport();
	});

	test('upgrades to Pro through Paystack, and the limits change', async ({ page, api }) => {
		seedProfile(api);
		await page.goto('/app/profiles');
		await expect(page.getByRole('button', { name: 'New profile' })).toBeDisabled();
		await expect(page.getByRole('status')).toContainText(
			'You have 1 profile, the most on Free. Delete one or upgrade to Pro for 10.'
		);

		await page.goto('/app/settings');
		const billing = page.locator('#billing');
		await expect(billing.getByRole('meter', { name: 'Profiles' })).toHaveAttribute(
			'aria-valuetext',
			'1 of 1'
		);
		await expect(billing.getByText('3 CVs, 1 profile and 5 AI runs a month.')).toBeVisible();
		await billing.getByRole('button', { name: 'Upgrade to Pro' }).click();

		// Paystack sends the user back with a reference, which is verified.
		await expect(page.getByText('You are on Pro now.')).toBeVisible();
		await expect(page).toHaveURL(/\/app\/settings\?tab=billing$/);
		await expect(billing.getByText('Renews on 10 November.')).toBeVisible();
		await expect(billing.getByRole('meter', { name: 'AI runs this month' })).toHaveAttribute(
			'aria-valuetext',
			'0 of 150'
		);
		await expect(nav(page).getByText('Pro', { exact: true })).toBeVisible();
		await expect(nav(page).getByText('0 of 150 AI runs')).toBeVisible();
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
		seedProfile(api);
		api.aiRuns = 3;
		await page.setViewportSize({ width: 768, height: 1024 });
		await page.goto('/app/settings?tab=billing');

		await expect(page.locator('#billing').getByText('3 of 5')).toBeVisible();
		expect(await hasHorizontalScroll(page)).toBe(false);
		await page.screenshot({ path: 'test-results/settings-billing-768.png', fullPage: true });
	});
});
