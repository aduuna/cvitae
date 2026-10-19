import type { ApplicationData } from '../content/types.ts';

/** Messages from content scripts to the background script, and the answer to each. */
export interface Messages {
	/** From the connect page: keep this token if the api accepts it. */
	connect: {
		request: { token: string; email: string };
		reply: { ok: true; email: string } | { ok: false; message: string };
	};
	/** From the connect page: which account this browser is connected to. */
	connection: { request: Record<never, never>; reply: { connectedAs: string | null } };
	/** From a job site: whether to offer filling, and from what. */
	offer: {
		request: { url: string };
		reply: { show: false } | { show: true; source: string };
	};
	/** From a job site, once the user chose Fill fields: the data to fill with. */
	application: {
		request: { url: string };
		reply: { ok: true; data: ApplicationData } | { ok: false; message: string };
	};
}

export type MessageType = keyof Messages;
export type Message = { [T in MessageType]: { type: T } & Messages[T]['request'] }[MessageType];

export function send<T extends MessageType>(
	type: T,
	request: Messages[T]['request']
): Promise<Messages[T]['reply']> {
	return chrome.runtime.sendMessage({ type, ...request });
}

const TYPES: readonly MessageType[] = ['connect', 'connection', 'offer', 'application'];

export function isMessage(value: unknown): value is Message {
	return TYPES.includes((value as { type?: MessageType } | null)?.type as MessageType);
}
