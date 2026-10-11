// @vitest-environment node
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { findRawColors, scanDirectories } from './token-scan';

const root = fileURLToPath(new URL('..', import.meta.url));

describe('findRawColors', () => {
	it.each([
		['palette utility', '<div class="bg-gray-500"></div>'],
		['palette utility with variant', '<div class="hover:border-red-700"></div>'],
		['yellow palette', "const c = 'bg-yellow-200';"],
		['black utility', '<p class="text-black"></p>'],
		['white utility with opacity', '<p class="bg-white/50"></p>'],
		['variant map entry', "const variants = { primary: 'bg-black text-white' };"],
		['hex in inline style', '<p style="color: #fff"></p>'],
		['hex in style block', '<style> p { color: #0a0a0a; } </style>'],
		['arbitrary hex value', '<p class="bg-[#ff0000]"></p>'],
		['rgb function', '<p style="background: rgb(0 0 0 / 0.5)"></p>'],
		['oklch function', '<style> p { color: oklch(0.5 0 0); } </style>'],
		['named color in CSS', '<style> p { color: white; } </style>'],
		['raw palette variable', '<style> p { color: var(--color-gray-500); } </style>']
	])('flags a %s', (_name, source) => {
		expect(findRawColors(source)).not.toEqual([]);
	});

	it.each([
		['semantic utilities', '<div class="border-line bg-surface text-fg"></div>'],
		['semantic token with opacity', '<div class="bg-accent/85 text-accent-fg"></div>'],
		['placeholder and danger tokens', '<span class="bg-placeholder text-danger"></span>'],
		['svelte block', '{#each items as item (item.id)}{/each}'],
		['fragment link', '<a href="#main">Skip</a>'],
		['whitespace utility', '<span class="whitespace-nowrap"></span>'],
		['white-space property', '<style> p { white-space: nowrap; } </style>'],
		['semantic variable', '<style> p { color: var(--color-fg-muted); } </style>']
	])('allows %s', (_name, source) => {
		expect(findRawColors(source)).toEqual([]);
	});

	it('reports file, line and match', () => {
		expect(findRawColors('<p>\n<b class="text-gray-900"></b>', 'X.svelte')).toEqual([
			{ file: 'X.svelte', line: 2, match: 'gray-900', rule: 'raw palette name' }
		]);
	});
});

describe('design tokens', () => {
	it('components and routes use semantic color tokens only', () => {
		const violations = scanDirectories([`${root}src/lib/components`, `${root}src/routes`]);
		const report = violations.map(
			(v) => `${v.file.replace(root, '')}:${v.line} ${v.match} (${v.rule})`
		);
		expect(report).toEqual([]);
	});

	it('app.css defines every semantic color token', () => {
		for (const name of SEMANTIC) {
			expect(css).toMatch(new RegExp(`--color-${name}: var\\(--color-[a-z]+(-\\d+)?\\);`));
		}
		expect(css).toContain('--color-*: initial;');
	});

	it('the dark theme redefines every theme-dependent token from the raw scale', () => {
		const dark = themeColors('dark');
		const expected = SEMANTIC.filter((name) => !THEME_INDEPENDENT.includes(name));
		expect(Object.keys(darkBlock()).sort()).toEqual(expected.sort());
		for (const name of SEMANTIC) expect(dark[name]).toMatch(/^#[0-9a-f]{6}$/);
	});

	describe.each(['light', 'dark'] as const)('%s theme contrast (WCAG 2.2 AA)', (mode) => {
		const colors = themeColors(mode);
		it.each([
			['fg', 'surface', 4.5],
			['fg', 'canvas', 4.5],
			['fg', 'muted', 4.5],
			['fg-muted', 'surface', 4.5],
			['danger', 'surface', 4.5],
			['accent-fg', 'accent', 4.5],
			['placeholder-fg', 'placeholder', 4.5],
			['accent', 'surface', 3]
		])('%s on %s is at least %s:1', (fg, bg, minimum) => {
			expect(contrast(colors[fg], colors[bg])).toBeGreaterThanOrEqual(minimum);
		});
	});
});

const css = readFileSync(`${root}src/app.css`, 'utf8');

const SEMANTIC = [
	'canvas',
	'surface',
	'subtle',
	'muted',
	'line',
	'line-strong',
	'fg',
	'fg-muted',
	'fg-faint',
	'accent',
	'accent-fg',
	'danger',
	'placeholder',
	'placeholder-fg',
	'paper',
	'scrim'
];

/** The CV keeps its print colors in both themes. */
const THEME_INDEPENDENT = ['placeholder', 'placeholder-fg', 'paper'];

const DARK_SELECTOR = ":root[data-theme='dark']";

/** `--color-name: var(--color-raw);` declarations in a block of CSS, as { name: raw }. */
function aliases(block: string): Record<string, string> {
	const pairs = block.matchAll(/--color-([a-z-]+): var\(--color-([a-z0-9-]+)\);/g);
	return Object.fromEntries([...pairs].map(([, name = '', raw = '']) => [name, raw]));
}

/** The light theme: the declarations in `@theme`, before the dark block. */
function lightBlock(): Record<string, string> {
	return aliases(css.split(DARK_SELECTOR)[0] ?? '');
}

function darkBlock(): Record<string, string> {
	const block = /:root\[data-theme='dark'\] \{([^}]*)\}/.exec(css);
	if (!block?.[1]) throw new Error(`app.css has no ${DARK_SELECTOR} block`);
	return aliases(block[1]);
}

/** Every semantic token resolved to its hex value in one theme. */
function themeColors(mode: 'light' | 'dark'): Record<string, string> {
	const raw = Object.fromEntries(
		[...css.matchAll(/--color-([a-z0-9-]+): (#[0-9a-f]{6});/g)].map(([, name, hex]) => [name, hex])
	);
	const semantic = { ...lightBlock(), ...(mode === 'dark' ? darkBlock() : {}) };
	return Object.fromEntries(Object.entries(semantic).map(([name, alias]) => [name, raw[alias]]));
}

function luminance(hex: string | undefined): number {
	if (!hex) throw new Error('unknown color token');
	const [r = 0, g = 0, b = 0] = [1, 3, 5].map((i) => {
		const c = parseInt(hex.slice(i, i + 2), 16) / 255;
		return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
	});
	return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string | undefined, b: string | undefined): number {
	const [light = 0, dark = 0] = [luminance(a), luminance(b)].sort((x, y) => y - x);
	return (light + 0.05) / (dark + 0.05);
}
