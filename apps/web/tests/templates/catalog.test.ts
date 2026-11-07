import { afterEach, describe, expect, it, vi } from 'vitest';
import type { TemplateMeta } from '#lib/cv/types.ts';
import { inCatalogOrder, templates } from '#lib/templates.svelte.ts';
import { fakeApi, json } from '../extension/fake-api.ts';

function meta(id: string, name: string, custom = false): TemplateMeta {
	return { id, name, description: '', paper_sizes: ['a4'], target_pages: 1, custom };
}

const CLASSIC = meta('classic', 'Classic');
const COMPACT = meta('compact', 'Compact');
const SLATE = meta('u-aaaaaaaaa2', 'Slate', true);

describe('the template catalog', () => {
	afterEach(() => {
		templates.reset();
		vi.unstubAllGlobals();
	});

	it('puts the built-in templates before the user own, each in the api order', () => {
		const ink = meta('u-aaaaaaaaa3', 'Ink', true);
		expect(inCatalogOrder([SLATE, CLASSIC, ink, COMPACT]).map((t) => t.id)).toEqual([
			'classic',
			'compact',
			'u-aaaaaaaaa2',
			'u-aaaaaaaaa3'
		]);
	});

	it('loads once and splits the list into built-in and custom', async () => {
		const { calls } = fakeApi({ 'GET /api/v1/templates': () => json([SLATE, CLASSIC, COMPACT]) });

		await templates.load();
		await templates.load();

		expect(calls).toEqual(['GET /api/v1/templates']);
		expect(templates.list.map((t) => t.name)).toEqual(['Classic', 'Compact', 'Slate']);
		expect(templates.builtIn.map((t) => t.name)).toEqual(['Classic', 'Compact']);
		expect(templates.custom.map((t) => t.name)).toEqual(['Slate']);
	});

	it('loads again on refresh, so a saved, renamed or deleted template shows everywhere', async () => {
		let rows = [CLASSIC, COMPACT];
		const { calls } = fakeApi({ 'GET /api/v1/templates': () => json(rows) });
		await templates.load();
		expect(templates.custom).toEqual([]);

		rows = [CLASSIC, COMPACT, SLATE];
		await templates.refresh();
		expect(templates.custom.map((t) => t.name)).toEqual(['Slate']);
		expect(templates.name('u-aaaaaaaaa2')).toBe('Slate');

		rows = [CLASSIC, COMPACT, { ...SLATE, name: 'Ink' }];
		await templates.refresh();
		expect(templates.name('u-aaaaaaaaa2')).toBe('Ink');

		rows = [CLASSIC, COMPACT];
		await templates.refresh();
		expect(templates.custom).toEqual([]);
		expect(calls).toHaveLength(4);
	});

	it('names an unknown template by its id', () => {
		expect(templates.name('u-gone')).toBe('u-gone');
	});

	it('forgets its list on reset, and tries again after a failed load', async () => {
		fakeApi({ 'GET /api/v1/templates': () => json([CLASSIC, SLATE]) });
		await templates.load();

		templates.reset();
		expect(templates.list).toEqual([]);

		fakeApi({
			'GET /api/v1/templates': () =>
				json({ error: { code: 'internal_error', message: 'Broken' } }, 500)
		});
		await expect(templates.load()).rejects.toThrow('Broken');
		fakeApi({ 'GET /api/v1/templates': () => json([CLASSIC]) });
		await templates.load();
		expect(templates.list.map((t) => t.id)).toEqual(['classic']);
	});
});
