import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthError } from '#lib/api/client.ts';
import Login from '../../src/routes/login/+page.svelte';

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

describe('sign-in page', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		session().status = 'signed-out';
	});

	it('offers Google and email-link sign-in', () => {
		render(Login);

		expect(screen.getByRole('heading', { level: 1, name: 'Chameleon vitae' })).toBeVisible();
		const google = screen.getByRole('button', { name: 'Continue with Google' });
		expect(google).toBeVisible();
		// Google's mark, decorative: the button's name stays the text.
		expect(google.querySelector('img')).toHaveAttribute('src', 'brand/google-g.svg');
		expect(google.querySelector('img')).toHaveAttribute('alt', '');
		expect(screen.getByRole('button', { name: 'Email me a sign-in link' })).toBeVisible();
		expect(screen.getByText('New here? Your first sign-in creates your account.')).toBeVisible();
	});

	it('links back to the landing page', () => {
		render(Login);

		expect(screen.getByRole('link', { name: 'Chameleon vitae home' })).toHaveAttribute('href', '/');
	});

	it('signs in with Google', async () => {
		render(Login);

		await userEvent.click(screen.getByRole('button', { name: 'Continue with Google' }));

		expect(session().signInWithGoogle).toHaveBeenCalledOnce();
	});

	it('shows sign-in errors', async () => {
		session().signInWithGoogle.mockRejectedValueOnce(new AuthError('Pop-ups are blocked.'));
		render(Login);

		await userEvent.click(screen.getByRole('button', { name: 'Continue with Google' }));

		expect(await screen.findByRole('alert')).toHaveTextContent('Pop-ups are blocked.');
	});

	it('emails a sign-in link back to this site', async () => {
		render(Login);

		await userEvent.type(screen.getByLabelText('Email'), ' ada@example.com ');
		await userEvent.click(screen.getByRole('button', { name: 'Email me a sign-in link' }));

		expect(session().sendEmailLink).toHaveBeenCalledWith(
			'ada@example.com',
			`${location.origin}/auth/complete`
		);
		expect(await screen.findByRole('heading', { name: 'Check your email' })).toBeVisible();
		expect(screen.getByText('ada@example.com')).toBeVisible();

		await userEvent.click(screen.getByRole('button', { name: 'Use a different email' }));
		expect(screen.getByLabelText('Email')).toBeVisible();
	});

	it('sends signed-in users to their documents', () => {
		session().status = 'signed-in';

		render(Login);

		expect(mocks.goto).toHaveBeenCalledWith('/app/documents', { replaceState: true });
		expect(screen.queryByRole('button', { name: 'Continue with Google' })).toBeNull();
	});
});
