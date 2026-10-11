import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthError } from '#lib/api/client.ts';
import Complete from '../../src/routes/auth/complete/+page.svelte';

const mocks = vi.hoisted(() => ({
	goto: vi.fn(),
	session: null as never,
	pending: { value: null as string | null }
}));

vi.mock('$app/navigation', () => ({ goto: mocks.goto }));
vi.mock('$app/paths', () => ({
	resolve: (path: string) => path,
	asset: (path: string) => path
}));
vi.mock('#lib/auth/session.svelte.ts', async () => {
	const { sessionMock } = await import('./session-mock');
	mocks.session = sessionMock() as never;
	return {
		session: mocks.session,
		pendingEmail: { get: () => mocks.pending.value, set: vi.fn() }
	};
});

function session() {
	return mocks.session as unknown as ReturnType<typeof import('./session-mock').sessionMock>;
}

describe('email link completion', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		session().isEmailLink.mockReturnValue(true);
		mocks.pending.value = null;
	});

	it('completes with the remembered email and opens documents', async () => {
		mocks.pending.value = 'ada@example.com';

		render(Complete);

		await vi.waitFor(() =>
			expect(mocks.goto).toHaveBeenCalledWith('/app/documents', { replaceState: true })
		);
		expect(session().completeEmailLink).toHaveBeenCalledWith('ada@example.com', location.href);
	});

	it('asks for the email on another device', async () => {
		render(Complete);

		expect(await screen.findByRole('heading', { name: 'Confirm your email' })).toBeVisible();
		await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com');
		await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));

		expect(session().completeEmailLink).toHaveBeenCalledWith('ada@example.com', location.href);
	});

	it('explains expired links', async () => {
		mocks.pending.value = 'ada@example.com';
		session().completeEmailLink.mockRejectedValueOnce(
			new AuthError('This sign-in link has expired or was already used. Request a new one.')
		);

		render(Complete);

		expect(await screen.findByRole('alert')).toHaveTextContent('has expired');
		expect(mocks.goto).not.toHaveBeenCalled();
	});

	it('refuses pages that are not sign-in links', async () => {
		session().isEmailLink.mockReturnValue(false);

		render(Complete);

		expect(
			await screen.findByRole('heading', { name: 'This link cannot sign you in' })
		).toBeVisible();
		await userEvent.click(screen.getByRole('button', { name: 'Back to sign in' }));
		expect(mocks.goto).toHaveBeenCalledWith('/');
	});
});
