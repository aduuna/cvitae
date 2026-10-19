import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FIND_TIMEOUT_MS } from '#lib/extension/connect.ts';
import ExtensionPage from '../../src/routes/app/extension/+page.svelte';
import { fakeExtension, ready } from '../extension/fake-extension.ts';
import { fakeApi, json } from '../extension/fake-api.ts';

const mocks = vi.hoisted(() => ({ goto: vi.fn(), session: null as never }));

vi.mock('$app/navigation', () => ({ goto: mocks.goto }));
vi.mock('$app/paths', () => ({ resolve: (path: string) => path }));
vi.mock('#lib/auth/session.svelte.ts', async () => {
	const { sessionMock } = await import('./session-mock');
	mocks.session = sessionMock() as never;
	return { session: mocks.session };
});

const connection = {
	id: 'c1',
	label: 'Chrome on macOS',
	created_at: '2026-10-18T09:00:00Z',
	last_used_at: null
};
const created = { ...connection, token: 'cvx_secret' };

describe('the browser extension page', () => {
	let extension: ReturnType<typeof fakeExtension> | null = null;

	beforeEach(() => {
		(mocks.session as { email: string | null }).email = 'ada@example.com';
	});
	afterEach(() => {
		extension?.remove();
		extension = null;
		vi.unstubAllGlobals();
	});

	it('says what the extension does and how it handles data', async () => {
		fakeApi({ 'GET /api/v1/extension/connections': () => json([]) });

		render(ExtensionPage);

		expect(screen.getByText(/Attaches the CV you tailored for the job/)).toBeVisible();
		expect(screen.getByRole('link', { name: 'How it handles your data' })).toHaveAttribute(
			'href',
			'/privacy'
		);
		expect(screen.getByText(/not in the browser stores yet/)).toBeVisible();
		expect(await screen.findByText('No browser is connected.')).toBeVisible();
	});

	it('connects, hands the token to the extension, and lists the browser', async () => {
		let listed: unknown[] = [];
		const api = fakeApi({
			'GET /api/v1/extension/connections': () => json(listed),
			'POST /api/v1/extension/connections': () => {
				listed = [connection];
				return json(created, 201);
			}
		});
		extension = fakeExtension((message) =>
			message.type === 'ping'
				? ready()
				: { source: 'cvitae-extension', type: 'connected', email: 'ada@example.com' }
		);

		render(ExtensionPage);
		await userEvent.click(await screen.findByRole('button', { name: 'Connect extension' }));

		expect(await screen.findByText('Connected to ada@example.com.')).toBeVisible();
		expect(extension.received.at(-1)).toEqual({
			source: 'cvitae-app',
			type: 'token',
			token: 'cvx_secret',
			email: 'ada@example.com'
		});
		const list = screen.getByRole('heading', { name: 'Connected browsers' }).closest('section')!;
		expect(await within(list).findByText('Chrome on macOS')).toBeVisible();
		expect(api.calls.filter((c) => c === 'GET /api/v1/extension/connections')).toHaveLength(2);
	});

	it('says when this browser is connected already', async () => {
		fakeApi({ 'GET /api/v1/extension/connections': () => json([connection]) });
		extension = fakeExtension(() => ready('ada@example.com'));

		render(ExtensionPage);

		expect(
			await screen.findByText('This browser is connected to ada@example.com already.')
		).toBeVisible();
		expect(screen.getByRole('button', { name: 'Connect again' })).toBeVisible();
	});

	it('removes the connection when the extension refuses the token', async () => {
		const api = fakeApi({
			'GET /api/v1/extension/connections': () => json([]),
			'POST /api/v1/extension/connections': () => json(created, 201),
			'DELETE /api/v1/extension/connections/c1': () => new Response(null, { status: 204 })
		});
		extension = fakeExtension((message) =>
			message.type === 'ping'
				? ready()
				: { source: 'cvitae-extension', type: 'failed', message: 'Could not reach the server.' }
		);

		render(ExtensionPage);
		await userEvent.click(await screen.findByRole('button', { name: 'Connect extension' }));

		expect(await screen.findByRole('alert')).toHaveTextContent('Could not reach the server.');
		await vi.waitFor(() => expect(api.calls).toContain('DELETE /api/v1/extension/connections/c1'));
	});

	it('explains what to do when the extension is missing', async () => {
		fakeApi({ 'GET /api/v1/extension/connections': () => json([]) });
		render(ExtensionPage);

		// The page waits FIND_TIMEOUT_MS for an answer before it gives up.
		expect(
			await screen.findByText(/not installed in this browser/, {}, { timeout: FIND_TIMEOUT_MS * 2 })
		).toBeVisible();
		extension = fakeExtension(() => ready());
		await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
		expect(await screen.findByRole('button', { name: 'Connect extension' })).toBeVisible();
	});
});
