import { session } from '#lib/auth/session.svelte.ts';

// SPA: everything renders in the browser; the api serves the static build.
export const ssr = false;
export const prerender = false;

// Every page needs to know whether someone is signed in before it renders.
export async function load() {
	await session.start();
}
