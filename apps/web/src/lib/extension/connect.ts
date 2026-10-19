import { isExtensionMessage, type ExtensionMessage, type PageMessage } from './protocol.ts';

/** How long to wait for the extension's content script, which loads with the page. */
export const FIND_TIMEOUT_MS = 1500;
/** The extension checks the token with the api before it answers. */
export const HANDOVER_TIMEOUT_MS = 8000;

/** A name for the connection, for the list in Settings: "Chrome on macOS". */
export function browserLabel(userAgent: string): string {
	const browser = /Edg\//.test(userAgent)
		? 'Edge'
		: /OPR\/|Opera/.test(userAgent)
			? 'Opera'
			: /Firefox\//.test(userAgent)
				? 'Firefox'
				: /Chrome\/|Chromium\//.test(userAgent)
					? 'Chrome'
					: /Safari\//.test(userAgent)
						? 'Safari'
						: 'Browser';
	const os = /CrOS/.test(userAgent)
		? 'ChromeOS'
		: /Android/.test(userAgent)
			? 'Android'
			: /iPhone|iPad/.test(userAgent)
				? 'iOS'
				: /Windows/.test(userAgent)
					? 'Windows'
					: /Mac OS X|Macintosh/.test(userAgent)
						? 'macOS'
						: /Linux/.test(userAgent)
							? 'Linux'
							: null;
	return os ? `${browser} on ${os}` : browser;
}

/** Post to the extension's content script and wait for the first answer `accept` takes. */
function exchange<T>(
	win: Window,
	message: PageMessage,
	timeoutMs: number,
	accept: (answer: ExtensionMessage) => T | undefined
): Promise<T | null> {
	return new Promise((resolve) => {
		const done = (value: T | null) => {
			clearTimeout(timer);
			win.removeEventListener('message', listen);
			resolve(value);
		};
		const listen = (event: MessageEvent) => {
			if (event.source !== win || event.origin !== win.location.origin) return;
			if (!isExtensionMessage(event.data)) return;
			const value = accept(event.data);
			if (value !== undefined) done(value);
		};
		const timer = setTimeout(() => done(null), timeoutMs);
		win.addEventListener('message', listen);
		win.postMessage(message, win.location.origin);
	});
}

export interface Found {
	/** The account this browser is connected to already, if any. */
	connectedAs: string | null;
}

/** Whether the extension is installed and running on this page; null when it does not answer. */
export function findExtension(win: Window = window, timeoutMs = FIND_TIMEOUT_MS) {
	return exchange<Found>(win, { source: 'cvitae-app', type: 'ping' }, timeoutMs, (answer) =>
		answer.type === 'ready' ? { connectedAs: answer.connectedAs } : undefined
	);
}

export type Handover = { ok: true; email: string } | { ok: false; message: string };

const NO_ANSWER =
	'The extension did not answer. Check that it is installed and turned on, then reload this page.';

/** Give the extension its token. It checks the token before it says it is connected. */
export async function handOver(
	token: string,
	email: string,
	win: Window = window,
	timeoutMs = HANDOVER_TIMEOUT_MS
): Promise<Handover> {
	const answer = await exchange<Handover>(
		win,
		{ source: 'cvitae-app', type: 'token', token, email },
		timeoutMs,
		(reply) => {
			if (reply.type === 'connected') return { ok: true, email: reply.email };
			if (reply.type === 'failed') return { ok: false, message: reply.message };
			return undefined;
		}
	);
	return answer ?? { ok: false, message: NO_ANSWER };
}
