import { afterEach, describe, expect, it, vi } from 'vitest';
import { loadMode, saveMode } from '#lib/components/editor/mode.ts';

describe('editing mode storage', () => {
	afterEach(() => {
		localStorage.clear();
		vi.restoreAllMocks();
	});

	it('defaults to Form and remembers the last mode', () => {
		expect(loadMode()).toBe('form');

		saveMode('typst');

		expect(loadMode()).toBe('typst');
	});

	it('ignores unknown values', () => {
		localStorage.setItem('vitae.editor.mode', 'wysiwyg');

		expect(loadMode()).toBe('form');
	});

	it('works without storage', () => {
		vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
			throw new Error('blocked');
		});
		vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
			throw new Error('blocked');
		});

		expect(() => saveMode('markdown')).not.toThrow();
		expect(loadMode()).toBe('form');
	});
});
