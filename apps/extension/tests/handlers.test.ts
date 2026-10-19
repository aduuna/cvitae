import { beforeEach, describe, expect, it, vi } from 'vitest';
import { connectApi } from '../src/lib/api.ts';
import { createHandlers } from '../src/lib/handlers.ts';
import { installChrome, type FakeChrome } from './chrome.ts';
import { sampleData } from './helpers.ts';

const APP = 'http://localhost:5173';
const JOB_PAGE = 'https://boards.greenhouse.io/harbour/jobs/4012345';
const at = '2026-10-01T09:00:00Z';

const session = {
	email: 'ada@example.com',
	display_name: null,
	profiles: [{ id: 'p1', name: 'Data engineering', is_default: true, updated_at: at }],
	documents: [{ id: 'd1', name: 'Harbour Bank CV', job_id: 'j1', placeholders: 0, updated_at: at }],
	jobs: [
		{
			id: 'j1',
			title: 'Data engineer',
			company: 'Harbour Bank',
			url: JOB_PAGE,
			created_at: at,
			updated_at: at
		}
	]
};

function json(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

const revoked = () =>
	json({ error: { code: 'unauthorized', message: 'This browser is no longer connected.' } }, 401);

describe('background handlers', () => {
	let fake: FakeChrome;
	let calls: string[];
	let respond: (path: string, token: string | null) => Response;

	const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
		const request = input as Request;
		const path = new URL(request.url).pathname;
		calls.push(path);
		const token = request.headers.get('Authorization')?.replace('Bearer ', '') ?? null;
		return respond(path, token);
	});

	const handlers = () =>
		createHandlers({ api: (token) => connectApi(token, fetchImpl as typeof fetch), now: () => 0 });

	beforeEach(() => {
		fake = installChrome();
		calls = [];
		respond = (path, token) => {
			if (token !== 'cvx_good') return revoked();
			if (path === '/api/v1/extension/session') return json(session);
			if (path.endsWith('/application')) return json(sampleData());
			return json({}, 404);
		};
	});

	it('keeps a token from the connect page once the api accepts it', async () => {
		const reply = await handlers().handle(
			{ type: 'connect', token: 'cvx_good', email: 'typed@example.com' },
			{ url: `${APP}/app/extension` }
		);

		expect(reply).toEqual({ ok: true, email: 'ada@example.com' });
		expect(fake.store).toMatchObject({ token: 'cvx_good', email: 'ada@example.com' });
	});

	it('refuses a token the api does not accept', async () => {
		const reply = await handlers().handle(
			{ type: 'connect', token: 'cvx_bad', email: 'ada@example.com' },
			{ url: `${APP}/app/extension` }
		);

		expect(reply).toMatchObject({ ok: false });
		expect(fake.store['token']).toBeUndefined();
	});

	it('takes tokens and answers about the connection on the app only', async () => {
		const elsewhere = { url: 'https://evil.example/app/extension' };
		await fake.chrome.storage.local.set({ token: 'cvx_good', email: 'ada@example.com' });

		expect(
			await handlers().handle({ type: 'connect', token: 'cvx_good', email: 'x' }, elsewhere)
		).toMatchObject({ ok: false });
		expect(await handlers().handle({ type: 'connection' }, elsewhere)).toEqual({
			connectedAs: null
		});
		expect(
			await handlers().handle({ type: 'connection' }, { url: `${APP}/app/extension` })
		).toEqual({ connectedAs: 'ada@example.com' });
		expect(calls).toEqual([]);
	});

	it('offers to fill only when connected and allowed', async () => {
		const h = handlers();
		expect(await h.handle({ type: 'offer', url: JOB_PAGE }, { url: JOB_PAGE })).toEqual({
			show: false
		});

		await fake.chrome.storage.local.set({ token: 'cvx_good' });
		expect(await h.handle({ type: 'offer', url: JOB_PAGE }, { url: JOB_PAGE })).toEqual({
			show: true,
			source: 'Harbour Bank CV'
		});

		await fake.chrome.storage.local.set({ offer: false });
		expect(await h.handle({ type: 'offer', url: JOB_PAGE }, { url: JOB_PAGE })).toEqual({
			show: false
		});
	});

	it('loads the session once a minute at most', async () => {
		await fake.chrome.storage.local.set({ token: 'cvx_good' });
		const h = handlers();

		await h.handle({ type: 'offer', url: JOB_PAGE }, { url: JOB_PAGE });
		await h.handle({ type: 'offer', url: JOB_PAGE }, { url: JOB_PAGE });

		expect(calls).toEqual(['/api/v1/extension/session']);
	});

	it("gives the data of the page's tailored CV when the user fills", async () => {
		await fake.chrome.storage.local.set({ token: 'cvx_good' });

		const reply = await handlers().handle(
			{ type: 'application', url: 'https://harbourbank.com/embed' },
			{ url: 'https://harbourbank.com/embed', tabUrl: JOB_PAGE }
		);

		expect(reply).toMatchObject({ ok: true, data: { email: 'ama@example.com' } });
		expect(calls).toContain('/api/v1/extension/documents/d1/application');
	});

	it('forgets a revoked token', async () => {
		await fake.chrome.storage.local.set({ token: 'cvx_revoked', email: 'ada@example.com' });

		const reply = await handlers().handle(
			{ type: 'application', url: JOB_PAGE },
			{ url: JOB_PAGE }
		);

		expect(reply).toEqual({
			ok: false,
			message: 'Open the extension from the toolbar and connect it to your account.'
		});
		expect(fake.store['token']).toBeUndefined();
	});

	it('passes on other failures', async () => {
		await fake.chrome.storage.local.set({ token: 'cvx_good' });
		respond = () =>
			json({ error: { code: 'service_unavailable', message: 'Try again soon.' } }, 503);

		const reply = await handlers().handle(
			{ type: 'application', url: JOB_PAGE },
			{ url: JOB_PAGE }
		);

		expect(reply).toEqual({ ok: false, message: 'Try again soon.' });
		expect(fake.store['token']).toBe('cvx_good');
	});
});
