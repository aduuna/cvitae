import { api, ApiError, unwrap } from '#lib/api/client.ts';
import type { Diagnostic } from '#lib/cv/types.ts';

/**
 * Live preview of a saved CV. Stale requests are aborted; on a compile error the last good pages
 * stay and the diagnostics are shown next to them.
 */
export class PreviewState {
	pages = $state<string[]>([]);
	pageCount = $state<number | null>(null);
	loading = $state(false);
	diagnostics = $state<Diagnostic[]>([]);
	error = $state<string | null>(null);

	#documentId: string;
	#controller: AbortController | null = null;

	constructor(documentId: string) {
		this.#documentId = documentId;
	}

	async refresh(): Promise<void> {
		this.#controller?.abort();
		const controller = new AbortController();
		this.#controller = controller;
		this.loading = true;
		try {
			const result = await unwrap(
				api.POST('/api/v1/documents/{document_id}/preview', {
					params: { path: { document_id: this.#documentId } },
					signal: controller.signal
				})
			);
			this.pages = result.pages;
			this.pageCount = result.page_count;
			this.diagnostics = [];
			this.error = null;
		} catch (error) {
			if (controller.signal.aborted) return;
			if (error instanceof ApiError && error.code === 'render_failed') {
				this.diagnostics = (error.details.diagnostics as Diagnostic[] | undefined) ?? [];
				this.error = null;
			} else {
				this.error = error instanceof ApiError ? error.message : 'The preview could not load.';
			}
		} finally {
			if (this.#controller === controller) {
				this.loading = false;
				this.#controller = null;
			}
		}
	}

	dispose(): void {
		this.#controller?.abort();
	}
}

/** Width of an SVG page in CSS pixels, from its `width="...pt"` attribute (A4 by default). */
export function pageWidthPx(svg: string): number {
	const points = /<svg[^>]*\swidth="([\d.]+)pt"/.exec(svg)?.[1];
	return Math.round((points ? Number(points) : 595.28) * (96 / 72));
}

/** An image URL for an SVG page. Images cannot run scripts or clash with other pages' ids. */
export function svgDataUrl(svg: string): string {
	return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}
