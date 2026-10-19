import { spawnSync } from 'node:child_process';
import { join } from 'node:path';
import { E2E_APP_URL, E2E_OUT_DIR } from './server.ts';

/** Build the Chrome extension pointed at the mock api. */
export default function globalSetup(): void {
	const result = spawnSync(
		process.execPath,
		['--disable-warning=ExperimentalWarning', 'scripts/build.ts', 'chrome'],
		{
			cwd: join(import.meta.dirname, '../..'),
			env: { ...process.env, VITE_APP_URL: E2E_APP_URL, EXTENSION_OUT_DIR: E2E_OUT_DIR },
			stdio: 'inherit'
		}
	);
	if (result.status !== 0) throw new Error('The extension did not build.');
}
