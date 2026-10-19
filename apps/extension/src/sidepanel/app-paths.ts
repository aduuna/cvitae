/**
 * Stands in for SvelteKit's $app/paths, which the web app's Logo.svelte imports. The panel's files
 * (the logo among them) sit at the extension's root.
 */
export function asset(file: string): string {
	return `/${file.replace(/^\/+/, '')}`;
}
