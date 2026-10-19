/**
 * Builds the extension into dist/<browser> for Chrome and Firefox:
 *
 * - sidepanel.html and its assets (Vite, Svelte, Tailwind);
 * - background.js, content.js and connect.js, each one classic script: content scripts cannot
 *   load modules, and Firefox's background page runs classic scripts;
 * - manifest.json, from src/manifest.ts.
 *
 * Usage: node scripts/build.ts [chrome] [firefox]   (both when none is named)
 * VITE_APP_URL is the web app the build talks to (default http://localhost:5173). Nothing is
 * minified, so store reviewers can read what they approve.
 */
import { copyFile, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { build } from 'vite';
import { manifest, type Target } from '../src/manifest.ts';
import { resolve } from '../vite.config.ts';

const root = fileURLToPath(new URL('..', import.meta.url));
const path = (relative: string) => fileURLToPath(new URL(`../${relative}`, import.meta.url));

const SCRIPTS = {
	background: 'src/background.ts',
	content: 'src/content/index.ts',
	connect: 'src/connect.ts'
} as const;

const named = process.argv
	.slice(2)
	.filter((arg): arg is Target => arg === 'chrome' || arg === 'firefox');
const targets: Target[] = named.length ? named : ['chrome', 'firefox'];
const appUrl = (process.env.VITE_APP_URL || 'http://localhost:5173').replace(/\/+$/, '');
const { version } = JSON.parse(await readFile(path('package.json'), 'utf8')) as { version: string };
const outBase = process.env.EXTENSION_OUT_DIR || 'dist';

for (const target of targets) {
	const outDir = path(`${outBase}/${target}`);
	// Each browser's build holds only its own code paths (src/lib/browser.ts).
	const define = { 'import.meta.env.VITE_TARGET': JSON.stringify(target) };
	await build({
		root,
		configFile: path('vite.config.ts'),
		logLevel: 'warn',
		define,
		build: { outDir, emptyOutDir: true, minify: false }
	});
	// The web app's logo, which the panel shows through the web app's Logo.svelte.
	await copyFile(path('../web/static/logo.svg'), `${outDir}/logo.svg`);
	for (const [name, entry] of Object.entries(SCRIPTS)) {
		await build({
			root,
			configFile: false,
			logLevel: 'warn',
			resolve,
			define,
			publicDir: false,
			build: {
				outDir,
				emptyOutDir: false,
				minify: false,
				target: 'es2022',
				lib: {
					entry: path(entry),
					formats: ['iife'],
					name: `cvitae_${name}`,
					fileName: () => `${name}.js`
				}
			}
		});
	}
	await writeFile(
		`${outDir}/manifest.json`,
		`${JSON.stringify(manifest(target, appUrl, version), null, '\t')}\n`
	);
	console.log(`Built ${target} for ${appUrl} in ${outBase}/${target}`);
}
