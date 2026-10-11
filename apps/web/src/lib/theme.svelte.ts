import { MediaQuery } from 'svelte/reactivity';

export type ThemePreference = 'system' | 'light' | 'dark';
export type ResolvedTheme = 'light' | 'dark';

/** static/theme.js reads the same key before first paint; keep the two in sync. */
export const THEME_STORAGE_KEY = 'vitae.theme';

export const themeOptions: { value: ThemePreference; label: string }[] = [
	{ value: 'system', label: 'System' },
	{ value: 'light', label: 'Light' },
	{ value: 'dark', label: 'Dark' }
];

/** The saved choice; storage can be unavailable (private mode), so failures follow the system. */
function loadPreference(): ThemePreference {
	try {
		const value = localStorage.getItem(THEME_STORAGE_KEY);
		return value === 'light' || value === 'dark' ? value : 'system';
	} catch {
		return 'system';
	}
}

function savePreference(preference: ThemePreference): void {
	try {
		if (preference === 'system') localStorage.removeItem(THEME_STORAGE_KEY);
		else localStorage.setItem(THEME_STORAGE_KEY, preference);
	} catch {
		// Not persisted; the choice still applies for this session.
	}
}

/** The theme choice, per browser. The root layout writes `resolved` to `<html data-theme>`. */
class Theme {
	#preference = $state<ThemePreference>(loadPreference());
	#systemDark = new MediaQuery('prefers-color-scheme: dark', false);

	get preference(): ThemePreference {
		return this.#preference;
	}

	set preference(value: ThemePreference) {
		this.#preference = value;
		savePreference(value);
	}

	/** The theme on screen: the choice, or the device setting under "system". */
	get resolved(): ResolvedTheme {
		if (this.#preference !== 'system') return this.#preference;
		return this.#systemDark.current ? 'dark' : 'light';
	}
}

export const theme = new Theme();
