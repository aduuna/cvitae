import { afterEach, describe, expect, it, vi } from 'vitest';
import { pageWidthPx, PreviewState, svgDataUrl } from '#lib/preview.svelte.ts';

function json(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

describe('PreviewState', () => {
	afterEach(() => vi.unstubAllGlobals());

	it('shows the rendered pages', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => json({ pages: ['<svg/>', '<svg/>'], page_count: 2 }))
		);
		const preview = new PreviewState('doc-1');

		await preview.refresh();

		expect(preview.pages).toEqual(['<svg/>', '<svg/>']);
		expect(preview.pageCount).toBe(2);
		expect(preview.loading).toBe(false);
	});

	it('keeps the last good pages and shows diagnostics on a compile error', async () => {
		const diagnostics = [{ message: 'unknown variable: x', line: 3, column: 1, file: 'main.typ' }];
		const fetch = vi
			.fn()
			.mockResolvedValueOnce(json({ pages: ['<svg>good</svg>'], page_count: 1 }))
			.mockResolvedValueOnce(
				json({ error: { code: 'render_failed', message: 'x', details: { diagnostics } } }, 422)
			)
			.mockResolvedValueOnce(
				json({ error: { code: 'service_unavailable', message: 'Busy.' } }, 503)
			);
		vi.stubGlobal('fetch', fetch);
		const preview = new PreviewState('doc-1');

		await preview.refresh();
		await preview.refresh();
		expect(preview.pages).toEqual(['<svg>good</svg>']);
		expect(preview.diagnostics).toEqual(diagnostics);

		await preview.refresh();
		expect(preview.error).toBe('Busy.');
		expect(preview.pages).toEqual(['<svg>good</svg>']);
	});

	it('aborts a stale request when a newer one starts', async () => {
		const signals: AbortSignal[] = [];
		vi.stubGlobal(
			'fetch',
			vi.fn(async (request: Request) => {
				signals.push(request.signal);
				return json({ pages: [`<svg>${signals.length}</svg>`], page_count: 1 });
			})
		);
		const preview = new PreviewState('doc-1');

		const first = preview.refresh();
		const second = preview.refresh();
		await Promise.all([first, second]);

		expect(signals[0]?.aborted).toBe(true);
		expect(preview.pages).toEqual(['<svg>2</svg>']);
	});
});

describe('page helpers', () => {
	it('reads the page width in points', () => {
		expect(pageWidthPx('<svg viewBox="0 0 612 792" width="612pt" height="792pt">')).toBe(816);
		expect(pageWidthPx('<svg>')).toBe(794);
	});

	it('makes an image URL', () => {
		expect(svgDataUrl('<svg a="#"/>')).toBe(
			'data:image/svg+xml;charset=utf-8,%3Csvg%20a%3D%22%23%22%2F%3E'
		);
	});
});
