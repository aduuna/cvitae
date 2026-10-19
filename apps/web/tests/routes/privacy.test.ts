import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { CONTACT_EMAIL } from '#lib/site.ts';
import Privacy from '../../src/routes/privacy/+page.svelte';

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path,
	asset: (path: string) => path
}));

describe('privacy policy', () => {
	it('covers what is collected, AI providers, the extension and your rights', () => {
		render(Privacy);

		expect(screen.getByRole('heading', { level: 1, name: 'Privacy policy' })).toBeVisible();
		expect(
			screen.getAllByRole('heading', { level: 2 }).map((heading) => heading.textContent)
		).toEqual([
			'What we collect',
			'How we use it',
			'AI providers',
			'The browser extension',
			'Who else handles your data',
			'How long we keep it',
			'Your rights',
			'Cookies and browser storage',
			'Children',
			'Changes'
		]);
		expect(screen.getByText(/do not sell your data/)).toBeVisible();
		expect(screen.getByText(/It does not record which pages you visit/)).toBeVisible();
	});

	it('says how to reach us', () => {
		render(Privacy);

		const links = screen.getAllByRole('link', { name: CONTACT_EMAIL });
		expect(links.length).toBeGreaterThan(1);
		for (const link of links) expect(link).toHaveAttribute('href', `mailto:${CONTACT_EMAIL}`);
	});
});
