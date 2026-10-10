import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, setAuthHeaders, unwrap, DEV_USER } from '#lib/api/client.ts';
import { pendingEmail, providerFor, Session, type ClientConfig } from '#lib/auth/session.svelte.ts';
import { fakeProvider } from './fake-provider';

const FIREBASE: ClientConfig = {
	auth_mode: 'firebase',
	firebase: { api_key: 'k', auth_domain: 'd', project_id: 'p', app_id: 'a' },
	ai_models: [{ id: 'mimo-flash', label: 'MiMo Flash', provider: 'mimo', plan: 'free' }],
	default_ai_model: 'mimo-flash',
	plans_enforced: false
};

const ME = {
	id: '00000000-0000-4000-8000-000000000001',
	email: 'ada@example.com',
	display_name: null,
	preferred_ai_model: null,
	plan: 'free',
	default_template_id: null
};

function json(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

function sessionWith(initial: string | null = null) {
	const fake = fakeProvider(initial);
	const session = new Session(
		async () => FIREBASE,
		async () => fake.provider
	);
	return { session, ...fake };
}

describe('Session', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
		localStorage.clear();
		setAuthHeaders(async () => ({ 'X-Dev-User': DEV_USER }));
	});

	it('starts signed out when nobody is signed in', async () => {
		const { session } = sessionWith();
		expect(session.status).toBe('loading');

		await session.start();

		expect(session.status).toBe('signed-out');
		expect(session.mode).toBe('firebase');
		expect(session.email).toBeNull();
	});

	it('follows sign-in and sign-out', async () => {
		const { session } = sessionWith();
		await session.start();

		await session.signInWithGoogle();
		expect([session.status, session.email]).toEqual(['signed-in', 'ada@example.com']);

		await session.signOut();
		expect(session.status).toBe('signed-out');
	});

	it('signs api requests with the provider', async () => {
		const { session } = sessionWith('ada@example.com');
		const fetch = vi.fn(async (request: Request) => {
			expect(request.headers.get('Authorization')).toBe('Bearer token-for-ada@example.com');
			expect(request.headers.get('X-Dev-User')).toBeNull();
			return json([]);
		});
		vi.stubGlobal('fetch', fetch);

		await session.start();
		await unwrap(api.GET('/api/v1/profiles'));

		expect(fetch).toHaveBeenCalledOnce();
	});

	it('remembers the email a link was sent to until the link is used', async () => {
		const { session, provider } = sessionWith();
		await session.start();

		await session.sendEmailLink('ada@example.com', 'http://localhost/auth/complete');
		expect(provider.sendEmailLink).toHaveBeenCalledWith(
			'ada@example.com',
			'http://localhost/auth/complete'
		);
		expect(pendingEmail.get()).toBe('ada@example.com');

		const link = 'http://localhost/auth/complete?oobCode=x';
		expect(session.isEmailLink(link)).toBe(true);
		await session.completeEmailLink('ada@example.com', link);

		expect(pendingEmail.get()).toBeNull();
		expect(session.status).toBe('signed-in');
	});

	it('loads me once and keeps updates', async () => {
		const { session } = sessionWith('ada@example.com');
		const fetch = vi.fn(async (request: Request) =>
			request.method === 'PATCH' ? json({ ...ME, display_name: 'Ada' }) : json(ME)
		);
		vi.stubGlobal('fetch', fetch);
		await session.start();

		await Promise.all([session.loadMe(), session.loadMe()]);
		expect(fetch).toHaveBeenCalledOnce();

		await session.updateMe({ display_name: 'Ada' });
		expect((await session.loadMe()).display_name).toBe('Ada');
		expect(session.me?.display_name).toBe('Ada');
	});

	it('forgets me when another user signs in', async () => {
		const { session, emit } = sessionWith('ada@example.com');
		vi.stubGlobal('fetch', async () => json(ME));
		await session.start();
		await session.loadMe();

		emit('bob@example.com');

		expect(session.me).toBeNull();
	});

	it('retries after loading me fails', async () => {
		const { session } = sessionWith('ada@example.com');
		const fetch = vi
			.fn()
			.mockResolvedValueOnce(json({ error: { code: 'x', message: 'Down', details: {} } }, 503))
			.mockResolvedValueOnce(json(ME));
		vi.stubGlobal('fetch', fetch);
		await session.start();

		await expect(session.loadMe()).rejects.toMatchObject({ message: 'Down' });
		await expect(session.loadMe()).resolves.toMatchObject({ email: 'ada@example.com' });
	});

	it('can start again after the config fails to load', async () => {
		const fake = fakeProvider();
		const config = vi
			.fn()
			.mockRejectedValueOnce(new Error('offline'))
			.mockResolvedValueOnce(FIREBASE);
		const session = new Session(config, async () => fake.provider);

		await expect(session.start()).rejects.toThrow('offline');
		await session.start();

		expect(session.status).toBe('signed-out');
	});

	it('loads the client config from the api', async () => {
		vi.stubGlobal('fetch', async () =>
			json({
				auth_mode: 'dev',
				firebase: null,
				ai_models: [
					{ id: 'claude-haiku', label: 'Claude Haiku', provider: 'claude', plan: 'free' }
				],
				default_ai_model: 'claude-haiku',
				plans_enforced: true
			})
		);
		const session = new Session();

		await session.start();

		expect([session.mode, session.status, session.email]).toEqual(['dev', 'signed-in', DEV_USER]);
		expect(session.aiModels.map((m) => m.id)).toEqual(['claude-haiku']);
		expect([session.defaultAiModel, session.plansEnforced]).toEqual(['claude-haiku', true]);
	});

	it('fails to start when the client config is unavailable', async () => {
		vi.stubGlobal('fetch', async () => new Response('', { status: 500 }));

		await expect(new Session().start()).rejects.toThrow('client config: 500');
	});

	it('needs start before sign-in actions', () => {
		expect(() => new Session().provider).toThrow('Session.start()');
	});

	it('uses the dev provider when firebase is not configured', async () => {
		const provider = await providerFor({
			auth_mode: 'dev',
			firebase: null,
			ai_models: [],
			default_ai_model: null,
			plans_enforced: false
		});

		expect(await provider.headers()).toEqual({ 'X-Dev-User': DEV_USER });
	});
});

describe('pendingEmail', () => {
	it('survives storage that throws', () => {
		const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
			throw new Error('blocked');
		});
		const set = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
			throw new Error('blocked');
		});

		expect(pendingEmail.get()).toBeNull();
		expect(() => pendingEmail.set('a@example.com')).not.toThrow();
		spy.mockRestore();
		set.mockRestore();
	});
});
