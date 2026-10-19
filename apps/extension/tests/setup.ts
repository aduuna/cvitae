import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { matchMediaStub, setColorScheme } from '../../web/tests/media.ts';

// Node-environment tests (the token check) have no window.
if (typeof window !== 'undefined') {
	// jsdom has no matchMedia; the web app's theme reads prefers-color-scheme through it.
	Object.defineProperty(window, 'matchMedia', { writable: true, value: matchMediaStub });
	setColorScheme('light');

	afterEach(() => {
		document.head.innerHTML = '';
		document.body.innerHTML = '';
	});
}

afterEach(() => {
	vi.unstubAllGlobals();
});
