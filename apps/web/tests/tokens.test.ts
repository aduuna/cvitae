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
		const css = readFileSync(`${root}src/app.css`, 'utf8');
		const semantic = [
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
			'placeholder'
		];
		for (const name of semantic) {
			expect(css).toMatch(new RegExp(`--color-${name}: var\\(--color-[a-z]+(-\\d+)?\\);`));
		}
		expect(css).toContain('--color-*: initial;');
	});
});
