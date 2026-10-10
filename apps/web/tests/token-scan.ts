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
