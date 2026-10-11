import '@testing-library/jest-dom/vitest';
import { matchMediaStub, setColorScheme, setViewportWidth } from './media';

// jsdom has no layout engine and no matchMedia; svelte/reactivity's MediaQuery needs it.
// Node-environment tests (the token scan) have no window at all.
if (typeof window !== 'undefined') {
	Object.defineProperty(window, 'matchMedia', { writable: true, value: matchMediaStub });
	setViewportWidth(1280);
	setColorScheme('light');
}
