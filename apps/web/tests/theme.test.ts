import { flushSync } from 'svelte';
import { render } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Logo from '#lib/components/shell/Logo.svelte';
import { THEME_STORAGE_KEY, theme } from '#lib/theme.svelte.ts';
import RootLayout from '../src/routes/+layout.svelte';
import bootScript from '../static/theme.js?raw';
import { setColorScheme } from './media';
import { text } from './snippet';

vi.mock('$app/paths', () => ({ asset: (path: string) => path }));

/** A fresh theme module, as on page load, reading whatever storage holds now. */
async function freshTheme() {
	vi.resetModules();
	return (await import('#lib/theme.svelte.ts')).theme;
}

function runBootScript() {
	new Function(bootScript)();
	return document.documentElement.dataset.theme;
}

beforeEach(() => {
	localStorage.clear();
	theme.preference = 'system';
	delete document.documentElement.dataset.theme;
});

afterEach(() => {
	vi.restoreAllMocks();
	setColorScheme('light');
});

describe('theme', () => {
	it('follows the device setting under system', () => {
		expect(theme.preference).toBe('system');
		expect(theme.resolved).toBe('light');
		setColorScheme('dark');
		expect(theme.resolved).toBe('dark');
	});

	it('overrides the device setting with an explicit choice', () => {
		setColorScheme('dark');
		theme.preference = 'light';
		expect(theme.resolved).toBe('light');
		setColorScheme('light');
		theme.preference = 'dark';
		expect(theme.resolved).toBe('dark');
	});

	it('saves explicit choices and forgets system', () => {
		theme.preference = 'dark';
		expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
		theme.preference = 'system';
		expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull();
	});

	it('loads the saved choice on start', async () => {
		localStorage.setItem(THEME_STORAGE_KEY, 'dark');
		expect((await freshTheme()).preference).toBe('dark');
	});

	it('treats an unknown saved value as system', async () => {
		localStorage.setItem(THEME_STORAGE_KEY, 'sepia');
		expect((await freshTheme()).preference).toBe('system');
	});

	it('still works when storage is blocked', async () => {
		vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
			throw new DOMException('blocked', 'SecurityError');
		});
		vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
			throw new DOMException('blocked', 'SecurityError');
		});
		const fresh = await freshTheme();
		expect(fresh.preference).toBe('system');
		fresh.preference = 'dark';
		expect(fresh.resolved).toBe('dark');
	});
});

describe('root layout', () => {
	it('keeps <html data-theme> in step with the choice and the device', () => {
		render(RootLayout, { children: text('page') });
		expect(document.documentElement.dataset.theme).toBe('light');

		setColorScheme('dark');
		flushSync();
		expect(document.documentElement.dataset.theme).toBe('dark');

		theme.preference = 'light';
		flushSync();
		expect(document.documentElement.dataset.theme).toBe('light');
	});
});

describe('logo', () => {
	it('inverts the black line art on the dark theme only', () => {
		render(Logo, { label: 'Chameleon vitae' });
		const logo = document.querySelector('img');
		expect(logo).not.toHaveClass('invert');

		theme.preference = 'dark';
		flushSync();
		expect(logo).toHaveClass('invert');
	});
});

describe('static/theme.js', () => {
	it('reads the same storage key as the theme module', () => {
		expect(bootScript).toContain(`'${THEME_STORAGE_KEY}'`);
	});

	it.each([
		[null, 'light', 'light'],
		[null, 'dark', 'dark'],
		['dark', 'light', 'dark'],
		['light', 'dark', 'light']
	] as const)('saved %s on a %s device paints %s', (saved, device, painted) => {
		if (saved) localStorage.setItem(THEME_STORAGE_KEY, saved);
		setColorScheme(device);
		expect(runBootScript()).toBe(painted);
	});

	it('follows the device when storage is blocked', () => {
		vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
			throw new DOMException('blocked', 'SecurityError');
		});
		setColorScheme('dark');
		expect(runBootScript()).toBe('dark');
	});
});
