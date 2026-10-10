import { api, unwrap } from '#lib/api/client.ts';
import type { TemplateMeta } from '#lib/cv/types.ts';

/** Template metadata from the api, loaded once per session. */
class TemplateCatalog {
	list = $state<TemplateMeta[]>([]);
	#loading: Promise<void> | null = null;

	load(): Promise<void> {
		this.#loading ??= unwrap(api.GET('/api/v1/templates')).then(
			(templates) => {
				this.list = templates;
			},
			(error: unknown) => {
				this.#loading = null;
				throw error;
			}
		);
		return this.#loading;
	}

	name(id: string): string {
		return this.list.find((template) => template.id === id)?.name ?? id;
	}
}

export const templates = new TemplateCatalog();
