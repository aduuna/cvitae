import { isPageMessage, type ExtensionMessage } from '@web/extension/protocol.ts';
import { APP_ORIGIN } from './config.ts';
import { send } from './lib/messages.ts';

/**
 * Runs on the app's connect page only. Answers the page's ping, and passes the token it hands
 * over to the background script, which checks it with the api before keeping it.
 */
function start(win: Window): void {
	const post = (message: ExtensionMessage) => win.postMessage(message, APP_ORIGIN);
	const announce = async () => {
		const { connectedAs } = await send('connection', {});
		post({ source: 'cvitae-extension', type: 'ready', connectedAs });
	};
	win.addEventListener('message', (event) => {
		if (event.source !== win || event.origin !== APP_ORIGIN || !isPageMessage(event.data)) return;
		const message = event.data;
		if (message.type === 'ping') {
			void announce();
			return;
		}
		void send('connect', { token: message.token, email: message.email }).then((reply) =>
			post(
				reply.ok
					? { source: 'cvitae-extension', type: 'connected', email: reply.email }
					: { source: 'cvitae-extension', type: 'failed', message: reply.message }
			)
		);
	});
	// The page may have pinged before this script loaded.
	void announce();
}

// The manifest's pattern cannot name a port; the origin check here can.
if (location.origin === APP_ORIGIN) start(window);
