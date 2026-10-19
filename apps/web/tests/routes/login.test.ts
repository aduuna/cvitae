import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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
		expect(screen.queryByLabelText('Password')).toBeNull();
	});

	it('links back to the landing page', () => {
		render(Login);

		expect(screen.getByRole('link', { name: 'Chameleon vitae home' })).toHaveAttribute('href', '/');
	});

	it('links the privacy policy', () => {
		render(Login);

		expect(screen.getByRole('link', { name: 'privacy policy' })).toHaveAttribute(
			'href',
			'/privacy'
		);
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

	describe('at /login?password', () => {
		beforeEach(() => window.history.replaceState({}, '', '/login?password'));
		afterEach(() => window.history.replaceState({}, '', '/'));

		it('asks for a password in place of the email link', () => {
			render(Login);

			expect(screen.getByText('Use the email and password you were given.')).toBeVisible();
			expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'password');
			expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeVisible();
			expect(screen.queryByRole('button', { name: 'Email me a sign-in link' })).toBeNull();
		});

		it('signs in with it', async () => {
			render(Login);

			await userEvent.type(screen.getByLabelText('Email'), ' review@example.com ');
			await userEvent.type(screen.getByLabelText('Password'), 'secret');
			await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));

			expect(session().signInWithPassword).toHaveBeenCalledWith('review@example.com', 'secret');
		});

		it('shows a wrong password', async () => {
			session().signInWithPassword.mockRejectedValueOnce(
				new AuthError('The email or password is wrong. Check both and try again.')
			);
			render(Login);

			await userEvent.type(screen.getByLabelText('Email'), 'review@example.com');
			await userEvent.type(screen.getByLabelText('Password'), 'wrong');
			await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));

			expect(await screen.findByRole('alert')).toHaveTextContent(
				'The email or password is wrong. Check both and try again.'
			);
		});
	});

	describe('sent here from an app page', () => {
		afterEach(() => window.history.replaceState({}, '', '/'));

		it('goes back to it after signing in', () => {
			window.history.replaceState({}, '', '/login?next=%2Fapp%2Fextension');
			session().status = 'signed-in';

			render(Login);

			expect(mocks.goto).toHaveBeenCalledWith('/app/extension', { replaceState: true });
		});

		it('carries it in the email sign-in link', async () => {
			window.history.replaceState({}, '', '/login?next=%2Fapp%2Fextension');
			render(Login);

			await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com');
			await userEvent.click(screen.getByRole('button', { name: 'Email me a sign-in link' }));

			expect(session().sendEmailLink).toHaveBeenCalledWith(
				'ada@example.com',
				`${location.origin}/auth/complete?next=%2Fapp%2Fextension`
			);
		});
	});
});
