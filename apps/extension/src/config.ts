/**
 * The web app the extension belongs to; its api is on the same origin (in development, Vite
 * proxies /api to the api). Set VITE_APP_URL when building for a deployed environment.
 */
export const APP_URL: string = (import.meta.env.VITE_APP_URL || 'http://localhost:5173').replace(
	/\/+$/,
	''
);

export const APP_ORIGIN: string = new URL(APP_URL).origin;
