/**
 * Where to install the browser extension. Null until it is published there; the Extension page
 * then says it is not in that store yet. Set each address once its listing is live.
 */
export const EXTENSION_STORES: readonly { browser: string; url: string | null }[] = [
	{ browser: 'Chrome', url: null },
	{ browser: 'Firefox', url: null }
];
