import { fileURLToPath } from 'node:url';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig } from 'vitest/config';

const path = (relative: string) => fileURLToPath(new URL(relative, import.meta.url));

/**
 * The side panel reuses the web app's tokens and UI primitives from apps/web/src/lib (`@web`).
 * Those files import Svelte from the web app's node_modules: dedupe keeps one Svelte runtime.
 */
export const resolve = {
	alias: {
		'@web': path('../web/src/lib'),
		// Logo.svelte asks SvelteKit for asset paths; the panel serves them from its own root.
		'$app/paths': path('./src/sidepanel/app-paths.ts')
	},
	dedupe: ['svelte', '@lucide/svelte']
};

export default defineConfig({
	plugins: [
		tailwindcss(),
		// Templates built element by element, not with innerHTML, which add-on reviews flag.
		svelte({ compilerOptions: { fragments: 'tree' } }),
		svelteTesting()
	],
	resolve,
	build: {
		rollupOptions: { input: { sidepanel: path('./sidepanel.html') } },
		target: 'es2022'
	},
	test: {
		environment: 'jsdom',
		include: ['tests/**/*.test.ts'],
		setupFiles: ['tests/setup.ts']
	}
});
