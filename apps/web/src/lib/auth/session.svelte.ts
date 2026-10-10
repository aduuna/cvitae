import { api, setAuthHeaders, unwrap, type Schemas } from '#lib/api/client.ts';
import { devProvider, firebaseProvider, type AuthProvider } from './provider.ts';

export type Me = Schemas['Me'];
export type ClientConfig = Schemas['ClientConfig'];

const EMAIL_KEY = 'cvitae.signInEmail';

/** The email an email link was sent to, so the link can be completed in this browser. */
export const pendingEmail = {
	get(): string | null {
		try {
			return localStorage.getItem(EMAIL_KEY);
		} catch {
			return null;
		}
	},
	set(email: string | null): void {
		try {
			if (email) localStorage.setItem(EMAIL_KEY, email);
			else localStorage.removeItem(EMAIL_KEY);
		} catch {
			// Without storage the user types the email again when they open the link.
		}
	}
};

async function loadClientConfig(): Promise<ClientConfig> {
	const response = await fetch('/api/v1/client-config');
	if (!response.ok) throw new Error(`client config: ${response.status}`);
	return (await response.json()) as ClientConfig;
}

export async function providerFor(config: ClientConfig): Promise<AuthProvider> {
	if (config.auth_mode === 'firebase' && config.firebase) return firebaseProvider(config.firebase);
	return devProvider();
}

/** Who is signed in, and the actions that change it. */
export class Session {
	status = $state<'loading' | 'signed-out' | 'signed-in'>('loading');
	email = $state<string | null>(null);
	mode = $state<ClientConfig['auth_mode'] | null>(null);
	/** The AI models the server offers, free first. */
	aiModels = $state<ClientConfig['ai_models']>([]);
	defaultAiModel = $state<ClientConfig['default_ai_model']>(null);
	/** Pro models need the Pro plan (switched on with billing). */
	plansEnforced = $state(false);
	me = $state<Me | null>(null);

	#provider: AuthProvider | null = null;
	#starting: Promise<void> | null = null;
	#loadingMe: Promise<Me> | null = null;
	readonly #config: () => Promise<ClientConfig>;
	readonly #makeProvider: (config: ClientConfig) => Promise<AuthProvider>;

	constructor(
		config: () => Promise<ClientConfig> = loadClientConfig,
		makeProvider: (config: ClientConfig) => Promise<AuthProvider> = providerFor
	) {
		this.#config = config;
		this.#makeProvider = makeProvider;
	}

	/** Resolves once the first sign-in state is known. Safe to call more than once. */
	start(): Promise<void> {
		this.#starting ??= (async () => {
			const config = await this.#config();
			const provider = await this.#makeProvider(config);
			this.#provider = provider;
			this.mode = config.auth_mode;
			this.aiModels = config.ai_models;
			this.defaultAiModel = config.default_ai_model;
			this.plansEnforced = config.plans_enforced;
			setAuthHeaders(() => provider.headers());
			await new Promise<void>((resolve) => {
				provider.watch((email) => {
					if (email !== this.email) {
						this.me = null;
						this.#loadingMe = null;
					}
					this.email = email;
					this.status = email ? 'signed-in' : 'signed-out';
					resolve();
				});
			});
		})().catch((error: unknown) => {
			this.#starting = null;
			throw error;
		});
		return this.#starting;
	}

	get provider(): AuthProvider {
		if (!this.#provider) throw new Error('Session.start() has not finished');
		return this.#provider;
	}

	signInWithGoogle(): Promise<void> {
		return this.provider.signInWithGoogle();
	}

	async sendEmailLink(email: string, continueUrl: string): Promise<void> {
		await this.provider.sendEmailLink(email, continueUrl);
		pendingEmail.set(email);
	}

	isEmailLink(url: string): boolean {
		return this.provider.isEmailLink(url);
	}

	async completeEmailLink(email: string, url: string): Promise<void> {
		await this.provider.completeEmailLink(email, url);
		pendingEmail.set(null);
	}

	signOut(): Promise<void> {
		return this.provider.signOut();
	}

	/** The signed-in user's record, loaded once per sign-in. */
	loadMe(): Promise<Me> {
		this.#loadingMe ??= unwrap(api.GET('/api/v1/me')).then(
			(me) => (this.me = me),
			(error: unknown) => {
				this.#loadingMe = null;
				throw error;
			}
		);
		return this.#loadingMe;
	}

	async updateMe(changes: Schemas['MeUpdate']): Promise<Me> {
		const me = await unwrap(api.PATCH('/api/v1/me', { body: changes }));
		this.me = me;
		this.#loadingMe = Promise.resolve(me);
		return me;
	}
}

export const session = new Session();
