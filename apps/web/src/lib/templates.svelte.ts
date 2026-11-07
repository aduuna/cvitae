import { api, unwrap } from '#lib/api/client.ts';
import type { TemplateMeta } from '#lib/cv/types.ts';

/** Used when the user has not chosen a default template (matches the api). */
export const DEFAULT_TEMPLATE_ID = 'classic';

/** The built-in templates first, then the user's own, each group in the api's order. */
export function inCatalogOrder(templates: TemplateMeta[]): TemplateMeta[] {
	return [...templates.filter((t) => !t.custom), ...templates.filter((t) => t.custom)];
}

/**
 * Template metadata from the api, loaded once per session and again after the user's own templates
 * change. Every template picker reads it, so a custom template shows up after the built-in ones
 * everywhere at once.
 */
class TemplateCatalog {
	list = $state<TemplateMeta[]>([]);
	#loading: Promise<void> | null = null;

	/** The templates that ship with the app. */
	get builtIn(): TemplateMeta[] {
		return this.list.filter((template) => !template.custom);
	}

	/** The signed-in user's own, ready to use. */
	get custom(): TemplateMeta[] {
		return this.list.filter((template) => template.custom);
	}

	load(): Promise<void> {
		this.#loading ??= unwrap(api.GET('/api/v1/templates')).then(
			(templates) => {
				this.list = inCatalogOrder(templates);
			},
			(error: unknown) => {
				this.#loading = null;
				throw error;
			}
		);
		return this.#loading;
	}

	/** Load the list again, after a custom template was saved, renamed or deleted. */
	refresh(): Promise<void> {
		this.#loading = null;
		return this.load();
	}

	/** Forget everything, so the next user to sign in does not see this one's templates. */
	reset(): void {
		this.#loading = null;
		this.list = [];
	}

	name(id: string): string {
		return this.list.find((template) => template.id === id)?.name ?? id;
	}
}

export const templates = new TemplateCatalog();
