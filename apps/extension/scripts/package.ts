/**
 * Builds the extension for the stores and zips it into releases/:
 *
 * - cvitae-chrome-<version>.zip, for the Chrome Web Store;
 * - cvitae-firefox-<version>.zip, for addons.mozilla.org;
 * - cvitae-source-<version>.zip, the source Mozilla asks for with bundled code (apps/extension
 *   and apps/web, which it builds on, as they are now).
 *
 * Usage: bun run package
 * VITE_APP_URL is the deployed web app (default https://cvitae.aduuna.dev). A local address is
 * refused: a store build must talk to a deployed app. Bump "version" in package.json first.
 */
import { spawnSync, type SpawnSyncOptions } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir, readFile, rm } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const OUT = 'dist-release';
const RELEASES = 'releases';
const JUNK = ['*.DS_Store', '*/._*', '._*', '*Thumbs.db', '*desktop.ini', '__MACOSX/*'];

function run(command: string, args: string[], options: SpawnSyncOptions = {}): string {
	const result = spawnSync(command, args, { cwd: root, encoding: 'utf8', ...options });
	if (result.status !== 0) {
		throw new Error(`${command} ${args.join(' ')} failed:\n${result.stderr ?? ''}`);
	}
	return String(result.stdout ?? '');
}

const appUrl = (process.env.VITE_APP_URL || 'https://cvitae.aduuna.dev').replace(/\/+$/, '');
const { hostname, protocol } = new URL(appUrl);
if (protocol !== 'https:' || /^(localhost|127\.|0\.0\.0\.0|\[::1\])/.test(hostname)) {
	throw new Error(`A store build needs a deployed https address, not ${appUrl}. Set VITE_APP_URL.`);
}
const { version } = JSON.parse(await readFile(`${root}package.json`, 'utf8')) as {
	version: string;
};

run(process.execPath, ['--disable-warning=ExperimentalWarning', 'scripts/build.ts'], {
	env: { ...process.env, VITE_APP_URL: appUrl, EXTENSION_OUT_DIR: OUT },
	stdio: 'inherit'
});

await mkdir(`${root}${RELEASES}`, { recursive: true });
for (const target of ['chrome', 'firefox']) {
	const zip = `${root}${RELEASES}/cvitae-${target}-${version}.zip`;
	await rm(zip, { force: true });
	// From inside the build, so manifest.json is at the root of the zip as the stores require.
	// Without the files operating systems leave in folders (public/ is copied as it is), which
	// add-on review flags.
	run('zip', ['-r', '-q', '-X', zip, '.', '-x', ...JUNK], { cwd: `${root}${OUT}/${target}` });
	console.log(`${RELEASES}/cvitae-${target}-${version}.zip`);
}

// The source as built: the files git knows or would add (not ignored ones like node_modules).
const source = `${RELEASES}/cvitae-source-${version}.zip`;
const repo = run('git', ['rev-parse', '--show-toplevel']).trim();
const listed = run(
	'git',
	['ls-files', '--cached', '--others', '--exclude-standard', '--', 'apps/extension', 'apps/web'],
	{ cwd: repo }
);
const files = listed.split('\n').filter((file) => file && existsSync(`${repo}/${file}`));
await rm(`${root}${source}`, { force: true });
run('zip', ['-q', '-X', `${root}${source}`, '-@'], { cwd: repo, input: files.join('\n') });
console.log(source);
