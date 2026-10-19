import { CONNECT_PATH } from '@web/extension/protocol.ts';
import { APP_URL } from './config.ts';
import { openPanel } from './lib/browser.ts';
import { createHandlers } from './lib/handlers.ts';
import { isMessage } from './lib/messages.ts';
import { onSettingsChanged } from './lib/settings.ts';

const handlers = createHandlers();

// The token lives in local storage. Content scripts never read it (they ask this script), and in
// Chrome they cannot: storage is closed to them. Firefox has no such setting.
chrome.storage.local.setAccessLevel?.({ accessLevel: 'TRUSTED_CONTEXTS' })?.catch(() => {});

// A new install starts with connecting the account.
chrome.runtime.onInstalled.addListener(({ reason }) => {
	if (reason === 'install') void chrome.tabs.create({ url: `${APP_URL}${CONNECT_PATH}` });
});

chrome.action.onClicked.addListener(openPanel);

chrome.runtime.onMessage.addListener((message: unknown, sender, respond) => {
	if (sender.id !== chrome.runtime.id || !isMessage(message)) return false;
	handlers
		.handle(message, { url: sender.url, tabUrl: sender.tab?.url })
		.then(respond, () => respond(null));
	return true;
});

// The side panel may connect or disconnect; drop what was cached for the old token.
onSettingsChanged(() => handlers.forget());
