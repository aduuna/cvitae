/**
 * What the extension keeps in the browser: the connection's token, the account's email, the
 * profile or CV last chosen, and whether to offer filling on job sites. Never profile or CV
 * content: that is fetched when a form is filled and dropped afterwards.
 */

export interface SourceRef {
	kind: 'profile' | 'document';
	id: string;
}

export interface Settings {
	token: string | null;
	email: string | null;
	source: SourceRef | null;
	/** Offer to fill when a job site shows an application form. */
	offer: boolean;
}

export const DEFAULTS: Settings = { token: null, email: null, source: null, offer: true };

export async function loadSettings(): Promise<Settings> {
	const keys = Object.keys(DEFAULTS) as (keyof Settings)[];
	const stored = (await chrome.storage.local.get(keys)) as Partial<Settings>;
	return { ...DEFAULTS, ...stored };
}

export async function saveSettings(changes: Partial<Settings>): Promise<void> {
	await chrome.storage.local.set(changes);
}

/** Forget the connection, as after disconnecting or when the api no longer accepts the token. */
export async function forgetConnection(): Promise<void> {
	await chrome.storage.local.remove(['token', 'email', 'source']);
}

export function onSettingsChanged(callback: () => void): () => void {
	const listener = (_: unknown, area: string) => {
		if (area === 'local') callback();
	};
	chrome.storage.onChanged.addListener(listener);
	return () => chrome.storage.onChanged.removeListener(listener);
}
