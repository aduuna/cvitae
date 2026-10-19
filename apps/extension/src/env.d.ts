/// <reference types="vite/client" />

interface ImportMetaEnv {
	/** The web app the build talks to (scripts/build.ts). */
	readonly VITE_APP_URL?: string;
	/** The browser a build is for; unset in tests, which take Chrome's paths. */
	readonly VITE_TARGET?: 'chrome' | 'firefox';
}
