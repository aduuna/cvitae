/**
 * How the connect page hands the browser extension its token. Both sides post messages to the
 * page's own window, on the app's origin: the extension runs a content script on the connect page
 * only, and checks the origin and sender of every message. apps/extension imports this module.
 */

/** Where the extension sends the user to connect it. */
export const CONNECT_PATH = '/app/extension';

/** The page's messages. */
export type PageMessage =
	| { source: 'cvitae-app'; type: 'ping' }
	| { source: 'cvitae-app'; type: 'token'; token: string; email: string };

/** The extension's answers. */
export type ExtensionMessage =
	| { source: 'cvitae-extension'; type: 'ready'; connectedAs: string | null }
	| { source: 'cvitae-extension'; type: 'connected'; email: string }
	| { source: 'cvitae-extension'; type: 'failed'; message: string };

function hasSource(data: unknown, source: string): data is { type: unknown } {
	return (
		typeof data === 'object' && data !== null && (data as { source?: unknown }).source === source
	);
}

export function isPageMessage(data: unknown): data is PageMessage {
	if (!hasSource(data, 'cvitae-app')) return false;
	const message = data as Partial<Record<string, unknown>>;
	return (
		message.type === 'ping' ||
		(message.type === 'token' &&
			typeof message.token === 'string' &&
			typeof message.email === 'string')
	);
}

export function isExtensionMessage(data: unknown): data is ExtensionMessage {
	if (!hasSource(data, 'cvitae-extension')) return false;
	const message = data as Partial<Record<string, unknown>>;
	switch (message.type) {
		case 'ready':
			return message.connectedAs === null || typeof message.connectedAs === 'string';
		case 'connected':
			return typeof message.email === 'string';
		case 'failed':
			return typeof message.message === 'string';
		default:
			return false;
	}
}
