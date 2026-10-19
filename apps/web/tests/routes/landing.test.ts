import { render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Landing from '../../src/routes/+page.svelte';

const mocks = vi.hoisted(() => ({ goto: vi.fn(), session: null as never }));

vi.mock('$app/navigation', () => ({ goto: mocks.goto }));
vi.mock('$app/paths', () => ({
	resolve: (path: string) => path,
	asset: (path: string) => path
}));
vi.mock('#lib/auth/session.svelte.ts', async () => {
	const { sessionMock } = await import('./session-mock');
	mocks.session = sessionMock() as never;
	return { session: mocks.session };
});

function session() {
	return mocks.session as unknown as ReturnType<typeof import('./session-mock').sessionMock>;
}

describe('landing page', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		session().status = 'signed-out';
	});

	it('says what the app does', () => {
		render(Landing);

		expect(
			screen.getByRole('heading', { level: 1, name: 'One career, a CV for every job' })
		).toBeVisible();
		expect(screen.getByRole('img', { name: /^The CV editor/ })).toBeVisible();
	});

	it('walks through the flow in order, each step with a picture', () => {
		render(Landing);

		const flow = screen.getByRole('region', {
			name: 'From the CV you have to the CV each job needs'
		});
		// The steps themselves, not the list items drawn inside their pictures.
		const steps = [...flow.querySelectorAll<HTMLElement>(':scope ol > li')];
		expect(
			steps.map((step) => within(step).getByRole('heading', { level: 3 }).textContent)
		).toEqual([
			'Import your CV',
			'Keep a profile for each direction',
			'Tailor it to the job',
			'Edit the CV',
			'Export the PDF'
		]);
		for (const step of steps) expect(within(step).getByRole('img')).toHaveAccessibleName();
	});

	it('signs in from the top bar and gets started from the hero and the bottom', () => {
		render(Landing);

		const signIn = within(screen.getByRole('banner')).getByRole('link', { name: 'Sign in' });
		expect(signIn).toHaveAttribute('href', '/login');
		const getStarted = screen.getAllByRole('link', { name: 'Get started' });
		expect(getStarted).toHaveLength(2);
		for (const link of getStarted) expect(link).toHaveAttribute('href', '/login');
		expect(screen.getByRole('link', { name: 'See how it works' })).toHaveAttribute(
			'href',
			'#how-it-works'
		);
	});

	it('links the privacy policy from the footer', () => {
		render(Landing);

		const footer = screen.getByRole('navigation', { name: 'Footer' });
		expect(within(footer).getByRole('link', { name: 'Privacy' })).toHaveAttribute(
			'href',
			'/privacy'
		);
	});

	it('pictures the real template renders and the line drawings', () => {
		const { container } = render(Landing);

		const sources = [...container.querySelectorAll('img')].map((img) => img.getAttribute('src'));
		expect(new Set(sources)).toEqual(
			new Set([
				'logo.svg',
				'illustrations/tailor.svg',
				'illustrations/stack.svg',
				'illustrations/cover-letter.svg',
				'illustrations/extension.svg',
				'illustrations/ats.svg',
				'landing/classic.png',
				'landing/compact.png',
				'landing/modern.png',
				'landing/minimal.png',
				'landing/technical.png'
			])
		);
	});

	it('presents cover letters, the browser extension and the ATS score', () => {
		render(Landing);

		const more = screen.getByRole('region', { name: 'More help with every application' });
		expect(
			within(more)
				.getAllByRole('heading', { level: 3 })
				.map((heading) => heading.textContent)
		).toEqual(['Cover letters in your tone', 'Fill in applications faster', 'ATS score']);
		expect(within(more).queryByText(/coming soon/i)).toBeNull();
	});

	it('tells search engines and link previews what the site is', () => {
		render(Landing);

		expect(document.title).toBe('Chameleon vitae: a CV tailored to every job');
		const head = (selector: string) => document.head.querySelector(selector);
		expect(head('meta[name="description"]')?.getAttribute('content')).toContain('cvitae');
		expect(head('link[rel="canonical"]')).toHaveAttribute('href', 'https://cvitae.aduuna.dev/');
		expect(head('meta[property="og:image"]')).toHaveAttribute(
			'content',
			'https://cvitae.aduuna.dev/og.png'
		);
		const data = JSON.parse(head('script[type="application/ld+json"]')?.textContent ?? '[]');
		expect(data[0]).toMatchObject({
			'@type': 'WebSite',
			name: 'Chameleon vitae',
			alternateName: ['cvitae', 'Chameleon CV']
		});
	});

	it('shows signed-in users the page with a way into the app', async () => {
		session().status = 'signed-in';

		render(Landing);

		const banner = within(screen.getByRole('banner'));
		expect(await banner.findByRole('link', { name: 'Open app' })).toHaveAttribute(
			'href',
			'/app/documents'
		);
		expect(banner.queryByRole('link', { name: 'Sign in' })).toBeNull();
		expect(screen.queryByRole('link', { name: 'Get started' })).toBeNull();
		expect(screen.queryByText('Your first sign-in creates your account.')).toBeNull();
		expect(mocks.goto).not.toHaveBeenCalled();
	});
});
