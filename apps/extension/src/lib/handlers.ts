import { errorMessage } from '@web/api/client.ts';
import { APP_ORIGIN } from '../config.ts';
import {
	connectApi,
	isRevoked,
	loadApplication,
	loadSession,
	type Api,
	type ExtensionSession
} from './api.ts';
import type { Message, Messages } from './messages.ts';
import { forgetConnection, loadSettings, saveSettings } from './settings.ts';
import { sourceName, suggestSource } from './sources.ts';

const SESSION_TTL_MS = 60_000;

export interface Deps {
	api: (token: string) => Api;
	now: () => number;
}

const defaults: Deps = { api: (token) => connectApi(token), now: () => Date.now() };

function fromApp(url: string | undefined): boolean {
	try {
		return url !== undefined && new URL(url).origin === APP_ORIGIN;
	} catch {
		return false;
	}
}

/**
 * The background script's answers to content scripts. It holds the token and makes the api
 * calls: a content script runs inside a web page and never sees the token.
 */
export function createHandlers(deps: Deps = defaults) {
	let cached: { token: string; at: number; session: ExtensionSession } | null = null;

	async function session(token: string): Promise<ExtensionSession> {
		if (cached && cached.token === token && deps.now() - cached.at < SESSION_TTL_MS) {
			return cached.session;
		}
		const fresh = await loadSession(deps.api(token));
		cached = { token, at: deps.now(), session: fresh };
		return fresh;
	}

	async function connected<T>(work: (token: string) => Promise<T>, otherwise: T): Promise<T> {
		const { token } = await loadSettings();
		if (!token) return otherwise;
		try {
			return await work(token);
		} catch (error) {
			if (isRevoked(error)) {
				cached = null;
				await forgetConnection();
				return otherwise;
			}
			throw error;
		}
	}

	async function connect({
		token
	}: Messages['connect']['request']): Promise<Messages['connect']['reply']> {
		try {
			const checked = await loadSession(deps.api(token));
			cached = null;
			await saveSettings({ token, email: checked.email, source: null });
			return { ok: true, email: checked.email };
		} catch (error) {
			return {
				ok: false,
				message: isRevoked(error)
					? 'The server did not accept this connection. Reload the page and try again.'
					: errorMessage(error)
			};
		}
	}

	async function offer(urls: (string | undefined)[]): Promise<Messages['offer']['reply']> {
		const settings = await loadSettings();
		if (!settings.offer) return { show: false };
		return connected<Messages['offer']['reply']>(
			async (token) => {
				const current = await session(token);
				const suggestion = suggestSource(current, urls, settings.source);
				return suggestion
					? { show: true, source: sourceName(current, suggestion.source) }
					: { show: false };
			},
			{ show: false }
		);
	}

	async function application(
		urls: (string | undefined)[]
	): Promise<Messages['application']['reply']> {
		type Reply = Messages['application']['reply'];
		const settings = await loadSettings();
		const notConnected: Reply = {
			ok: false,
			message: 'Open the extension from the toolbar and connect it to your account.'
		};
		try {
			return await connected<Reply>(async (token) => {
				const current = await session(token);
				const suggestion = suggestSource(current, urls, settings.source);
				if (!suggestion) return { ok: false, message: 'Add a profile in Chameleon vitae first.' };
				return { ok: true, data: await loadApplication(deps.api(token), suggestion.source) };
			}, notConnected);
		} catch (error) {
			return { ok: false, message: errorMessage(error) };
		}
	}

	/** Answer one message. `urls` are the page's: the sender's tab and frame. */
	async function handle(message: Message, sender: { url?: string; tabUrl?: string }) {
		const urls = [sender.tabUrl, sender.url];
		switch (message.type) {
			case 'connect':
				// Only the connect page on the app's own origin may hand over a token.
				if (!fromApp(sender.url)) return { ok: false, message: 'Connect from Chameleon vitae.' };
				return connect(message);
			case 'connection': {
				if (!fromApp(sender.url)) return { connectedAs: null };
				const { token, email } = await loadSettings();
				return { connectedAs: token ? email : null };
			}
			case 'offer':
				return offer(urls);
			case 'application':
				return application(urls);
		}
	}

	return { handle, forget: () => (cached = null) };
}
