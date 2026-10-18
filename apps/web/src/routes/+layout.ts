import { browser } from '$app/env';
import { session } from '#lib/auth/session.svelte.ts';

// SPA: everything renders in the browser; the api serves the static build.
export const ssr = false;
export const prerender = false;

// Every page needs to know whether someone is signed in before it renders. The landing page is
// prerendered at build time, when there is no api to ask; it asks again once it runs in the browser.
export async function load() {
	if (browser) await session.start();
}
