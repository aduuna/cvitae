/**
 * Colours for what the extension draws inside job sites: the fill prompt and the mark on filled
 * fields. A site's CSS variables are its own, so these values are copied from the web app's
 * semantic tokens (apps/web/src/app.css); tests/tokens.test.ts fails if the two drift apart.
 */
export const TOKENS = {
	light: {
		surface: '#ffffff',
		fg: '#18181b',
		'fg-muted': '#71717a',
		line: '#e4e4e7',
		accent: '#0a0a0a',
		'accent-fg': '#ffffff',
		placeholder: '#ffe58a'
	},
	dark: {
		surface: '#18181b',
		fg: '#f4f4f5',
		'fg-muted': '#a1a1aa',
		line: '#27272a',
		accent: '#ffffff',
		'accent-fg': '#0a0a0a',
		placeholder: '#ffe58a'
	}
} as const;

export type TokenName = keyof typeof TOKENS.light;

/** CSS custom properties for a shadow root, light by default and dark with the device. */
export function tokenProperties(): string {
	const props = (theme: keyof typeof TOKENS) =>
		Object.entries(TOKENS[theme])
			.map(([name, value]) => `--${name}: ${value};`)
			.join(' ');
	return `:host { ${props('light')} } @media (prefers-color-scheme: dark) { :host { ${props('dark')} } }`;
}

/** --shadow-pop in app.css. */
export const SHADOW_POP = '0 4px 24px rgb(0 0 0 / 0.12)';

/** The mark on a filled field: an accent outline with a placeholder-yellow halo, visible on light
 * and dark sites alike. */
export const FILLED_STYLE = [
	`outline: 2px solid ${TOKENS.light.accent} !important`,
	'outline-offset: 1px !important',
	`box-shadow: 0 0 0 4px ${TOKENS.light.placeholder} !important`
].join('; ');
