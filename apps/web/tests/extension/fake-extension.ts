import {
	isPageMessage,
	type ExtensionMessage,
	type PageMessage
} from '../../src/lib/extension/protocol.ts';

/** As a browser delivers a content script's window.postMessage. jsdom's own leaves the origin
 * empty and the source null. */
export function postAsExtension(message: ExtensionMessage): void {
	window.dispatchEvent(
		new MessageEvent('message', { data: message, origin: window.location.origin, source: window })
	);
}

/**
 * Plays the extension's content script on the connect page: answers the page's messages on the
 * same window, as the real one does. `reply` decides each answer; null stays silent.
 */
export function fakeExtension(reply: (message: PageMessage) => ExtensionMessage | null) {
	const received: PageMessage[] = [];
	const listen = (event: MessageEvent) => {
		if (!isPageMessage(event.data)) return;
		received.push(event.data);
		const answer = reply(event.data);
		if (answer) setTimeout(() => postAsExtension(answer), 0);
	};
	window.addEventListener('message', listen);
	return { received, remove: () => window.removeEventListener('message', listen) };
}

export const ready = (connectedAs: string | null = null): ExtensionMessage => ({
	source: 'cvitae-extension',
	type: 'ready',
	connectedAs
});
