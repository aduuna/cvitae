import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit({
			// SPA: the api serves build/ and falls back to index.html for client-side routes.
			adapter: adapter({ fallback: 'index.html' })
		}),
		svelteTesting()
	],
	server: {
		proxy: { '/api': 'http://localhost:8000' }
	},
	test: {
		environment: 'jsdom',
		include: ['tests/**/*.test.ts'],
		setupFiles: ['tests/setup.ts']
	}
});
