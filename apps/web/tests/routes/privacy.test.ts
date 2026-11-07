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

	it('says what drafting answers sends, and that nothing of it is stored', () => {
		render(Privacy);

		const drafts = screen.getByText(/Draft answers and Redraft send the questions you ticked/);
		expect(drafts).toHaveTextContent(/without your email, phone number or links/);
		expect(drafts).toHaveTextContent(/are not stored, and neither are the drafts/);
	});

	it('says a CV uploaded for a template goes to Claude, and what is kept', () => {
		render(Privacy);

		const template = screen.getByText(/Making a template from a CV you like always uses Claude/);
		expect(template).toHaveTextContent(/whichever model you chose/);
		expect(template).toHaveTextContent(/sent to Anthropic/);
		expect(template).toHaveTextContent(
			/does not copy your uploaded CV's name, contact details or text/
		);
		expect(template).toHaveTextContent(/we keep the code, not Claude's replies/);
		expect(screen.getByText(/A CV you upload to make a template is kept like one/)).toBeVisible();
	});

	it('says how to reach us', () => {
		render(Privacy);

		const links = screen.getAllByRole('link', { name: CONTACT_EMAIL });
		expect(links.length).toBeGreaterThan(1);
		for (const link of links) expect(link).toHaveAttribute('href', `mailto:${CONTACT_EMAIL}`);
	});
});
