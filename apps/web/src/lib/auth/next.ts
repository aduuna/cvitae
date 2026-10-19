/**
 * Coming back to the page a signed-out user was sent away from, such as the browser extension's
 * connect page. The page travels in `?next=`; only paths inside the app are followed, so a link
 * cannot send anyone elsewhere after they sign in.
 */

const HOME = '/app/documents';

/** The app path in `?next=`, or null when there is none or it leads outside the app. */
export function nextPath(url: URL): string | null {
	const next = url.searchParams.get('next');
	if (!next) return null;
	const target = new URL(next, url.origin);
	const inside = target.origin === url.origin && target.pathname.startsWith('/app/');
	return inside ? target.pathname + target.search : null;
}

/** Where to go once signed in. */
export function afterSignIn(url: URL): string {
	return nextPath(url) ?? HOME;
}

/**
 * Where a signed-out visitor to an app page goes: sign-in, remembering the page, when it is one
 * worth coming back to (the extension's connect page, a saved job in Tailor); else the home page.
 */
export function signInPath(url: Pick<URL, 'pathname' | 'search'>): string {
	const here = url.pathname + url.search;
	return url.pathname.startsWith('/app/') && !url.pathname.startsWith(HOME)
		? `/login?next=${encodeURIComponent(here)}`
		: '/';
}

/** Add `?next=` to an address, for links that come back to this page (the email sign-in link). */
export function withNext(address: string, next: string | null): string {
	return next ? `${address}?next=${encodeURIComponent(next)}` : address;
}
