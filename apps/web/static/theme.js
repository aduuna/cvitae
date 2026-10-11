// Sets <html data-theme> before first paint so a dark theme never flashes light.
// A blocking file rather than an inline script, so a strict CSP needs no hash for it.
// $lib/theme.svelte.ts owns the choice once the app starts; keep the storage key in sync.
(() => {
	let preference = null;
	try {
		preference = localStorage.getItem('vitae.theme');
	} catch {
		// Storage blocked: follow the system.
	}
	const dark =
		preference === 'dark' ||
		(preference !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches);
	document.documentElement.dataset.theme = dark ? 'dark' : 'light';
})();
