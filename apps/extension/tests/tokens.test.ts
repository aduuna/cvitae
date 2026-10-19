// @vitest-environment node
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { scanDirectories, themeColors } from '../../web/tests/token-scan.ts';
import { TOKENS } from '../src/content/tokens.ts';

const root = join(import.meta.dirname, '..');
const css = readFileSync(join(root, '../web/src/app.css'), 'utf8');

describe('design tokens', () => {
	it.each(['light', 'dark'] as const)(
		'what the extension draws in job sites uses the %s theme tokens',
		(mode) => {
			const colors = themeColors(css, mode);
			for (const [name, value] of Object.entries(TOKENS[mode])) {
				expect([name, value]).toEqual([name, colors[name]]);
			}
		}
	);

	it('the extension names no raw colors outside its token copy', () => {
		const tokenFile = join(root, 'src/content/tokens.ts');
		const report = scanDirectories([join(root, 'src')])
			.filter((v) => v.file !== tokenFile)
			.map((v) => `${v.file.replace(root, '')}:${v.line} ${v.match} (${v.rule})`);

		expect(report).toEqual([]);
	});
});
