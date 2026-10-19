import { readdirSync, readFileSync, statSync } from 'node:fs';
import { extname, join } from 'node:path';

export interface Violation {
	file: string;
	line: number;
	match: string;
	rule: string;
}

/**
 * Raw colors that must not appear in components or routes (docs/DESIGN.md, Enforcement).
 * Only src/app.css may name the raw palette; everything else uses semantic tokens.
 */
const RULES: { rule: string; pattern: RegExp }[] = [
	{ rule: 'raw palette name', pattern: /\b(?:gray|red|yellow)-\d{2,3}\b/g },
	{ rule: 'raw palette name', pattern: /\b(?:[a-z]+-)+(?:black|white)\b/g },
	{ rule: 'named color in CSS', pattern: /:\s*(?:black|white)\b/g },
	{
		rule: 'hex color',
		pattern: /(?<![\w&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![\w-])/g
	},
	{ rule: 'color function', pattern: /\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch)\(/g }
];

const SCANNED_EXTENSIONS = new Set(['.svelte', '.ts', '.js', '.css']);

export function findRawColors(source: string, file = '<inline>'): Violation[] {
	const violations: Violation[] = [];
	source.split('\n').forEach((text, index) => {
		for (const { rule, pattern } of RULES) {
			for (const match of text.matchAll(pattern)) {
				violations.push({ file, line: index + 1, match: match[0], rule });
			}
		}
	});
	return violations;
}

function listFiles(dir: string): string[] {
	return readdirSync(dir).flatMap((name) => {
		const path = join(dir, name);
		if (statSync(path).isDirectory()) return listFiles(path);
		return SCANNED_EXTENSIONS.has(extname(path)) ? [path] : [];
	});
}

export function scanDirectories(dirs: string[]): Violation[] {
	return dirs.flatMap(listFiles).flatMap((file) => findRawColors(readFileSync(file, 'utf8'), file));
}

const DARK_SELECTOR = ":root[data-theme='dark']";

/** `--color-name: var(--color-raw);` declarations in a block of CSS, as { name: raw }. */
function aliases(block: string): Record<string, string> {
	const pairs = block.matchAll(/--color-([a-z-]+): var\(--color-([a-z0-9-]+)\);/g);
	return Object.fromEntries([...pairs].map(([, name = '', raw = '']) => [name, raw]));
}

/** The dark theme's semantic tokens in app.css, as { name: raw }. */
export function darkAliases(css: string): Record<string, string> {
	const block = /:root\[data-theme='dark'\] \{([^}]*)\}/.exec(css);
	if (!block?.[1]) throw new Error(`app.css has no ${DARK_SELECTOR} block`);
	return aliases(block[1]);
}

/** Every semantic token in app.css resolved to its hex value in one theme. */
export function themeColors(css: string, mode: 'light' | 'dark'): Record<string, string> {
	const raw = Object.fromEntries(
		[...css.matchAll(/--color-([a-z0-9-]+): (#[0-9a-f]{6});/g)].map(([, name, hex]) => [name, hex])
	);
	// The light theme is the declarations in `@theme`, before the dark block.
	const light = aliases(css.split(DARK_SELECTOR)[0] ?? '');
	const semantic = { ...light, ...(mode === 'dark' ? darkAliases(css) : {}) };
	return Object.fromEntries(Object.entries(semantic).map(([name, alias]) => [name, raw[alias]]));
}
